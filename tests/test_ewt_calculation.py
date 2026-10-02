"""EWT engine + queue edge-case tests (master blueprint v1.1, Part B + Part D).

Run:  python -m pytest tests/test_ewt_calculation.py -q

Three groups:
  1. **Pure EWT maths** — the estimate must be explainable, so every branch has
     a test with hand-computed numbers.
  2. **BUG-01 regression** — the public booking token counter used to ignore the
     clinic, so two clinics shared one sequence. This is the test that proves it
     is fixed.
  3. **Production upgrade safety** — adding columns to `queue_entries` must not
     break an existing SQLite database (that is how the live PA database
     upgrades itself on restart).
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_TEST_DB = ROOT / "test_ewt_calculation.db"
if _TEST_DB.exists():
    try:
        _TEST_DB.unlink()
    except Exception:
        pass

os.environ["GHOS_DB_URL"] = f"sqlite:///{_TEST_DB}"
os.environ["SYSTEM_AI_FALLBACK_ENABLED"] = "false"

import pytest  # noqa: E402
import sqlalchemy as sa  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import main_v2  # noqa: E402
from src.domain.queue import ewt  # noqa: E402
from src.domain.queue.value_objects.queue_status import QueueStatus  # noqa: E402
from src.infrastructure.clinic.models.clinic_model import ClinicModel  # noqa: E402
from src.infrastructure.queue.models.queue_entry_model import QueueEntryModel  # noqa: E402
from src.shared.infrastructure.database import async_session_factory  # noqa: E402

main_v2.Base.metadata.create_all(bind=main_v2.engine)

NOW = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)


# ══════════════════════════════════════════════════════════════════════════
# 1. Pure EWT maths
# ══════════════════════════════════════════════════════════════════════════


class TestServiceMinutes:
    def test_missing_timestamps_give_nothing(self):
        assert ewt.service_minutes(None, NOW) is None
        assert ewt.service_minutes(NOW, None) is None

    def test_normal_consultation(self):
        assert ewt.service_minutes(NOW - timedelta(minutes=9), NOW) == pytest.approx(9.0)

    def test_negative_and_insane_values_are_rejected(self):
        # staff clicked start twice → negative duration
        assert ewt.service_minutes(NOW, NOW - timedelta(minutes=5)) is None
        # forgot to complete an entry → 5 hour "consultation"
        assert ewt.service_minutes(NOW - timedelta(hours=5), NOW) is None

    def test_naive_and_iso_strings_are_accepted(self):
        assert ewt.service_minutes("2026-10-02T11:50:00", "2026-10-02T12:00:00") == pytest.approx(10.0)


class TestAverage:
    def test_no_history_falls_back(self):
        avg, samples = ewt.avg_service_minutes([])
        assert avg == ewt.DEFAULT_AVG_MINUTES
        assert samples == 0

    def test_small_sample_leans_on_the_fallback(self):
        # One 20-minute visit should not immediately become "20 min per patient".
        avg, samples = ewt.avg_service_minutes([20.0])
        assert samples == 1
        assert ewt.DEFAULT_AVG_MINUTES < avg < 20.0

    def test_enough_history_uses_the_real_average(self):
        avg, samples = ewt.avg_service_minutes([8, 9, 10, 9, 8, 9, 10])
        assert samples == 7
        assert 8.0 <= avg <= 10.0

    def test_longest_outlier_is_trimmed(self):
        trimmed, _ = ewt.avg_service_minutes([8, 9, 10, 8, 9, 100])
        untrimmed = sum([8, 9, 10, 8, 9, 100]) / 6
        assert trimmed < untrimmed

    def test_entries_with_timestamps_are_understood(self):
        rows = [
            {"started_at": NOW - timedelta(minutes=m), "completed_at": NOW}
            for m in (6, 7, 8, 6, 7, 8)
        ]
        avg, samples = ewt.avg_service_minutes(rows)
        assert samples == 6
        assert 5.0 <= avg <= 9.0

    def test_average_is_clamped_to_a_sane_band(self):
        avg, _ = ewt.avg_service_minutes([2.5] * 10)
        assert avg >= ewt.MIN_AVG_MINUTES
        avg_high, _ = ewt.avg_service_minutes([40.0] * 10)
        assert avg_high <= ewt.MAX_AVG_MINUTES


class TestVisitTyping:
    def test_first_visit_is_new(self):
        assert ewt.classify_visit_type(total_visits=1) == "new"

    def test_returning_patient_is_followup(self):
        assert ewt.classify_visit_type(total_visits=6) == "followup"

    def test_attachted_report_is_a_report_review(self):
        assert ewt.classify_visit_type(total_visits=4, has_report=True) == "report"

    def test_non_opd_service_is_a_procedure(self):
        assert ewt.classify_visit_type(total_visits=3, service_code="ECG") == "procedure"

    def test_weights_match_the_blueprint(self):
        assert ewt.visit_weight("new") > 1.0
        assert ewt.visit_weight("followup") < 1.0
        assert ewt.complexity_weight("new") == 2
        assert ewt.complexity_weight("followup") == 1


class TestEstimateWait:
    def test_next_in_line_waits_zero(self):
        estimate = ewt.estimate_wait(ahead=[], current=None, now=NOW)
        assert estimate.minutes == 0
        assert estimate.patients_ahead == 0
        assert "baari" in estimate.note.lower()

    def test_chamber_gate_never_promises_a_countdown(self):
        estimate = ewt.estimate_wait(
            ahead=[{"visit_type": "new"}], current=None, chamber_open=False, now=NOW
        )
        assert estimate.minutes == 0
        assert estimate.state == "arrival_pending"
        assert estimate.chamber_open is False
        assert "safe" in estimate.note.lower()

    def test_three_waiting_with_an_overrunning_case(self):
        """The documented example: 3 ahead (1 new + 2 follow-up) + 20 min overrun.

        waiting  = 1.8×7 + 0.75×7 + 0.75×7 = 23.1
        inside   = expected 12.6, spent 20 → remaining 0, overrun 7.4
        total    = 30.5 → 30 minutes
        """
        ahead = [
            {"visit_type": "new"},
            {"visit_type": "followup"},
            {"visit_type": "followup"},
        ]
        current = {"visit_type": "new", "started_at": NOW - timedelta(minutes=20)}
        estimate = ewt.estimate_wait(
            ahead=ahead, avg_minutes=7.0, samples=25, current=current, now=NOW
        )
        assert estimate.minutes == 30
        assert estimate.patients_ahead == 4  # the patient inside counts as ahead
        assert estimate.delay_minutes == pytest.approx(7.4, abs=0.1)
        assert estimate.confidence == "high"

    def test_patient_inside_is_counted_through_remaining_time_not_twice(self):
        # Doctor just started a routine case: ~7 min remain, 0 overrun.
        current = {"visit_type": "followup", "started_at": NOW}
        estimate = ewt.estimate_wait(
            ahead=[], avg_minutes=8.0, samples=30, current=current, now=NOW
        )
        assert estimate.minutes == pytest.approx(6, abs=1)  # 0.75 × 8 = 6
        assert estimate.patients_ahead == 1

    def test_never_shows_zero_while_someone_is_ahead(self):
        estimate = ewt.estimate_wait(
            ahead=[{"visit_type": "report"}], avg_minutes=2.0, samples=30, now=NOW
        )
        assert estimate.minutes >= ewt.MIN_EWT_MINUTES

    def test_estimate_is_capped(self):
        ahead = [{"visit_type": "new"} for _ in range(60)]
        estimate = ewt.estimate_wait(ahead=ahead, avg_minutes=30.0, samples=40, now=NOW)
        assert estimate.minutes == ewt.MAX_EWT_MINUTES

    def test_a_called_patient_is_not_charged_twice(self):
        me = {"called_at": NOW - timedelta(minutes=10)}
        without = ewt.estimate_wait(
            ahead=[{"visit_type": "followup"}], avg_minutes=8.0, samples=30, now=NOW
        )
        with_me = ewt.estimate_wait(
            ahead=[{"visit_type": "followup"}],
            avg_minutes=8.0,
            samples=30,
            me=me,
            now=NOW,
        )
        assert with_me.minutes <= without.minutes

    def test_public_payload_is_json_safe(self):
        estimate = ewt.estimate_wait(ahead=[{"visit_type": "new"}], now=NOW)
        payload = estimate.to_public_dict()
        assert set(payload) >= {"wait_minutes", "patients_ahead", "state", "chamber_open"}
        assert isinstance(payload["wait_minutes"], int)

    def test_hinglish_line_is_honest_when_the_doctor_is_absent(self):
        estimate = ewt.estimate_wait(ahead=[{"visit_type": "new"}], chamber_open=False, now=NOW)
        assert "chamber" in estimate.to_line_hi().lower()


class TestConfidenceAndDelay:
    def test_confidence_needs_history(self):
        assert ewt.eta_confidence(2, 0) == "low"
        assert ewt.eta_confidence(2, 10) == "medium"
        assert ewt.eta_confidence(2, 30) == "high"

    def test_delay_badge_thresholds(self):
        assert ewt.delay_severity(None, 7.0, now=NOW) == "none"
        # 9 minutes into a 7-minute average → +2 → still fine
        mild = {"started_at": NOW - timedelta(minutes=9)}
        assert ewt.delay_severity(mild, 7.0, now=NOW) == "none"
        # 13 minutes → +6 → warning
        warn = {"started_at": NOW - timedelta(minutes=13)}
        assert ewt.delay_severity(warn, 7.0, now=NOW) == "warning"
        # 19 minutes → +12 → critical
        crit = {"started_at": NOW - timedelta(minutes=19)}
        assert ewt.delay_severity(crit, 7.0, now=NOW) == "critical"


class TestHoldStatus:
    def test_hold_is_part_of_the_live_queue(self):
        assert QueueStatus.HOLD.is_active is True
        assert QueueStatus.HOLD.is_terminal is False

    def test_transitions_around_hold(self):
        assert QueueStatus.CALLED.can_transition_to(QueueStatus.HOLD) is True
        assert QueueStatus.WAITING.can_transition_to(QueueStatus.HOLD) is True
        assert QueueStatus.HOLD.can_transition_to(QueueStatus.WAITING) is True
        # a held patient cannot jump straight into the chamber
        assert QueueStatus.HOLD.can_transition_to(QueueStatus.IN_PROGRESS) is False


# ══════════════════════════════════════════════════════════════════════════
# 2. BUG-01 regression — per-clinic token sequences
# ══════════════════════════════════════════════════════════════════════════


def _make_clinic(code: str, name: str) -> str:
    """Insert a clinic row and return its id (string)."""
    import asyncio

    from src.shared.domain.base_entity import uuid7

    clinic_id = uuid7()

    async def _insert():
        async with async_session_factory() as session:
            session.add(
                ClinicModel(
                    id=clinic_id,
                    clinic_name=name,
                    clinic_code=code,
                    doctor_name=f"Dr {name}",
                    specialty="Cardiology",
                    city="Jodhpur",
                    state="Rajasthan",
                    is_license_active=True,
                    is_active=True,
                )
            )
            await session.commit()
        return str(clinic_id)

    return asyncio.run(_insert())


@pytest.fixture(scope="module")
def client():
    """Plain TestClient — no lifespan, so no schedulers or backup threads run."""
    return TestClient(main_v2.app)


class TestBookingTokens:
    """BUG-01: the token counter must be partitioned per clinic."""

    def test_two_clinics_get_independent_token_sequences(self, client):
        clinic_a = _make_clinic("T-A", "Alpha Clinic")
        clinic_b = _make_clinic("T-B", "Beta Clinic")

        first_a = client.post(
            "/api/v1/marketplace/book",
            json={"clinic_id": clinic_a, "name": "A-1", "phone": "9000000001"},
        ).json()
        first_b = client.post(
            "/api/v1/marketplace/book",
            json={"clinic_id": clinic_b, "name": "B-1", "phone": "9000000002"},
        ).json()
        second_a = client.post(
            "/api/v1/marketplace/book",
            json={"clinic_id": clinic_a, "name": "A-2", "phone": "9000000003"},
        ).json()

        assert first_a["ok"] and first_b["ok"] and second_a["ok"]
        # Before the fix clinic B would have received token #2.
        assert first_a["token"] == 1
        assert first_b["token"] == 1
        assert second_a["token"] == 2

    def test_booking_stores_visit_type_and_a_wait_promise(self, client):
        clinic = _make_clinic("T-C", "Gamma Clinic")
        payload = client.post(
            "/api/v1/marketplace/book",
            json={"clinic_id": clinic, "name": "C-1", "phone": "9000000004", "age": 71},
        ).json()
        assert payload["ok"]
        assert payload["visit_type"] == "new"
        assert payload["room"]  # BUG-02: room used to be empty
        assert payload["patients_ahead"] == 0
        assert payload["wait_state"] in ("live", "arrival_pending")

        async def _read():
            async with async_session_factory() as session:
                row = await session.execute(
                    sa.select(QueueEntryModel)
                    .where(QueueEntryModel.clinic_id == clinic)
                    .limit(1)
                )
                entry = row.scalars().first()
                return entry.doctor_id, entry.sort_key, entry.complexity_weight

        import asyncio

        doctor_id, sort_key, weight = asyncio.run(_read())
        assert doctor_id == "chief"
        assert sort_key == 1.0
        assert weight == 2  # a new case is heavy

    def test_family_sharing_one_phone_does_not_crash_booking(self, client):
        """A shared family number matches several patients — booking must not 500."""
        clinic = _make_clinic("T-D", "Delta Clinic")
        for name in ("Father", "Mother", "Child"):
            response = client.post(
                "/api/v1/marketplace/book",
                json={"clinic_id": clinic, "name": name, "phone": "9000000009"},
            )
            assert response.status_code == 200
            assert response.json()["ok"] is True


# ══════════════════════════════════════════════════════════════════════════
# 4. Queue engine endpoints — chamber gate (E-01) + hold/return (E-02)
# ══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def opd_doctor(monkeypatch):
    """Pretend a chief doctor is logged into the OPD dashboard."""
    from src.presentation.opd.routes import opd_routes

    monkeypatch.setattr(
        opd_routes,
        "_require_opd_session",
        lambda request: {
            "role": "chief",
            "doctor_id": "chief",
            "name": "Dr Test",
            "lic_info": {},
        },
    )
    return "chief"


def _make_entry(
    clinic_id: str,
    token: int,
    status: str = "WAITING",
    patient_name: str = "Patient",
    sort_key: float | None = None,
    started_at: datetime | None = None,
    patient_id: str | None = None,
) -> str:
    """Insert a queue entry directly and return its id."""
    import asyncio

    from src.shared.domain.base_entity import uuid7

    entry_id = uuid7()
    now = datetime.now(timezone.utc)
    pid = patient_id or f"T-{token}"

    async def _insert():
        async with async_session_factory() as session:
            session.add(
                QueueEntryModel(
                    id=entry_id,
                    clinic_id=clinic_id,
                    doctor_id="chief",
                    visit_id=f"VIS-TEST-{token}",
                    patient_id=pid,
                    patient_uuid=str(uuid7()),
                    patient_name=patient_name,
                    service_code="OPD",
                    token_number=token,
                    department="Cardiology",
                    room="OPD Room",
                    status=status,
                    priority=0,
                    display_order=0,
                    sort_key=float(sort_key if sort_key is not None else token),
                    visit_type="followup",
                    complexity_weight=1,
                    created_by="test",
                    updated_by="test",
                    version=1,
                    started_at=started_at,
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.commit()
        return str(entry_id)

    return asyncio.run(_insert())


async def _read_entry(entry_id: str):
    import uuid as _uuid

    async with async_session_factory() as session:
        return await session.get(QueueEntryModel, _uuid.UUID(entry_id))


class TestChamberGate:
    def test_open_then_close_toggles_the_gate(self, client, opd_doctor):
        clinic = _make_clinic("T-E", "Echo Clinic")
        _make_entry(clinic, 1, status="WAITING")

        opened = client.post("/opd/api/chamber/open", json={"scheduled_time": "09:00"}).json()
        assert opened["ok"] is True
        assert opened["chamber_open"] is True
        assert opened["tracked"] is True

        status = client.get("/opd/api/chamber/status").json()
        assert status["chamber_open"] is True
        assert status["waiting"] >= 1

        closed = client.post("/opd/api/chamber/close", json={}).json()
        assert closed["ok"] is True
        assert closed["chamber_open"] is False

    def test_queue_ewt_is_arrival_pending_before_the_doctor_starts(self, client, opd_doctor):
        """E-01: with an unopened chamber nobody may be promised a countdown."""
        import asyncio

        from src.infrastructure.queue.models.chamber_session_model import (
            ChamberSessionModel,
        )

        clinic = _make_clinic("T-F", "Foxtrot Clinic")
        _make_entry(clinic, 1, status="WAITING", patient_name="Wait One")
        _make_entry(clinic, 2, status="WAITING", patient_name="Wait Two")

        now = datetime.now(timezone.utc)

        async def _closed_session():
            async with async_session_factory() as session:
                session.add(
                    ChamberSessionModel(
                        clinic_id=clinic,
                        doctor_id="chief",
                        session_date=now.date(),
                        scheduled_time="09:00",
                        opened_at=None,
                        created_at=now,
                        updated_at=now,
                    )
                )
                await session.commit()

        asyncio.run(_closed_session())

        feed = client.get("/opd/api/queue-ewt").json()
        assert feed["ok"] is True
        assert feed["chamber_open"] is False
        for row in feed["queue"]:
            assert row["wait_minutes"] == 0, "no fabricated countdown while the chamber is shut"


class TestHoldAndReturn:
    def test_returning_patient_lands_right_after_the_chamber(self, client, opd_doctor):
        clinic = _make_clinic("T-G", "Golf Clinic")
        _make_entry(clinic, 1, status="IN_PROGRESS", sort_key=1.0, patient_name="Inside")
        _make_entry(clinic, 2, status="WAITING", sort_key=2.0, patient_name="Next")
        held_id = _make_entry(clinic, 3, status="WAITING", sort_key=3.0, patient_name="Washroom")

        hold = client.post(
            "/opd/api/queue/hold", json={"entry_id": held_id, "reason": "washroom"}
        ).json()
        assert hold["ok"] is True and hold["status"] == "HOLD"

        back = client.post("/opd/api/queue/requeue", json={"entry_id": held_id}).json()
        assert back["ok"] is True
        # Next + 1: between the patient inside (1.0) and the next waiting (2.0)
        assert back["patients_ahead"] == 0

        import asyncio

        entry = asyncio.run(_read_entry(held_id))
        assert entry.status == "WAITING"
        assert entry.sort_key == pytest.approx(1.5)
        assert entry.requeue_count == 1

    def test_second_return_goes_to_the_back(self, client, opd_doctor):
        clinic = _make_clinic("T-H", "Hotel Clinic")
        _make_entry(clinic, 1, status="WAITING", sort_key=1.0)
        _make_entry(clinic, 2, status="WAITING", sort_key=2.0)
        held_id = _make_entry(clinic, 3, status="WAITING", sort_key=3.0)

        client.post("/opd/api/queue/hold", json={"entry_id": held_id})
        client.post("/opd/api/queue/requeue", json={"entry_id": held_id})
        client.post("/opd/api/queue/hold", json={"entry_id": held_id})
        client.post("/opd/api/queue/requeue", json={"entry_id": held_id})

        import asyncio

        entry = asyncio.run(_read_entry(held_id))
        assert entry.requeue_count == 2
        # Both other patients (sort_key 1.0 and 2.0) stay in front.
        assert entry.sort_key > 2.0, "a second hold must not jump the line"

    def test_cannot_hold_someone_already_inside(self, client, opd_doctor):
        clinic = _make_clinic("T-I", "India Clinic")
        inside_id = _make_entry(clinic, 1, status="IN_PROGRESS")
        response = client.post("/opd/api/queue/hold", json={"entry_id": inside_id})
        assert response.status_code == 400


class TestPublicTrackingWait:
    def test_tracking_status_exposes_the_live_wait(self, client):
        """The patient's WhatsApp link must show the real wait, not a guess."""
        clinic = _make_clinic("T-J", "Juliet Clinic")
        _make_entry(clinic, 2, status="IN_PROGRESS", patient_name="Inside", patient_id="P-INSIDE")
        _make_entry(clinic, 3, status="WAITING", patient_name="Ahead", patient_id="P-AHEAD")
        _make_entry(clinic, 4, status="WAITING", patient_name="Me", patient_id="P-ME")

        from src.presentation.staff.routes.staff_routes import make_tracking_token

        token = make_tracking_token("P-ME")
        payload = client.get(f"/track/{token}/status").json()

        assert payload["ok"] is True
        wait = payload["wait"]
        assert wait, "tracking payload should carry a wait estimate"
        assert wait["patients_ahead"] == 2  # the patient inside + the one waiting
        assert wait["wait_minutes"] > 0
        assert wait["chamber_open"] is True  # no session recorded → backward compatible
        assert "leave_now" in wait
        assert wait["line"]


