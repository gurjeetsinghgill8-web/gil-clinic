"""Growth tests (master blueprint BLOCK 4 · GRW-01 … GRW-04).

Run:  python -m pytest tests/test_growth.py -q

Groups:

  1. **GRW-01** — health card access log + revocation. A patient right to know
     who read their record, and to withdraw a share — both need a record, and
     neither can be reconstructed after the fact.
  2. **GRW-02** — the invite pipeline. The marketplace's "📢 Invite" button used
     to be a toast; every patient ask was thrown away at the moment it was made.
  3. **GRW-03** — city landing pages render real data, and only for real cities.
  4. **GRW-04** — the Family Health Locker, reachable only from an already
     verified portal session.
"""

from __future__ import annotations

import hashlib
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_TEST_DB = ROOT / "test_growth.db"
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
from src.infrastructure.clinic.models.lead_model import (  # noqa: E402
    STATUS_CONTACTED,
    STATUS_INTERESTED,
    STATUS_NEW,
    ClinicLeadModel,
)
from src.infrastructure.opd.models.patient_portal_models import (  # noqa: E402
    HealthCardAccessModel,
    HealthCardModel,
    PatientPortalLinkModel,
)
from src.infrastructure.patient.models.patient_model import PatientModel  # noqa: E402
from src.shared.infrastructure.database import async_session_factory  # noqa: E402

main_v2.Base.metadata.create_all(bind=main_v2.engine)
main_v2._migrate_sqlite_columns()

# Stamped in the past so these rows are never the "most recent queue entry" —
# several other test modules rely on that production fallback.
NOW = datetime.now(timezone.utc) - timedelta(hours=2)


def _run(coro):
    import asyncio

    return asyncio.run(coro)


def _make_clinic(code: str, name: str, city: str = "Jodhpur",
                 specialty: str = "Cardiology") -> str:
    from src.shared.domain.base_entity import uuid7

    clinic_id = uuid7()

    async def _insert():
        async with async_session_factory() as session:
            session.add(
                ClinicModel(
                    id=clinic_id, clinic_name=name, clinic_code=code,
                    doctor_name=f"Dr {name}", specialty=specialty,
                    city=city, state="Rajasthan", address=f"{city} main road",
                    open_time="00:01", close_time="23:58",
                    is_license_active=True, is_active=True,
                )
            )
            await session.commit()
        return str(clinic_id)

    return _run(_insert())


def _make_patient(patient_id: str, name: str, phone: str,
                  age: int = 30) -> str:
    """Insert a patient row and return the patient_id."""
    from src.shared.domain.base_entity import uuid7

    async def _insert():
        async with async_session_factory() as session:
            session.add(
                PatientModel(
                    id=uuid7(), patient_id=patient_id, name=name, age=age,
                    gender="Male", date_of_birth="",
                    phone=phone,
                    phone_hash=hashlib.sha256(phone.encode()).hexdigest(),
                    address="", status="active", total_visits=1,
                    version=1, created_at=NOW, updated_at=NOW,
                )
            )
            await session.commit()

    _run(_insert())
    return patient_id


def _make_card(uid: str, patient_id: str, name: str) -> None:
    async def _insert():
        async with async_session_factory() as session:
            session.add(
                HealthCardModel(
                    uid=uid, patient_id=patient_id, patient_name=name,
                    active=1, view_count=0,
                    expires_at=datetime.now(timezone.utc) + timedelta(days=30),
                )
            )
            await session.commit()

    _run(_insert())


@pytest.fixture
def login(monkeypatch):
    from src.presentation.opd.routes import opd_routes

    def _login(clinic_id: str = ""):
        monkeypatch.setattr(
            opd_routes,
            "_require_opd_session",
            lambda request: {
                "role": "chief", "doctor_id": "chief", "name": "Dr Test",
                "clinic_id": clinic_id, "lic_info": {},
            },
        )
        return "chief"

    return _login


@pytest.fixture(scope="module")
def client():
    return TestClient(main_v2.app)


# ══════════════════════════════════════════════════════════════════════════
# 1. GRW-01 — health card access log + revoke
# ══════════════════════════════════════════════════════════════════════════


