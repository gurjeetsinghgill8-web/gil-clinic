"""Cross-clinic referral tests (master blueprint BLOCK 7 · F-06).

Run:  python -m pytest tests/test_referrals.py -q

What matters here, and why each test exists:

  * **Nothing enters a queue until the receiving clinic accepts.** A referral
    that silently pushed a patient into another clinic's queue would be a
    tenancy and trust failure, not a feature.
  * **The slip cannot be forged, replayed, or forwarded into two tokens.**
  * **Only the addressed clinic can act on it.** Guessing an id is not enough.
  * Accepting creates a REAL token — the same queue every walk-in joins — and
    places the patient at the back by default, because a referral is a real
    patient but not an emergency.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_TEST_DB = ROOT / "test_referrals.db"
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
from src.infrastructure.clinic.models.clinic_model import ClinicModel  # noqa: E402
from src.infrastructure.clinic.models.referral_model import (  # noqa: E402
    STATUS_ACCEPTED,
    STATUS_DECLINED,
    STATUS_PENDING,
    ReferralModel,
)
from src.infrastructure.queue.models.queue_entry_model import QueueEntryModel  # noqa: E402
from src.shared.infrastructure.database import async_session_factory  # noqa: E402

main_v2.Base.metadata.create_all(bind=main_v2.engine)
main_v2._migrate_sqlite_columns()


def _run(coro):
    import asyncio

    return asyncio.run(coro)


def _make_clinic(code: str, name: str, specialty: str = "Cardiology") -> str:
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

    return _run(_insert())


def _make_waiting_entry(clinic_id: str, token: int) -> str:
    from src.shared.domain.base_entity import uuid7

    entry_id = uuid7()
    now = datetime.now(timezone.utc)

    async def _insert():
        async with async_session_factory() as session:
            session.add(
                QueueEntryModel(
                    id=entry_id,
                    clinic_id=clinic_id,
                    doctor_id="chief",
                    visit_id=f"VIS-REF-{token}",
                    patient_id=f"REF-W-{token}",
                    patient_uuid=str(uuid7()),
                    patient_name=f"Walking In {token}",
                    service_code="OPD",
                    token_number=token,
                    department="OPD",
                    room="OPD Room",
                    status="WAITING",
                    priority=0,
                    display_order=0,
                    sort_key=float(token),
                    visit_type="followup",
                    complexity_weight=1,
                    created_by="test",
                    updated_by="test",
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.commit()

    _run(_insert())
    return str(entry_id)


@pytest.fixture
def login(monkeypatch):
    """Log a chief doctor in at a specific clinic (tenancy matters here)."""
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
    return TestClient(main_v2.app)


def _create(client, to_clinic_id, **over):
    body = {
        "to_clinic_id": to_clinic_id,
        "patient_name": "Referred Patient",
        "patient_phone": "9700000001",
        "reason": "Echo + cardiology review chahiye",
    }
    body.update(over)
    response = client.post("/opd/api/referrals", json=body)
    return response


# ══════════════════════════════════════════════════════════════════════════
# 1. Creating a slip
# ══════════════════════════════════════════════════════════════════════════


class TestCreateReferral:
    def test_a_slip_is_created_with_a_signed_url(self, client, login):
        sender = _make_clinic("RF-A", "Sender Clinic")
        receiver = _make_clinic("RF-B", "Receiver Clinic")
        login(sender)

        response = _create(client, receiver)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["ok"] is True
        assert "/r/" in body["slip_url"]
        assert body["urgency"] == "ROUTINE"
        assert body["to_clinic_name"] == "Receiver Clinic"

    def test_urgency_is_carried_and_labelled(self, client, login):
        sender = _make_clinic("RF-C", "Urgent Sender")
        receiver = _make_clinic("RF-D", "Urgent Receiver")
        login(sender)
        body = _create(client, receiver, urgency="URGENT").json()
        assert body["urgency"] == "URGENT"
        assert "Turant" in body["urgency_label"]

    def test_an_unknown_urgency_degrades_to_routine(self, client, login):
        sender = _make_clinic("RF-E", "Bad Urgency Sender")
        receiver = _make_clinic("RF-F", "Bad Urgency Receiver")
        login(sender)
        body = _create(client, receiver, urgency="SUPER-DUPER-URGENT").json()
        assert body["urgency"] == "ROUTINE", "never invent a priority level"

    def test_a_clinic_cannot_refer_to_itself(self, client, login):
        clinic = _make_clinic("RF-G", "Self Referral Clinic")
        login(clinic)
        response = _create(client, clinic)
        assert response.status_code == 400
        assert "Apni hi clinic" in response.json()["error"]

    def test_a_patient_is_required(self, client, login):
        sender = _make_clinic("RF-H", "No Patient Sender")
        receiver = _make_clinic("RF-I", "No Patient Receiver")
        login(sender)
        response = client.post(
            "/opd/api/referrals",
            json={"to_clinic_id": receiver, "reason": "x"},
        )
        assert response.status_code == 400

    def test_an_unknown_receiver_is_a_clean_404(self, client, login):
        login(_make_clinic("RF-J", "Bad Receiver Sender"))
        response = _create(client, "00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404


# ══════════════════════════════════════════════════════════════════════════
# 2. The receiving clinic's inbox
# ══════════════════════════════════════════════════════════════════════════


class TestInbox:
    def test_a_referral_appears_only_in_the_receivers_inbox(self, client, login):
        sender = _make_clinic("RF-K", "Inbox Sender")
        receiver = _make_clinic("RF-L", "Inbox Receiver")
        bystander = _make_clinic("RF-M", "Inbox Bystander")

        login(sender)
        _create(client, receiver)

        login(receiver)
        inbox = client.get("/opd/api/referrals").json()
        assert inbox["total"] == 1
        assert inbox["pending"] == 1
        assert inbox["referrals"][0]["from_clinic_name"] == "Inbox Sender"

        # A third clinic must see nothing of it.
        login(bystander)
        other = client.get("/opd/api/referrals").json()
        assert other["total"] == 0

    def test_urgent_referrals_sort_first(self, client, login):
        sender = _make_clinic("RF-N", "Sort Sender")
        receiver = _make_clinic("RF-O", "Sort Receiver")
        login(sender)
        _create(client, receiver, patient_name="Routine One", urgency="ROUTINE")
        _create(client, receiver, patient_name="Urgent One", urgency="URGENT")
        _create(client, receiver, patient_name="Soon One", urgency="SOON")

        login(receiver)
        names = [r["patient_name"] for r in client.get("/opd/api/referrals").json()["referrals"]]
        assert names.index("Urgent One") < names.index("Soon One") < names.index("Routine One")

    def test_the_inbox_carries_no_unnecessary_identity(self, client, login):
        """The slip shows what the sender shared — not the patient's chart."""
        sender = _make_clinic("RF-P", "Privacy Sender")
        receiver = _make_clinic("RF-Q", "Privacy Receiver")
        login(sender)
        _create(client, receiver)

        login(receiver)
        row = client.get("/opd/api/referrals").json()["referrals"][0]
        for field in ("patient_name", "reason", "urgency", "slip_url", "created_at"):
            assert field in row
        # No clinical history, no prescriptions, no visit list.
        for forbidden in ("prescriptions", "medical_history", "visits", "diagnoses"):
            assert forbidden not in row