# ══════════════════════════════════════════════════════════════════════════
# 5. Production upgrade safety — additive SQLite migration
# ══════════════════════════════════════════════════════════════════════════


LEGACY_QUEUE_TABLE = """
CREATE TABLE queue_entries (
    id TEXT PRIMARY KEY,
    clinic_id VARCHAR(36),
    visit_id VARCHAR(50) NOT NULL,
    patient_id VARCHAR(30) NOT NULL,
    patient_uuid VARCHAR(36) NOT NULL,
    patient_name VARCHAR(200) NOT NULL,
    service_code VARCHAR(30) NOT NULL,
    token_number INTEGER NOT NULL,
    department VARCHAR(100) NOT NULL,
    room VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL,
    priority INTEGER NOT NULL DEFAULT 0,
    display_order INTEGER NOT NULL DEFAULT 0,
    created_by VARCHAR(100) NOT NULL DEFAULT '',
    updated_by VARCHAR(100) NOT NULL DEFAULT '',
    pending_alert BOOLEAN NOT NULL DEFAULT 0,
    alert_message VARCHAR(500),
    notes VARCHAR(2000) NOT NULL DEFAULT '',
    called_at DATETIME,
    started_at DATETIME,
    completed_at DATETIME,
    report_ready_at DATETIME,
    delivered_at DATETIME,
    version INTEGER NOT NULL DEFAULT 1,
    created_at DATETIME,
    updated_at DATETIME
);
"""