class TestHealthCardAccessLog:
    def test_a_view_is_recorded(self, client):
        uid = "g01-view-token"
        _make_patient("CQ-G01-A", "Log Patient", "9600000001")
        _make_card(uid, "CQ-G01-A", "Log Patient")

        response = client.get(f"/card/{uid}")
        assert response.status_code == 200

        async def _count():
            import sqlalchemy as sa

            async with async_session_factory() as session:
                row = await session.execute(
                    sa.select(sa.func.count(HealthCardAccessModel.id)).where(
                        HealthCardAccessModel.uid == uid
                    )
                )
                return int(row.scalar() or 0)

        assert _run(_count()) == 1, "the view must leave a record"

    def test_repeat_views_are_all_recorded(self, client):
        uid = "g01-repeat-token"
        _make_patient("CQ-G01-B", "Repeat Patient", "9600000002")
        _make_card(uid, "CQ-G01-B", "Repeat Patient")
        for _ in range(3):
            client.get(f"/card/{uid}")

        async def _views():
            import sqlalchemy as sa

            async with async_session_factory() as session:
                row = await session.execute(
                    sa.select(sa.func.count(HealthCardAccessModel.id)).where(
                        HealthCardAccessModel.uid == uid
                    )
                )
                return int(row.scalar() or 0)

        assert _run(_views()) == 3

    def test_a_denied_attempt_is_recorded_too(self, client):
        """A card being probed is exactly the pattern worth noticing early."""
        response = client.get("/card/does-not-exist-token")
        assert response.status_code == 404

        async def _denied():
            import sqlalchemy as sa

            async with async_session_factory() as session:
                row = await session.execute(
                    sa.select(HealthCardAccessModel).where(
                        HealthCardAccessModel.uid == "does-not-exist-token"
                    )
                )
                return row.scalars().all()

        rows = _run(_denied())
        assert len(rows) == 1
        assert rows[0].outcome == "denied"
        assert rows[0].denial_reason

    def test_the_log_stores_no_clinical_content(self, client):
        uid = "g01-privacy-token"
        _make_patient("CQ-G01-C", "Privacy Patient", "9600000003")
        _make_card(uid, "CQ-G01-C", "Privacy Patient")
        client.get(f"/card/{uid}")

        async def _row():
            import sqlalchemy as sa

            async with async_session_factory() as session:
                row = await session.execute(
                    sa.select(HealthCardAccessModel).where(
                        HealthCardAccessModel.uid == uid
                    )
                )
                return row.scalars().first()

        record = _run(_row())
        # It is an access log, not a second copy of the chart.
        assert not hasattr(record, "readings")
        assert not hasattr(record, "prescriptions")
        assert record.ip_hash and len(record.ip_hash) == 32, "IP is hashed, not stored"

    def test_the_access_report_needs_a_staff_session(self, client):
        # The guard redirects an anonymous caller to the login page, so the
        # redirect must NOT be followed — otherwise a 200 login page would read
        # as a successful API response.
        response = client.get(
            "/opd/api/health-card/access", params={"uid": "x"},
            follow_redirects=False,
        )
        assert response.status_code in (301, 302, 303, 307, 401, 403), response.status_code

    def test_the_access_report_summarises_views(self, client, login):
        uid = "g01-report-token"
        _make_patient("CQ-G01-D", "Report Patient", "9600000004")
        _make_card(uid, "CQ-G01-D", "Report Patient")
        client.get(f"/card/{uid}")
        client.get(f"/card/{uid}")

        login()
        body = client.get("/opd/api/health-card/access", params={"uid": uid}).json()
        assert body["ok"] is True
        assert body["summary"]["total_views"] == 2
        assert body["summary"]["granted"] == 2
        assert body["access"]
        assert "clinical" in body["note"].lower() or "content" in body["note"].lower()