# ══════════════════════════════════════════════════════════════════════════
# 3. Accepting — the only path into a queue
# ══════════════════════════════════════════════════════════════════════════


class TestAccept:
    def _referral_id(self, client, login, sender, receiver):
        login(sender)
        _create(client, receiver, patient_name="Accept Patient")
        login(receiver)
        return client.get("/opd/api/referrals").json()["referrals"][0]["id"]

    def test_nothing_enters_the_queue_before_acceptance(self, client, login):
        """The core tenancy guarantee."""
        sender = _make_clinic("RF-R", "Tenancy Sender")
        receiver = _make_clinic("RF-S", "Tenancy Receiver")
        self._referral_id(client, login, sender, receiver)

        async def _count():
            import sqlalchemy as sa

            async with async_session_factory() as session:
                row = await session.execute(
                    sa.select(sa.func.count(QueueEntryModel.id)).where(
                        QueueEntryModel.clinic_id == receiver
                    )
                )
                return int(row.scalar() or 0)

        assert _run(_count()) == 0, "a pending referral must not create a token"

    def test_accepting_creates_a_real_token(self, client, login):
        sender = _make_clinic("RF-T", "Accept Sender")
        receiver = _make_clinic("RF-U", "Accept Receiver")
        referral_id = self._referral_id(client, login, sender, receiver)

        body = client.post(f"/opd/api/referrals/{referral_id}/accept", json={}).json()
        assert body["ok"] is True
        assert body["token"] >= 1
        assert body["token_label"]

        async def _read():
            import sqlalchemy as sa

            async with async_session_factory() as session:
                row = await session.execute(
                    sa.select(QueueEntryModel).where(
                        QueueEntryModel.clinic_id == receiver
                    )
                )
                return row.scalars().all()

        entries = _run(_read())
        assert len(entries) == 1
        assert entries[0].patient_name == "Accept Patient"
        assert entries[0].created_by == "referral"

    def test_a_referral_cannot_be_accepted_twice(self, client, login):
        """A forwarded link must not mint two tokens."""
        sender = _make_clinic("RF-V", "Double Sender")
        receiver = _make_clinic("RF-W", "Double Receiver")
        referral_id = self._referral_id(client, login, sender, receiver)

        first = client.post(f"/opd/api/referrals/{referral_id}/accept", json={})
        assert first.status_code == 200

        second = client.post(f"/opd/api/referrals/{referral_id}/accept", json={})
        assert second.status_code == 409
        assert "pehle hi accept" in second.json()["error"]

    def test_a_referred_patient_goes_to_the_back_of_the_line(self, client, login):
        """A referral is a real patient, not an emergency — nobody is jumped."""
        sender = _make_clinic("RF-X", "Fair Sender")
        receiver = _make_clinic("RF-Y", "Fair Receiver")
        _make_waiting_entry(receiver, 1)
        _make_waiting_entry(receiver, 2)
        referral_id = self._referral_id(client, login, sender, receiver)

        body = client.post(f"/opd/api/referrals/{referral_id}/accept", json={}).json()
        assert body["patients_in_queue"] == 3
        assert "aakhir" in body["position_note"]

        feed = client.get("/opd/api/queue-ewt").json()
        assert feed["queue"][-1]["patient_name"] == "Accept Patient"

    def test_reception_can_put_an_urgent_referral_at_the_front(self, client, login):
        sender = _make_clinic("RF-Z", "Front Sender")
        receiver = _make_clinic("RF-AA", "Front Receiver")
        _make_waiting_entry(receiver, 1)
        referral_id = self._referral_id(client, login, sender, receiver)

        body = client.post(
            f"/opd/api/referrals/{referral_id}/accept", json={"at_front": True}
        ).json()
        assert "front" in body["position_note"].lower()

        feed = client.get("/opd/api/queue-ewt").json()
        assert feed["queue"][0]["patient_name"] == "Accept Patient"

    def test_a_different_clinic_cannot_accept(self, client, login):
        """Guessing the referral id must not be enough."""
        sender = _make_clinic("RF-AB", "Guard Sender")
        receiver = _make_clinic("RF-AC", "Guard Receiver")
        intruder = _make_clinic("RF-AD", "Guard Intruder")
        referral_id = self._referral_id(client, login, sender, receiver)

        login(intruder)
        response = client.post(f"/opd/api/referrals/{referral_id}/accept", json={})
        assert response.status_code == 403
        assert "aapki clinic" in response.json()["error"]

    def test_an_expired_slip_is_refused(self, client, login):
        sender = _make_clinic("RF-AE", "Expiry Sender")
        receiver = _make_clinic("RF-AF", "Expiry Receiver")
        referral_id = self._referral_id(client, login, sender, receiver)

        async def _expire():
            import sqlalchemy as sa

            async with async_session_factory() as session:
                row = await session.execute(
                    sa.select(ReferralModel).where(
                        ReferralModel.id == __import__("uuid").UUID(referral_id)
                    )
                )
                referral = row.scalars().first()
                referral.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
                await session.commit()

        _run(_expire())
        response = client.post(f"/opd/api/referrals/{referral_id}/accept", json={})
        assert response.status_code == 400
        assert "expire" in response.json()["error"]

    def test_an_unknown_referral_is_a_clean_404(self, client, login):
        login(_make_clinic("RF-AG", "Unknown Referral Clinic"))
        response = client.post(
            "/opd/api/referrals/00000000-0000-0000-0000-000000000000/accept",
            json={},
        )
        assert response.status_code == 404