def test_migrator_adds_the_new_columns_to_an_old_database():
    """The live PA database is upgraded by ``_migrate_sqlite_columns()`` on boot.

    This runs the REAL migrator against a database that only has the pre-EWT
    schema — if this passes, the production upgrade path is safe.
    """
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "legacy.db"
        out_path = Path(tmp) / "out.txt"
        script = "\n".join(
            [
                "import os, sqlite3, sys",
                f"os.environ['GHOS_DB_URL'] = 'sqlite:///{db_path.as_posix()}'",
                f"sys.path.insert(0, {str(ROOT)!r})",
                "import main_v2",
                "con = sqlite3.connect(r'" + str(db_path) + "')",
                "con.executescript(r'''" + LEGACY_QUEUE_TABLE + "''')",
                "con.commit(); con.close()",
                # Mirror the real boot order from main_v2.lifespan():
                #   1. create_all()  → creates brand new tables (chamber_sessions)
                #   2. _migrate_sqlite_columns() → ALTERs new columns onto old tables
                "main_v2.Base.metadata.create_all(bind=main_v2.engine)",
                "main_v2._migrate_sqlite_columns()",
                "con = sqlite3.connect(r'" + str(db_path) + "')",
                "cols = {r[1] for r in con.execute('PRAGMA table_info(queue_entries)')}",
                "tables = {r[0] for r in con.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")}",
                "print('COLUMNS=' + ','.join(sorted(cols)))",
                "print('TABLES=' + ','.join(sorted(tables)))",
                "con.close()",
            ]
        )
        script_path = Path(tmp) / "run.py"
        script_path.write_text(script, encoding="utf-8")

        with out_path.open("w", encoding="utf-8") as sink:
            subprocess.run(
                [sys.executable, str(script_path)],
                stdout=sink,
                stderr=subprocess.STDOUT,
                cwd=str(ROOT),
                check=False,
            )

        output = out_path.read_text(encoding="utf-8", errors="ignore")
        line = next((ln for ln in output.splitlines() if ln.startswith("COLUMNS=")), "")
        assert line, f"migrator produced no output:\n{output}"
        columns = set(line.split("=", 1)[1].split(","))

        for expected in (
            "doctor_id",
            "visit_type",
            "complexity_weight",
            "estimated_minutes",
            "sort_key",
            "requeue_count",
            "held_at",
            "hold_reason",
        ):
            assert expected in columns, f"{expected} was not added to the legacy table"

        tables_line = next((ln for ln in output.splitlines() if ln.startswith("TABLES=")), "")
        assert "chamber_sessions" in tables_line.split("=", 1)[1]