class TestHealthCardRevoke:
    def test_revoking_makes_the_link_stop_working(self, client, login):
        uid = "g01-revoke-token"
        _make_patient("CQ-G01-E", "Revoke Patient", "9600000005")
        _make_card(uid, "CQ-G01-E", "Revoke Patient")
        assert client.get(f"/card/{uid}").status_code == 200

        login()
        body = client.post(
            "/opd/api/health-card/revoke",
            json={"uid": uid, "reason": "patient request"},
        ).json()
        assert body["ok"] is True
        assert body["revoked"] == 1

        # The old link must now fail for everyone.
        assert client.get(f"/card/{uid}").status_code == 404

    def test_revocation_records_who_when_and_why(self, client, login):
        uid = "g01-audit-token"
        _make_patient("CQ-G01-F", "Audit Patient", "9600000006")
        _make_card(uid, "CQ-G01-F", "Audit Patient")

        login()
        client.post(
            "/opd/api/health-card/revoke",
            json={"uid": uid, "reason": "patient withdrew consent"},
        )

        async def _card():
            import sqlalchemy as sa

            async with async_session_factory() as session:
                row = await session.execute(
                    sa.select(HealthCardModel).where(HealthCardModel.uid == uid)
                )
                return row.scalars().first()

        card = _run(_card())
        assert card.active == 0
        assert card.revoked_at is not None, "a withdrawal with no timestamp is not auditable"
        assert card.revoked_by
        assert "consent" in card.revoked_reason

    def test_revoking_twice_is_a_clean_no_op_not_a_crash(self, client, login):
        uid = "g01-double-token"
        _make_patient("CQ-G01-G", "Double Patient", "9600000007")
        _make_card(uid, "CQ-G01-G", "Double Patient")

        login()
        first = client.post("/opd/api/health-card/revoke", json={"uid": uid})
        assert first.status_code == 200

        second = client.post("/opd/api/health-card/revoke", json={"uid": uid})
        # A patient asking twice must not see a failure.
        assert second.status_code == 404
        assert "pehle hi" in second.json()["error"]

    def test_revoke_can_target_a_patient_not_just_a_uid(self, client, login):
        uid = "g01-patient-token"
        _make_patient("CQ-G01-H", "By Patient Id", "9600000008")
        _make_card(uid, "CQ-G01-H", "By Patient Id")

        login()
        body = client.post(
            "/opd/api/health-card/revoke", json={"patient_id": "CQ-G01-H"}
        ).json()
        assert body["ok"] is True
        assert "CQ-G01-H" in body["patient_ids"]

    def test_revoke_needs_something_to_revoke(self, client, login):
        login()
        response = client.post("/opd/api/health-card/revoke", json={})
        assert response.status_code == 400

    def test_unknown_card_is_a_clean_404(self, client, login):
        login()
        response = client.post(
            "/opd/api/health-card/revoke", json={"uid": "never-existed"}
        )
        assert response.status_code == 404


# ══════════════════════════════════════════════════════════════════════════
# 2. GRW-02 — the invite pipeline
# ══════════════════════════════════════════════════════════════════════════