class TestDecline:
    def test_declining_keeps_the_queue_untouched(self, client, login):
        sender = _make_clinic("RF-AH", "Decline Sender")
        receiver = _make_clinic("RF-AI", "Decline Receiver")
        login(sender)
        _create(client, receiver)
        login(receiver)
        referral_id = client.get("/opd/api/referrals").json()["referrals"][0]["id"]

        body = client.post(
            f"/opd/api/referrals/{referral_id}/decline", json={"reason": "No slot today"}
        ).json()
        assert body["ok"] is True

        async def _count():
            import sqlalchemy as sa

            async with async_session_factory() as session:
                row = await session.execute(
                    sa.select(sa.func.count(QueueEntryModel.id)).where(
                        QueueEntryModel.clinic_id == receiver
                    )
                )
                return int(row.scalar() or 0)

        assert _run(_count()) == 0

    def test_a_declined_referral_leaves_the_pending_inbox(self, client, login):
        sender = _make_clinic("RF-AJ", "Leave Sender")
        receiver = _make_clinic("RF-AK", "Leave Receiver")
        login(sender)
        _create(client, receiver)
        login(receiver)
        referral_id = client.get("/opd/api/referrals").json()["referrals"][0]["id"]
        client.post(f"/opd/api/referrals/{referral_id}/decline", json={})

        assert client.get("/opd/api/referrals").json()["total"] == 0
        assert client.get(
            "/opd/api/referrals", params={"include_closed": "true"}
        ).json()["total"] == 1

    def test_a_declined_referral_cannot_then_be_accepted(self, client, login):
        sender = _make_clinic("RF-AL", "Late Sender")
        receiver = _make_clinic("RF-AM", "Late Receiver")
        login(sender)
        _create(client, receiver)
        login(receiver)
        referral_id = client.get("/opd/api/referrals").json()["referrals"][0]["id"]
        client.post(f"/opd/api/referrals/{referral_id}/decline", json={})

        response = client.post(f"/opd/api/referrals/{referral_id}/accept", json={})
        assert response.status_code == 400


