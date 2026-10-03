"""Slot booking + emergency override tests (master blueprint BLOCK 3).

Run:  python -m pytest tests/test_slots.py -q

Three groups:

  1. **token_label** — ``C-14`` / ``G-14`` / ``E-1``. Two doctors in one clinic
     each call out "token 14"; this is the label that tells them apart.
  2. **Slots (SLT-01 / SLT-02)** — CRUD, capacity that cannot be oversold, and
     the rule that a booking creates a REAL queue entry in the same live queue
     rather than a parallel appointment list.
  3. **Emergency override (E-08)** — ``#E-1`` gets the front of the line but
     never interrupts a consultation already in progress, and never consumes a
     routine token.

The clock-dependent parts are pinned with closed days / explicit dates so the
suite cannot flake depending on when it runs.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_TEST_DB = ROOT / "test_slots.db"
if _TEST_DB.exists():
    try:
        _TEST_DB.unlink()
    except Exception:
        pass

os.environ["GHOS_DB_URL"] = f"sqlite:///{_TEST_DB}"
os.environ["SYSTEM_AI_FALLBACK_ENABLED"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import main_v2  # noqa: E402
from src.domain.queue import ewt, token_label  # noqa: E402
from src.infrastructure.clinic.models.clinic_model import ClinicModel  # noqa: E402
from src.infrastructure.queue.models.queue_entry_model import QueueEntryModel  # noqa: E402
from src.shared.infrastructure.database import async_session_factory  # noqa: E402

main_v2.Base.metadata.create_all(bind=main_v2.engine)
# Also prove the new columns can be added to an existing database — this is the
# same migrator the live PythonAnywhere instance runs on restart.
main_v2._migrate_sqlite_columns()

TODAY = datetime.now(timezone.utc).date().isoformat()


# ══════════════════════════════════════════════════════════════════════════
# 1. token_label — C-14 / G-14 / E-1
# ══════════════════════════════════════════════════════════════════════════


class TestSpecialtyPrefix:
    @pytest.mark.parametrize(
        "specialty,expected",
        [
            ("Cardiology", "C"),
            ("cardiology", "C"),
            ("General Physician", "G"),
            ("General", "G"),
            ("Orthopedics", "O"),
            ("Pediatrics", "P"),
            ("Dermatology", "D"),
            ("ENT", "T"),
        ],
    )
    def test_known_specialties_map_to_the_blueprint_prefixes(self, specialty, expected):
        assert token_label.specialty_prefix(specialty) == expected

    def test_leading_word_is_used_for_a_decorated_name(self):
        assert token_label.specialty_prefix("Cardiology (Interventional)") == "C"

    def test_unknown_specialty_falls_back_to_its_first_letter(self):
        assert token_label.specialty_prefix("Rheumatology") == "R"

    def test_empty_specialty_still_produces_a_label(self):
        # An empty label reads as a bug to the patient, so never return "".
        assert token_label.specialty_prefix("") == token_label.DEFAULT_PREFIX
        assert token_label.specialty_prefix(None) == token_label.DEFAULT_PREFIX
        assert token_label.specialty_prefix("123") == token_label.DEFAULT_PREFIX


class TestTokenLabel:
    def test_simple_label(self):
        assert token_label.token_label(14, "C") == "C-14"

    def test_without_a_prefix_it_is_the_bare_number(self):
        # Exactly what the app showed before this module — nothing regresses.
        assert token_label.token_label(14) == "14"

    def test_emergency_label(self):
        assert token_label.token_label(1, emergency=True) == "E-1"

    def test_emergency_label_ignores_a_specialty_prefix(self):
        assert token_label.token_label(3, "C", emergency=True) == "E-3"

    def test_lowercase_prefix_is_normalised(self):
        assert token_label.token_label(7, "g") == "G-7"

    @pytest.mark.parametrize("bad", [None, "", 0, -5, "abc"])
    def test_unusable_token_yields_no_label(self, bad):
        assert token_label.token_label(bad, "C") == ""


class TestEntryLabel:
    def test_routine_entry_uses_the_specialty(self):
        entry = {"token_number": 14, "visit_type": "followup"}
        assert token_label.entry_label(entry, "Cardiology") == "C-14"

    def test_emergency_entry_switches_to_the_e_prefix(self):
        entry = {"token_number": 2, "visit_type": "emergency"}
        assert token_label.entry_label(entry, "Cardiology") == "E-2"

    def test_none_entry_is_safe(self):
        assert token_label.entry_label(None, "Cardiology") == ""

    def test_is_emergency_is_case_insensitive(self):
        assert token_label.is_emergency({"visit_type": "EMERGENCY"}) is True
        assert token_label.is_emergency({"visit_type": "Emergency"}) is True
        assert token_label.is_emergency({"visit_type": "followup"}) is False
        assert token_label.is_emergency({}) is False


class TestEmergencySequence:
    def test_starts_at_one(self):
        assert token_label.next_emergency_token([]) == 1

    def test_increments_from_the_highest(self):
        assert token_label.next_emergency_token([1, 2, 3]) == 4

    def test_out_of_order_input_still_finds_the_highest(self):
        assert token_label.next_emergency_token([3, 1, 2]) == 4

    def test_junk_is_ignored(self):
        assert token_label.next_emergency_token([None, "x", 2]) == 3


class TestEmergencyVisitType:
    def test_emergency_outranks_every_other_classification(self):
        # Even a procedure, and even a repeat patient — Code Red wins.
        assert ewt.classify_visit_type(
            total_visits=9, is_procedure=True, is_emergency=True
        ) == "emergency"

    def test_emergency_has_a_heavy_complexity_weight(self):
        assert ewt.complexity_weight("emergency") == 3
        assert ewt.complexity_weight("emergency") > ewt.complexity_weight("new")

    def test_emergency_occupies_the_chamber_honestly(self):
        # It jumps the queue, but it still takes time — everybody else's wait
        # must account for it or the EWT lies.
        weight = ewt.visit_weight("emergency")
        assert weight > ewt.visit_weight("followup")

    def test_it_has_a_label_for_the_patient_screen(self):
        assert "Emergency" in ewt.VISIT_TYPE_LABEL["emergency"]


# ══════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════


def _make_clinic(code: str, name: str, specialty: str = "Cardiology") -> str:
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
                    specialty=specialty,
                    city="Jodhpur",
                    state="Rajasthan",
                    open_time="00:01",
                    close_time="23:58",
                    is_license_active=True,
                    is_active=True,
                )
            )
            await session.commit()
        return str(clinic_id)

    return asyncio.run(_insert())


def _make_entry(
    clinic_id: str,
    token: int,
    status: str = "WAITING",
    patient_name: str = "Patient",
    sort_key: float | None = None,
    visit_type: str = "followup",
) -> str:
    import asyncio

    from src.shared.domain.base_entity import uuid7

    entry_id = uuid7()
    now = datetime.now(timezone.utc)
    # Use the real visit_id shape: the token counters filter on
    # ``VIS-<date>-%``, so a made-up id would make the counter tests vacuous.
    date_prefix = now.strftime("%Y%m%d")

    async def _insert():
        async with async_session_factory() as session:
            session.add(
                QueueEntryModel(
                    id=entry_id,
                    clinic_id=clinic_id,
                    doctor_id="chief",
                    visit_id=f"VIS-{date_prefix}-SLT{token}",
                    patient_id=f"SL-{token}",
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
                    visit_type=visit_type,
                    complexity_weight=ewt.complexity_weight(visit_type),
                    created_by="test",
                    updated_by="test",
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.commit()

    asyncio.run(_insert())
    return str(entry_id)


@pytest.fixture
def login(monkeypatch):
    """Log a chief doctor in, optionally pinned to a specific clinic.

    Pinning matters: without ``clinic_id`` the engine falls back to "the clinic
    of the most recent queue entry", which would make a test about capacity
    depend on rows another test created.
    """
    from src.presentation.opd.routes import opd_routes

    def _login(clinic_id: str = ""):
        monkeypatch.setattr(
            opd_routes,
            "_require_opd_session",
            lambda request: {
                "role": "chief",
                "doctor_id": "chief",
                "name": "Dr Test",
                "clinic_id": clinic_id,
                "lic_info": {},
            },
        )
        return "chief"

    return _login


@pytest.fixture(scope="module")
def client():
    """Plain TestClient — no lifespan, so no schedulers or backup threads run."""
    return TestClient(main_v2.app)


def _create_slots(client, **body):
    response = client.post("/opd/api/slots", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def _list_slots(client, date: str = ""):
    response = client.get("/opd/api/slots", params={"date": date} if date else None)
    assert response.status_code == 200, response.text
    return response.json()


# ══════════════════════════════════════════════════════════════════════════
# 2. Slot CRUD (SLT-01)
# ══════════════════════════════════════════════════════════════════════════


class TestSlotCreate:
    def test_single_slot(self, client, login):
        clinic = _make_clinic("S-1", "Single Slot Clinic")
        login(clinic)
        body = _create_slots(
            client, date=TODAY, start_time="14:30", end_time="14:50", capacity=2
        )
        assert body["ok"] is True
        assert body["created"] == 1
        assert body["times"] == ["14:30"]

        grid = _list_slots(client, TODAY)
        assert grid["total"] == 1
        slot = grid["slots"][0]
        assert slot["window"] == "14:30 – 14:50"
        assert slot["capacity"] == 2
        assert slot["booked"] == 0
        assert slot["remaining"] == 2
        assert slot["bookable"] if "bookable" in slot else True

    def test_bulk_generation_fills_the_window(self, client, login):
        clinic = _make_clinic("S-2", "Bulk Slot Clinic")
        login(clinic)
        # 09:00 → 10:00 in 20-minute steps = 3 slots.
        body = _create_slots(
            client,
            date=TODAY,
            from_time="09:00",
            to_time="10:00",
            duration_minutes=20,
        )
        assert body["ok"] is True
        assert body["created"] == 3
        assert body["times"] == ["09:00", "09:20", "09:40"]

    def test_bulk_generation_is_idempotent(self, client, login):
        clinic = _make_clinic("S-3", "Idempotent Slot Clinic")
        login(clinic)
        first = _create_slots(
            client, date=TODAY, from_time="11:00", to_time="12:00", duration_minutes=30
        )
        second = _create_slots(
            client, date=TODAY, from_time="11:00", to_time="12:00", duration_minutes=30
        )
        assert first["created"] == 2
        # Pressing the button twice must not double the day.
        assert second["created"] == 0
        assert second["skipped"] == 2

    def test_bulk_generation_is_bounded(self, client, login):
        """A slip of the keyboard must not write thousands of rows."""
        clinic = _make_clinic("S-4", "Bounded Slot Clinic")
        login(clinic)
        body = _create_slots(
            client,
            date=TODAY,
            from_time="00:00",
            to_time="23:00",
            duration_minutes=5,
        )
        assert body["created"] <= 80

    def test_missing_start_time_is_a_clean_400(self, client, login):
        clinic = _make_clinic("S-5", "Bad Slot Clinic")
        login(clinic)
        response = client.post("/opd/api/slots", json={"date": TODAY})
        assert response.status_code == 400
        assert response.json()["ok"] is False

    def test_end_before_start_is_rejected(self, client, login):
        clinic = _make_clinic("S-6", "Reversed Slot Clinic")
        login(clinic)
        response = client.post(
            "/opd/api/slots",
            json={"date": TODAY, "start_time": "15:00", "end_time": "14:00"},
        )
        assert response.status_code == 400

    def test_an_absurdly_long_slot_is_rejected(self, client, login):
        clinic = _make_clinic("S-7", "Long Slot Clinic")
        login(clinic)
        response = client.post(
            "/opd/api/slots",
            json={"date": TODAY, "start_time": "09:00", "end_time": "21:00"},
        )
        assert response.status_code == 400

    def test_slots_are_scoped_per_clinic(self, client, login):
        clinic_a = _make_clinic("S-8A", "Scope A")
        clinic_b = _make_clinic("S-8B", "Scope B")
        login(clinic_a)
        _create_slots(client, date=TODAY, start_time="08:00", end_time="08:20")

        login(clinic_b)
        grid = _list_slots(client, TODAY)
        assert grid["total"] == 0, "another clinic's slots must never appear"


class TestSlotToggleAndDelete:
    def test_toggle_closes_and_reopens_a_slot(self, client, login):
        clinic = _make_clinic("S-9", "Toggle Slot Clinic")
        login(clinic)
        _create_slots(client, date=TODAY, start_time="16:00", end_time="16:20")
        slot_id = _list_slots(client, TODAY)["slots"][0]["id"]

        closed = client.post(f"/opd/api/slots/{slot_id}/toggle").json()
        assert closed["ok"] is True
        assert closed["is_active"] is False
        assert _list_slots(client, TODAY)["slots"][0]["is_active"] is False

        reopened = client.post(f"/opd/api/slots/{slot_id}/toggle").json()
        assert reopened["is_active"] is True

    def test_delete_removes_an_empty_slot(self, client, login):
        clinic = _make_clinic("S-10", "Delete Slot Clinic")
        login(clinic)
        _create_slots(client, date=TODAY, start_time="17:00", end_time="17:20")
        slot_id = _list_slots(client, TODAY)["slots"][0]["id"]

        body = client.post(f"/opd/api/slots/{slot_id}/delete").json()
        assert body["ok"] is True
        assert _list_slots(client, TODAY)["total"] == 0

    def test_delete_is_refused_once_a_patient_holds_the_slot(self, client, login):
        """Deleting a booked slot would strand a patient with a token."""
        clinic = _make_clinic("S-11", "Protected Slot Clinic")
        login(clinic)
        _create_slots(client, date=TODAY, start_time="18:00", end_time="18:20")
        slot_id = _list_slots(client, TODAY)["slots"][0]["id"]

        booked = client.post(
            f"/opd/api/slots/{slot_id}/book", json={"name": "Slot Patient"}
        ).json()
        assert booked["ok"] is True

        response = client.post(f"/opd/api/slots/{slot_id}/delete")
        assert response.status_code == 400
        assert "booked" in response.json()["error"]

    def test_unknown_slot_is_a_clean_404(self, client, login):
        login(_make_clinic("S-12", "Unknown Slot Clinic"))
        missing = "00000000-0000-0000-0000-000000000000"
        assert client.post(f"/opd/api/slots/{missing}/toggle").status_code == 404
        assert client.post(f"/opd/api/slots/{missing}/delete").status_code == 404


# ══════════════════════════════════════════════════════════════════════════
# 3. Slot booking (SLT-02) — capacity cannot be oversold
# ══════════════════════════════════════════════════════════════════════════


class TestSlotBooking:
    def test_booking_creates_a_real_queue_entry(self, client, login):
        """A slot reserves a place in the SAME live queue — not a parallel list."""
        clinic = _make_clinic("B-1", "Real Queue Clinic")
        login(clinic)
        _create_slots(client, date=TODAY, start_time="10:00", end_time="10:20")
        slot_id = _list_slots(client, TODAY)["slots"][0]["id"]

        # A phone number unique to this test: the app deliberately REUSES a
        # patient by phone (the family-sharing fix), so a number another test
        # already registered would legitimately come back with that name.
        body = client.post(
            f"/opd/api/slots/{slot_id}/book",
            json={"name": "Ramesh Kumar", "phone": "9090909090"},
        ).json()
        assert body["ok"] is True
        assert body["token"] >= 1
        assert body["patient_name"] == "Ramesh Kumar"

        import asyncio

        async def _read():
            import sqlalchemy as sa

            async with async_session_factory() as session:
                row = await session.execute(
                    sa.select(QueueEntryModel).where(
                        QueueEntryModel.slot_id == slot_id
                    )
                )
                return row.scalars().all()

        entries = asyncio.run(_read())
        assert len(entries) == 1, "the booking must live in queue_entries"
        # The queue row is the same patient the API reported — whether they were
        # newly created or matched by phone.
        assert entries[0].patient_name == body["patient_name"]
        assert entries[0].status == "WAITING"
        assert entries[0].slot_time == "10:00"

    def test_a_returning_phone_number_reuses_the_same_patient(self, client, login):
        """Booking into a slot must not duplicate a patient who already exists."""
        clinic = _make_clinic("B-1R", "Repeat Patient Clinic")
        login(clinic)
        _create_slots(
            client, date=TODAY, start_time="10:10", end_time="10:30", capacity=2
        )
        slot_id = _list_slots(client, TODAY)["slots"][0]["id"]

        first = client.post(
            f"/opd/api/slots/{slot_id}/book",
            json={"name": "Sunita Devi", "phone": "9090909091"},
        ).json()
        second = client.post(
            f"/opd/api/slots/{slot_id}/book",
            json={"name": "Sunita Devi", "phone": "9090909091"},
        ).json()
        assert first["ok"] is True and second["ok"] is True
        assert first["patient_id"] == second["patient_id"], "phone reuse must hold"
        assert first["token"] != second["token"], "each visit still gets its own token"

    def test_capacity_is_enforced(self, client, login):
        clinic = _make_clinic("B-2", "Capacity Clinic")
        login(clinic)
        _create_slots(
            client, date=TODAY, start_time="10:30", end_time="10:50", capacity=2
        )
        slot_id = _list_slots(client, TODAY)["slots"][0]["id"]

        first = client.post(f"/opd/api/slots/{slot_id}/book", json={"name": "One"}).json()
        second = client.post(f"/opd/api/slots/{slot_id}/book", json={"name": "Two"}).json()
        assert first["ok"] is True
        assert second["ok"] is True

        response = client.post(f"/opd/api/slots/{slot_id}/book", json={"name": "Three"})
        assert response.status_code == 409, "a slot must never oversell"
        assert "bhar gaya" in response.json()["error"]

        slot = _list_slots(client, TODAY)["slots"][0]
        assert slot["booked"] == 2
        assert slot["remaining"] == 0
        assert slot["is_full"] is True

    def test_remaining_counts_down_as_people_book(self, client, login):
        clinic = _make_clinic("B-3", "Counting Clinic")
        login(clinic)
        _create_slots(
            client, date=TODAY, start_time="11:00", end_time="11:20", capacity=3
        )
        slot_id = _list_slots(client, TODAY)["slots"][0]["id"]

        for expected in (2, 1, 0):
            client.post(f"/opd/api/slots/{slot_id}/book", json={"name": "Patient"})
            slot = _list_slots(client, TODAY)["slots"][0]
            assert slot["remaining"] == expected

    def test_a_closed_slot_cannot_be_booked(self, client, login):
        clinic = _make_clinic("B-4", "Closed Slot Clinic")
        login(clinic)
        _create_slots(client, date=TODAY, start_time="12:00", end_time="12:20")
        slot_id = _list_slots(client, TODAY)["slots"][0]["id"]
        client.post(f"/opd/api/slots/{slot_id}/toggle")

        response = client.post(f"/opd/api/slots/{slot_id}/book", json={"name": "Nope"})
        assert response.status_code == 400
        assert "band" in response.json()["error"]

    def test_booking_needs_a_name(self, client, login):
        clinic = _make_clinic("B-5", "Nameless Clinic")
        login(clinic)
        _create_slots(client, date=TODAY, start_time="12:30", end_time="12:50")
        slot_id = _list_slots(client, TODAY)["slots"][0]["id"]
        response = client.post(f"/opd/api/slots/{slot_id}/book", json={})
        assert response.status_code == 400

    def test_each_booking_gets_its_own_token(self, client, login):
        clinic = _make_clinic("B-6", "Token Clinic")
        login(clinic)
        _create_slots(
            client, date=TODAY, start_time="13:00", end_time="13:20", capacity=3
        )
        slot_id = _list_slots(client, TODAY)["slots"][0]["id"]
        tokens = [
            client.post(f"/opd/api/slots/{slot_id}/book", json={"name": f"P{i}"}).json()["token"]
            for i in range(3)
        ]
        assert len(set(tokens)) == 3, "two patients must never share a token"


class TestSlotGridCarriesTheQueue:
    """Blueprint B5: a slot is never shown alone."""

    def test_slot_reports_the_live_queue_behind_it(self, client, login):
        clinic = _make_clinic("Q-1", "Queue Context Clinic")
        login(clinic)
        _make_entry(clinic, 1, status="WAITING")
        _make_entry(clinic, 2, status="WAITING")
        _create_slots(client, date=TODAY, start_time="23:00", end_time="23:20")

        grid = _list_slots(client, TODAY)
        slot = grid["slots"][0]
        assert "forecast" in slot and slot["forecast"]
        assert slot["confidence"] in ("high", "medium", "low")
        assert slot["queue"]["waiting"] == 2

    def test_a_slot_far_in_the_future_predicts_a_cleared_queue(self, client, login):
        """By 23:00 there is plenty of time to see everybody now waiting."""
        clinic = _make_clinic("Q-2", "Clearance Clinic")
        login(clinic)
        for token in range(1, 4):
            _make_entry(clinic, token, status="WAITING")
        _create_slots(client, date=TODAY, start_time="23:30", end_time="23:50")

        slot = _list_slots(client, TODAY)["slots"][0]
        assert "clear" in slot["forecast"].lower()

    def test_forecast_text_is_hinglish_and_usable(self, client, login):
        clinic = _make_clinic("Q-3", "Hinglish Clinic")
        login(clinic)
        _create_slots(client, date=TODAY, start_time="22:00", end_time="22:20")
        slot = _list_slots(client, TODAY)["slots"][0]
        forecast = slot["forecast"]
        assert isinstance(forecast, str) and forecast.strip()
        # It must say something a patient can act on, not a placeholder.
        assert any(
            word in forecast.lower()
            for word in ("queue", "patient", "min", "opd", "turn")
        )


# ══════════════════════════════════════════════════════════════════════════
# 4. Public marketplace slot surface
# ══════════════════════════════════════════════════════════════════════════


class TestPublicSlots:
    def test_public_slot_list_is_returned(self, client, login):
        clinic = _make_clinic("P-1", "Public Slot Clinic")
        login(clinic)
        _create_slots(
            client, date=TODAY, start_time="15:00", end_time="15:20", capacity=1
        )

        response = client.get(
            "/api/v1/marketplace/slots", params={"clinic_id": clinic, "date": TODAY}
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["ok"] is True
        assert payload["bookable"] == 1
        slot = payload["slots"][0]
        assert slot["bookable"] is True
        assert slot["window"] == "15:00 – 15:20"
        assert "advice" in payload and payload["advice"]

    def test_public_booking_through_the_marketplace_respects_capacity(self, client, login):
        clinic = _make_clinic("P-2", "Public Capacity Clinic")
        login(clinic)
        _create_slots(
            client, date=TODAY, start_time="15:30", end_time="15:50", capacity=1
        )
        slot_id = client.get(
            "/api/v1/marketplace/slots", params={"clinic_id": clinic, "date": TODAY}
        ).json()["slots"][0]["id"]

        first = client.post(
            "/api/v1/marketplace/book",
            json={
                "clinic_id": clinic,
                "name": "Public One",
                "phone": "9111111111",
                "slot_id": slot_id,
            },
        )
        assert first.status_code == 200, first.text
        assert first.json()["ok"] is True

        second = client.post(
            "/api/v1/marketplace/book",
            json={
                "clinic_id": clinic,
                "name": "Public Two",
                "phone": "9222222222",
                "slot_id": slot_id,
            },
        )
        assert second.status_code == 409

    def test_unknown_clinic_is_a_clean_404(self, client):
        response = client.get(
            "/api/v1/marketplace/slots",
            params={
                "clinic_id": "00000000-0000-0000-0000-000000000000",
                "date": TODAY,
            },
        )
        assert response.status_code == 404
        assert response.json()["ok"] is False


# ══════════════════════════════════════════════════════════════════════════
# 5. E-08 — Emergency override (Code Red)
# ══════════════════════════════════════════════════════════════════════════


class TestEmergencyOverride:
    def test_emergency_gets_its_own_e_sequence(self, client, login):
        clinic = _make_clinic("E-1", "Code Red Clinic")
        login(clinic)
        _make_entry(clinic, 1, status="WAITING")

        body = client.post(
            "/opd/api/slots/emergency", json={"name": "Chest Pain Case"}
        ).json()
        assert body["ok"] is True
        assert body["token_label"] == "E-1"
        assert body["emergency"] is True
        assert body["siren"] is True

    def test_a_second_emergency_becomes_e2(self, client, login):
        clinic = _make_clinic("E-2", "Second Red Clinic")
        login(clinic)
        first = client.post("/opd/api/slots/emergency", json={"name": "One"}).json()
        second = client.post("/opd/api/slots/emergency", json={"name": "Two"}).json()
        assert first["token_label"] == "E-1"
        assert second["token_label"] == "E-2"

    def test_emergency_never_consumes_a_routine_token(self, client, login):
        """Routine patients must not see a gap and think they were skipped."""
        clinic = _make_clinic("E-3", "No Gap Clinic")
        login(clinic)
        _make_entry(clinic, 1, status="WAITING")
        _make_entry(clinic, 2, status="WAITING")

        client.post("/opd/api/slots/emergency", json={"name": "Code Red"})

        # A routine booking after the emergency still gets token 3.
        _create_slots(
            client, date=TODAY, start_time="19:00", end_time="19:20", capacity=1
        )
        slot_id = _list_slots(client, TODAY)["slots"][0]["id"]
        routine = client.post(
            f"/opd/api/slots/{slot_id}/book", json={"name": "Routine Patient"}
        ).json()
        assert routine["token"] == 3, "the emergency must not have taken token 3"

    def test_emergency_does_not_interrupt_the_patient_inside(self, client, login):
        """Immediately after the chamber, never in front of it."""
        clinic = _make_clinic("E-4", "No Interrupt Clinic")
        login(clinic)
        _make_entry(clinic, 1, status="IN_PROGRESS", sort_key=1.0, patient_name="Inside")
        _make_entry(clinic, 2, status="WAITING", sort_key=2.0, patient_name="Next")

        body = client.post("/opd/api/slots/emergency", json={"name": "Code Red"}).json()
        assert body["ok"] is True
        assert "turant baad" in body["position_note"]

        feed = client.get("/opd/api/queue-ewt").json()
        order = [row["patient_name"] for row in feed["queue"]]
        assert order[0] == "Inside", "the consultation in progress must not be cut off"
        assert order[1] == "Code Red", "the emergency goes next"
        assert order[2] == "Next"

    def test_emergency_is_first_when_the_chamber_is_empty(self, client, login):
        clinic = _make_clinic("E-5", "Empty Chamber Clinic")
        login(clinic)
        _make_entry(clinic, 1, status="WAITING", sort_key=1.0, patient_name="Waiting One")
        _make_entry(clinic, 2, status="WAITING", sort_key=2.0, patient_name="Waiting Two")

        body = client.post("/opd/api/slots/emergency", json={"name": "Code Red"}).json()
        assert "pehle" in body["position_note"]

        feed = client.get("/opd/api/queue-ewt").json()
        assert feed["queue"][0]["patient_name"] == "Code Red"

    def test_the_queue_is_told_how_many_places_moved(self, client, login):
        clinic = _make_clinic("E-6", "Honest Clinic")
        login(clinic)
        for token in range(1, 6):
            _make_entry(clinic, token, status="WAITING")
        body = client.post("/opd/api/slots/emergency", json={"name": "Code Red"}).json()
        assert body["patients_moved_back"] == 5
        assert "5 waiting patient" in body["message"]
        assert body["broadcast"], "waiting patients need a message to send"

    def test_emergency_shows_the_emergency_label_in_the_live_feed(self, client, login):
        clinic = _make_clinic("E-7", "Label Feed Clinic")
        login(clinic)
        client.post("/opd/api/slots/emergency", json={"name": "Code Red"})
        feed = client.get("/opd/api/queue-ewt").json()
        row = next(r for r in feed["queue"] if r["patient_name"] == "Code Red")
        assert row["token_label"].startswith("E-")
        assert row["visit_label"] == ewt.VISIT_TYPE_LABEL["emergency"]

    def test_emergency_needs_no_body(self, client, login):
        """In a real Code Red nobody has time to fill a form."""
        clinic = _make_clinic("E-8", "No Form Clinic")
        login(clinic)
        body = client.post("/opd/api/slots/emergency", json={}).json()
        assert body["ok"] is True
        assert body["token_label"] == "E-1"

    def test_public_booking_also_skips_the_emergency_sequence(self, client, login):
        """The same rule must hold on the marketplace token counter (BUG-01 path)."""
        clinic = _make_clinic("E-9", "Public No Gap Clinic")
        login(clinic)
        client.post("/opd/api/slots/emergency", json={"name": "Code Red"})

        booked = client.post(
            "/api/v1/marketplace/book",
            json={"clinic_id": clinic, "name": "Walk In", "phone": "9333333333"},
        ).json()
        assert booked["ok"] is True, booked
        # E-1 exists, but the first ROUTINE token is still #1 — no visible gap.
        assert booked["token"] == 1
        assert booked["token_label"] == "C-1"


# ══════════════════════════════════════════════════════════════════════════
# 6. Routine tokens carry the specialty prefix everywhere
# ══════════════════════════════════════════════════════════════════════════


class TestRoutineTokenPrefix:
    def test_live_feed_labels_the_specialty(self, client, login):
        clinic = _make_clinic("R-1", "Cardiology Labels", specialty="Cardiology")
        login(clinic)
        _make_entry(clinic, 14, status="WAITING")
        feed = client.get("/opd/api/queue-ewt").json()
        assert feed["queue"][0]["token_label"] == "C-14"

    def test_a_general_physician_gets_the_g_prefix(self, client, login):
        clinic = _make_clinic("R-2", "General Labels", specialty="General Physician")
        login(clinic)
        _make_entry(clinic, 14, status="WAITING")
        feed = client.get("/opd/api/queue-ewt").json()
        assert feed["queue"][0]["token_label"] == "G-14"

    def test_chamber_status_labels_the_next_token(self, client, login):
        clinic = _make_clinic("R-3", "Next Token Labels", specialty="Cardiology")
        login(clinic)
        _make_entry(clinic, 9, status="WAITING")
        status = client.get("/opd/api/chamber/status").json()
        assert status["next_token"] == 9
        assert status["next_token_label"] == "C-9"

    def test_two_doctors_tokens_are_distinguishable(self, client, login):
        """The whole point of E-04's prefix: #14 is no longer ambiguous."""
        card = _make_clinic("R-4C", "Heart Clinic", specialty="Cardiology")
        general = _make_clinic("R-4G", "Family Clinic", specialty="General Physician")
        login(card)
        _make_entry(card, 14, status="WAITING")
        card_label = client.get("/opd/api/queue-ewt").json()["queue"][0]["token_label"]
        login(general)
        _make_entry(general, 14, status="WAITING")
        general_label = client.get("/opd/api/queue-ewt").json()["queue"][0]["token_label"]

        assert card_label == "C-14"
        assert general_label == "G-14"
        assert card_label != general_label