class TestInvitePipeline:
    def test_an_invite_creates_a_lead(self, client):
        clinic = _make_clinic("GR-A", "Lead Clinic", city="Udaipur")
        body = client.post(
            "/api/v1/marketplace/invite",
            json={"clinic_id": clinic, "problem": "seene me dard"},
        ).json()
        assert body["ok"] is True
        assert body["request_count"] == 1
        assert "Lead Clinic" in body["message"]

    def test_repeat_asks_increment_rather_than_duplicate(self, client):
        """How many patients asked is the number that decides outreach."""
        clinic = _make_clinic("GR-B", "Popular Clinic", city="Ajmer")
        for _ in range(3):
            client.post("/api/v1/marketplace/invite", json={"clinic_id": clinic})

        async def _leads():
            import sqlalchemy as sa

            async with async_session_factory() as session:
                row = await session.execute(
                    sa.select(ClinicLeadModel).where(ClinicLeadModel.clinic_id == clinic)
                )
                return row.scalars().all()

        leads = _run(_leads())
        assert len(leads) == 1, "one clinic, one lead"
        assert leads[0].request_count == 3

    def test_demand_notes_are_collected_and_deduplicated(self, client):
        clinic = _make_clinic("GR-C", "Note Clinic", city="Kota")
        for problem in ("seene me dard", "ECG chahiye", "seene me dard"):
            client.post(
                "/api/v1/marketplace/invite",
                json={"clinic_id": clinic, "problem": problem},
            )

        async def _lead():
            import sqlalchemy as sa

            async with async_session_factory() as session:
                row = await session.execute(
                    sa.select(ClinicLeadModel).where(ClinicLeadModel.clinic_id == clinic)
                )
                return row.scalars().first()

        lead = _run(_lead())
        notes = [n for n in lead.demand_notes.split("|") if n]
        assert notes == ["seene me dard", "ECG chahiye"], "no repeats"

    def test_a_lead_can_be_created_without_a_clinic_id(self, client):
        """A patient may name a clinic the network does not list yet."""
        body = client.post(
            "/api/v1/marketplace/invite",
            json={"clinic_name": "Some New Clinic", "city": "Bikaner"},
        ).json()
        assert body["ok"] is True

    def test_an_empty_invite_is_refused(self, client):
        response = client.post("/api/v1/marketplace/invite", json={})
        assert response.status_code == 400

    def test_the_pipeline_requires_staff_auth(self, client):
        # See the note above: do not follow the redirect to the login page.
        response = client.get("/opd/api/leads", follow_redirects=False)
        assert response.status_code in (301, 302, 303, 307, 401, 403), response.status_code

    def test_leads_sort_by_demand(self, client, login):
        quiet = _make_clinic("GR-D", "Quiet Clinic", city="Alwar")
        loud = _make_clinic("GR-E", "Loud Clinic", city="Alwar")
        client.post("/api/v1/marketplace/invite", json={"clinic_id": quiet})
        for _ in range(4):
            client.post("/api/v1/marketplace/invite", json={"clinic_id": loud})

        login()
        body = client.get("/opd/api/leads", params={"limit": 200}).json()
        names = [lead["clinic_name"] for lead in body["leads"]]
        assert names.index("Loud Clinic") < names.index("Quiet Clinic")
        assert body["by_status"][STATUS_NEW] >= 2

    def test_a_lead_moves_along_the_pipeline(self, client, login):
        clinic = _make_clinic("GR-F", "Pipeline Clinic", city="Bhilwara")
        client.post("/api/v1/marketplace/invite", json={"clinic_id": clinic})

        login()
        lead = next(
            x for x in client.get("/opd/api/leads", params={"limit": 200}).json()["leads"]
            if x["clinic_id"] == clinic
        )
        body = client.post(
            f"/opd/api/leads/{lead['id']}",
            json={"status": STATUS_INTERESTED, "note": "Wants demo on Monday"},
        ).json()
        assert body["ok"] is True
        assert body["status"] == STATUS_INTERESTED

        async def _lead():
            import sqlalchemy as sa
            import uuid as _uuid

            async with async_session_factory() as session:
                row = await session.execute(
                    sa.select(ClinicLeadModel).where(ClinicLeadModel.id == _uuid.UUID(lead["id"]))
                )
                return row.scalars().first()

        saved = _run(_lead())
        assert saved.status == STATUS_INTERESTED
        assert saved.last_contacted_at is not None
        assert "Monday" in saved.note

    def test_an_invalid_pipeline_stage_is_refused(self, client, login):
        clinic = _make_clinic("GR-G", "Bad Stage Clinic", city="Sikar")
        client.post("/api/v1/marketplace/invite", json={"clinic_id": clinic})
        login()
        lead = next(
            x for x in client.get("/opd/api/leads", params={"limit": 200}).json()["leads"]
            if x["clinic_id"] == clinic
        )
        response = client.post(
            f"/opd/api/leads/{lead['id']}", json={"status": "SUPER_INTERESTED"}
        )
        assert response.status_code == 400

    def test_renewed_demand_resurfaces_a_declined_lead(self, client, login):
        """Demand changed, so the outreach decision may have changed too."""
        clinic = _make_clinic("GR-H", "Second Chance Clinic", city="Pali")
        client.post("/api/v1/marketplace/invite", json={"clinic_id": clinic})

        login()
        lead = next(
            x for x in client.get("/opd/api/leads", params={"limit": 200}).json()["leads"]
            if x["clinic_id"] == clinic
        )
        client.post(f"/opd/api/leads/{lead['id']}", json={"status": "DECLINED"})

        # Three more patients ask → the lead comes back to CONTACTED.
        for _ in range(3):
            client.post("/api/v1/marketplace/invite", json={"clinic_id": clinic})

        async def _status():
            import sqlalchemy as sa

            async with async_session_factory() as session:
                row = await session.execute(
                    sa.select(ClinicLeadModel).where(ClinicLeadModel.clinic_id == clinic)
                )
                return row.scalars().first().status

        assert _run(_status()) == STATUS_CONTACTED


# ══════════════════════════════════════════════════════════════════════════
# 3. GRW-03 — city landing pages
# ══════════════════════════════════════════════════════════════════════════


class TestCityPages:
    def test_a_real_city_renders_real_clinics(self, client):
        _make_clinic("CTY-A", "City Page Clinic", city="Bhopal")
        response = client.get("/doctors/bhopal")
        assert response.status_code == 200, response.text
        assert "text/html" in response.headers["content-type"]
        assert "City Page Clinic" in response.text
        assert "Bhopal" in response.text

    def test_the_page_is_indexable_and_has_metadata(self, client):
        _make_clinic("CTY-B", "SEO Clinic", city="Indore")
        html = client.get("/doctors/indore").text
        assert "<title>" in html
        assert 'name="description"' in html
        assert 'rel="canonical"' in html
        assert "noindex" not in html

    def test_a_hyphenated_city_resolves(self, client):
        _make_clinic("CTY-C", "Hyphen Clinic", city="new delhi")
        response = client.get("/doctors/new-delhi")
        assert response.status_code == 200, response.text
        assert "Hyphen Clinic" in response.text

    def test_an_unknown_city_is_a_helpful_404_not_a_blank_page(self, client):
        response = client.get("/doctors/atlantis")
        assert response.status_code == 404
        # A dead end for a crawler AND a patient is the worst outcome.
        assert "find-doctor" in response.text
        assert "noindex" in response.text

    def test_the_page_shows_availability_not_a_static_label(self, client):
        _make_clinic("CTY-D", "Availability Clinic", city="Nagpur")
        html = client.get("/doctors/nagpur").text
        # Either open or closed wording — but a real state, from real hours.
        assert ("Khula" in html or "Band" in html or "Chhutti" in html
                or "Call" in html or "Jaldi" in html)

    def test_specialty_links_are_real_not_decorative(self, client):
        _make_clinic("CTY-E", "Spec Clinic", city="Surat", specialty="Orthopedics")
        html = client.get("/doctors/surat").text
        # Each chip must carry a specialty that exists in that city, so the
        # link lands on results rather than an empty page.
        assert "Orthopedics (1)" in html