# ══════════════════════════════════════════════════════════════════════════
# 4. The public slip page
# ══════════════════════════════════════════════════════════════════════════


class TestSlipPage:
    def test_the_slip_page_renders_for_a_valid_token(self, client, login):
        sender = _make_clinic("RF-AN", "Page Sender")
        receiver = _make_clinic("RF-AO", "Page Receiver")
        login(sender)
        slip_url = _create(client, receiver, patient_name="Page Patient").json()["slip_url"]
        path = "/r/" + slip_url.rsplit("/r/", 1)[1]

        response = client.get(path)
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Page Patient" in response.text
        assert "Page Sender" in response.text
        assert "Page Receiver" in response.text

    def test_a_tampered_token_is_refused(self, client, login):
        sender = _make_clinic("RF-AP", "Tamper Sender")
        receiver = _make_clinic("RF-AQ", "Tamper Receiver")
        login(sender)
        slip_url = _create(client, receiver).json()["slip_url"]
        token = slip_url.rsplit("/r/", 1)[1]
        tampered = token[:-4] + ("aaaa" if not token.endswith("aaaa") else "bbbb")

        response = client.get("/r/" + tampered)
        assert response.status_code == 404

    def test_a_garbage_token_is_refused(self, client):
        assert client.get("/r/not-a-token").status_code == 404

    def test_opening_the_slip_grants_nothing(self, client, login):
        """Viewing is read-only: the queue must stay empty."""
        sender = _make_clinic("RF-AR", "View Sender")
        receiver = _make_clinic("RF-AS", "View Receiver")
        login(sender)
        slip_url = _create(client, receiver).json()["slip_url"]
        token = slip_url.rsplit("/r/", 1)[1]

        for _ in range(3):
            client.get("/r/" + token)

        async def _state():
            import uuid as _uuid

            import sqlalchemy as sa

            async with async_session_factory() as session:
                row = await session.execute(
                    sa.select(ReferralModel).where(ReferralModel.to_clinic_id == receiver)
                )
                referral = row.scalars().first()
                entries = await session.execute(
                    sa.select(sa.func.count(QueueEntryModel.id)).where(
                        QueueEntryModel.clinic_id == receiver
                    )
                )
                return referral.status, referral.viewed_count, int(entries.scalar() or 0)

        status, views, entry_count = _run(_state())
        assert status == STATUS_PENDING, "viewing must not change the state"
        assert views == 3, "views are counted for the sender's benefit"
        assert entry_count == 0


# ══════════════════════════════════════════════════════════════════════════
# 5. Signed-token unit behaviour
# ══════════════════════════════════════════════════════════════════════════


class TestSlipToken:
    def test_round_trip(self):
        from src.presentation.referral.routes.referral_routes import (
            decode_slip_token,
            make_slip_token,
        )

        rid = "11111111-2222-3333-4444-555555555555"
        assert decode_slip_token(make_slip_token(rid)) == rid

    def test_a_foreign_token_is_rejected(self):
        from src.presentation.referral.routes.referral_routes import decode_slip_token

        assert decode_slip_token("totally-made-up") is None
        assert decode_slip_token("") is None

    def test_a_tracking_token_cannot_be_used_as_a_slip(self):
        """Different salt per token family — they must not be interchangeable."""
        from src.presentation.referral.routes.referral_routes import decode_slip_token
        from src.presentation.staff.routes.staff_routes import make_tracking_token

        assert decode_slip_token(make_tracking_token("CQ-20261003-001")) is None

    def test_an_expired_slip_is_rejected(self):
        from src.presentation.referral.routes.referral_routes import (
            decode_slip_token,
            make_slip_token,
        )

        token = make_slip_token("11111111-2222-3333-4444-555555555555")
        assert decode_slip_token(token, max_age=-1) is None