# ══════════════════════════════════════════════════════════════════════════
# 4. GRW-04 — Family Health Locker
# ══════════════════════════════════════════════════════════════════════════


def _make_portal_link(token: str, patient_id: str, name: str, phone: str) -> None:
    async def _insert():
        async with async_session_factory() as session:
            session.add(
                PatientPortalLinkModel(
                    token=token, patient_id=patient_id, patient_name=name,
                    phone=phone, phone_last4=phone[-4:], active=1,
                    expires_at=datetime.now(timezone.utc) + timedelta(days=30),
                )
            )
            await session.commit()

    _run(_insert())


class TestFamilyLocker:
    def _family(self, suffix: str, phone: str):
        father = _make_patient(f"CQ-FAM-{suffix}-1", f"Father {suffix}", phone, age=52)
        daughter = _make_patient(f"CQ-FAM-{suffix}-2", f"Daughter {suffix}", phone, age=14)
        _make_portal_link(f"fam{suffix}father", father, f"Father {suffix}", phone)
        _make_portal_link(f"fam{suffix}daughter", daughter, f"Daughter {suffix}", phone)
        return father, daughter

    def test_the_locker_needs_a_verified_session(self, client):
        phone = "9511111001"
        self._family("A", phone)
        response = client.get("/my/famAfather/family")
        assert response.status_code == 401

    def test_after_verification_the_whole_family_is_listed(self, client):
        phone = "9511111002"
        father, daughter = self._family("B", phone)

        # Verify with the registered number — the same check the portal uses.
        verify = client.post("/my/famBfather/verify", json={"phone": phone})
        assert verify.status_code == 200, verify.text

        body = client.get("/my/famBfather/family").json()
        assert body["ok"] is True
        assert body["count"] == 2
        ids = {m["patient_id"] for m in body["members"]}
        assert {father, daughter} <= ids
        assert body["phone_masked"].endswith(phone[-4:])

    def test_the_active_profile_is_flagged(self, client):
        phone = "9511111003"
        father, _daughter = self._family("C", phone)
        client.post("/my/famCfather/verify", json={"phone": phone})
        body = client.get("/my/famCfather/family").json()
        me = [m for m in body["members"] if m["is_me"]]
        assert len(me) == 1
        assert me[0]["patient_id"] == father

    def test_every_member_gets_a_working_portal_link(self, client):
        """The point of the locker: stop the family juggling five links."""
        phone = "9511111004"
        self._family("D", phone)
        client.post("/my/famDfather/verify", json={"phone": phone})
        body = client.get("/my/famDfather/family").json()
        for member in body["members"]:
            assert member["portal_url"].endswith(member["portal_token"])
            assert member["portal_token"]

    def test_the_locker_does_not_leak_another_members_readings(self, client):
        phone = "9511111005"
        self._family("E", phone)
        client.post("/my/famEfather/verify", json={"phone": phone})
        body = client.get("/my/famEfather/family").json()
        for member in body["members"]:
            assert "readings" not in member
            assert "prescriptions" not in member

    def test_a_number_with_one_profile_still_works(self, client):
        phone = "9511111006"
        _make_patient("CQ-SOLO-1", "Solo Patient", phone)
        _make_portal_link("solotoken", "CQ-SOLO-1", "Solo Patient", phone)
        client.post("/my/solotoken/verify", json={"phone": phone})
        body = client.get("/my/solotoken/family").json()
        assert body["count"] == 1
        assert body["members"][0]["is_me"] is True

    def test_a_wrong_number_cannot_open_the_locker(self, client):
        phone = "9511111007"
        self._family("F", phone)
        response = client.post("/my/famFfather/verify", json={"phone": "9999999999"})
        assert response.status_code == 403
        assert client.get("/my/famFfather/family").status_code == 401
