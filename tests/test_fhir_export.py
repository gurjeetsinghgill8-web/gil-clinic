"""ABDM / FHIR export tests (master blueprint BLOCK 8 · ABD-03).

Run:  python -m pytest tests/test_fhir_export.py -q

ABD-01, ABD-02, ABD-04 and ABD-05 genuinely need the NHA sandbox credentials
(`ABDM_CLIENT_ID` / `ABDM_CLIENT_SECRET`) and are therefore blocked. **ABD-03 is
not blocked**, and this file is the proof:

  * the Bundle is structurally valid FHIR R4 (`validate_bundle` returns clean),
  * every clinical resource points at a patient that is actually inside it,
  * an empty record produces a valid Bundle rather than an invented one,
  * the patient can get their own export from the card link they already hold,
  * and the export is logged as an access, because it is a read of the record.

The validator here is deliberately NOT a full FHIR validator — that needs the
specification package, which is too heavy for this host. It checks the mistakes
that actually break an import.
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

_TEST_DB = ROOT / "test_fhir_export.db"
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
from src.infrastructure.abdm.fhir import (  # noqa: E402
    bundle_summary,
    fhir_bundle,
    fhir_observation,
    fhir_patient,
    validate_bundle,
)
from src.infrastructure.clinic.models.clinic_model import ClinicModel  # noqa: E402
from src.infrastructure.opd.models.opd_models import OpdPrescriptionModel  # noqa: E402
from src.infrastructure.opd.models.patient_portal_models import (  # noqa: E402
    HealthCardAccessModel,
    HealthCardModel,
    PatientReadingModel,
)
from src.infrastructure.patient.models.patient_model import PatientModel  # noqa: E402
from src.shared.infrastructure.database import async_session_factory  # noqa: E402

main_v2.Base.metadata.create_all(bind=main_v2.engine)
main_v2._migrate_sqlite_columns()

NOW = datetime.now(timezone.utc) - timedelta(hours=2)


def _run(coro):
    import asyncio

    return asyncio.run(coro)


class _FakePatient:
    def __init__(self, **kw):
        self.patient_id = kw.get("patient_id", "CQ-FHIR-1")
        self.name = kw.get("name", "FHIR Patient")
        self.gender = kw.get("gender", "Male")
        self.phone = kw.get("phone", "9812345678")
        self.date_of_birth = kw.get("date_of_birth", "1980-05-04")
        self.blood_group = kw.get("blood_group", "B+")


class _FakePrescription:
    def __init__(self, diagnosis="", medicines=""):
        self.patient_id = "CQ-FHIR-1"
        self.diagnosis = diagnosis
        self.medicines = medicines


# ══════════════════════════════════════════════════════════════════════════
# 1. Pure Bundle construction
# ══════════════════════════════════════════════════════════════════════════


class TestBundleShape:
    def test_a_minimal_bundle_is_valid_fhir(self):
        bundle = fhir_bundle(patient=_FakePatient())
        assert bundle["resourceType"] == "Bundle"
        assert bundle["type"] == "collection"
        assert validate_bundle(bundle) == []

    def test_every_entry_has_a_full_url_and_an_id(self):
        bundle = fhir_bundle(
            patient=_FakePatient(),
            prescriptions=[_FakePrescription(diagnosis="Hypertension", medicines="Amlodipine 5mg")],
            readings=[{"label": "BP", "value": 130, "unit": "mmHg", "date_time": "2026-10-01"}],
        )
        for entry in bundle["entry"]:
            assert entry["fullUrl"].startswith("urn:uuid:")
            assert entry["resource"]["id"]

    def test_total_matches_the_entry_count(self):
        bundle = fhir_bundle(patient=_FakePatient())
        assert bundle["total"] == len(bundle["entry"])

    def test_a_patient_only_bundle_is_honest_not_padded(self):
        """No invented Observations just to look complete."""
        bundle = fhir_bundle(patient=_FakePatient())
        summary = bundle_summary(bundle)
        assert summary["counts"] == {"Patient": 1}

    def test_provenance_is_recorded(self):
        bundle = fhir_bundle(patient=_FakePatient())
        assert bundle["timestamp"]
        assert bundle["meta"]["lastUpdated"]
        tags = bundle["meta"]["tag"]
        assert tags and tags[0]["code"] == "offline-export"
        # The tag must not overclaim ABDM linkage that does not exist yet.
        assert "not yet" in tags[0]["display"].lower()

    def test_prescriptions_and_readings_are_included(self):
        bundle = fhir_bundle(
            patient=_FakePatient(),
            prescriptions=[
                _FakePrescription(diagnosis="Hypertension", medicines="Amlodipine"),
                _FakePrescription(diagnosis="", medicines="Vitamin D"),
            ],
            readings=[
                {"label": "BP", "value": 130, "unit": "mmHg", "date_time": "2026-10-01"},
                {"label": "Sugar", "value": 110, "unit": "mg/dL", "date_time": "2026-10-02"},
            ],
        )
        summary = bundle_summary(bundle)
        assert summary["counts"]["Patient"] == 1
        assert summary["counts"]["MedicationRequest"] == 2
        assert summary["counts"]["Observation"] == 2
        # Only the prescription with a real diagnosis gets a DiagnosticReport —
        # an empty conclusion is noise in a record a clinician must read.
        assert summary["counts"]["DiagnosticReport"] == 1

    def test_clinic_produces_organization_and_practitioner(self):
        clinic = ClinicModel(
            clinic_name="FHIR Clinic", clinic_code="FH-C",
            doctor_name="Dr FHIR", doctor_degree="MBBS",
        )
        bundle = fhir_bundle(patient=_FakePatient(), clinic=clinic)
        summary = bundle_summary(bundle)
        assert summary["counts"]["Organization"] == 1
        assert summary["counts"]["Practitioner"] == 1

    def test_a_bundle_without_a_patient_is_still_valid(self):
        bundle = fhir_bundle(patient=None)
        assert validate_bundle(bundle) == []
        assert bundle["total"] == 0

    def test_junk_resources_are_dropped_not_emitted(self):
        """A resource without a resourceType would fail FHIR validation."""
        bundle = fhir_bundle(
            patient=_FakePatient(),
            readings=[{"label": "BP", "value": 1}, "not-a-dict", None],
        )
        assert validate_bundle(bundle) == []
        for entry in bundle["entry"]:
            assert entry["resource"].get("resourceType")

    def test_unknown_gender_maps_to_unknown_not_a_guess(self):
        bundle = fhir_bundle(patient=_FakePatient(gender="Not Specified"))
        patient = bundle["entry"][0]["resource"]
        assert patient["gender"] == "unknown"


class TestValidateBundle:
    def test_it_catches_a_wrong_resource_type(self):
        problems = validate_bundle({"resourceType": "Patient", "entry": []})
        assert any("Bundle" in p for p in problems)

    def test_it_catches_a_missing_entry_wrapper(self):
        problems = validate_bundle(
            {"resourceType": "Bundle", "type": "collection", "total": 1, "entry": [{}]}
        )
        assert any("no resource" in p for p in problems)

    def test_it_catches_a_total_mismatch(self):
        bundle = fhir_bundle(patient=_FakePatient())
        bundle["total"] = 99
        assert any("does not match" in p for p in validate_bundle(bundle))

    def test_it_catches_a_dangling_subject_reference(self):
        """A clinical resource pointing at a patient who is not in the Bundle."""
        problems = validate_bundle(
            {
                "resourceType": "Bundle",
                "type": "collection",
                "total": 1,
                "entry": [
                    {
                        "fullUrl": "urn:uuid:x",
                        "resource": {
                            "resourceType": "Observation",
                            "id": "x",
                            "subject": {"reference": "Patient/GHOST"},
                        },
                    }
                ],
            }
        )
        assert any("dangling" in p for p in problems)

    def test_a_good_bundle_has_no_problems(self):
        bundle = fhir_bundle(
            patient=_FakePatient(),
            readings=[{"label": "BP", "value": 120, "unit": "mmHg", "date_time": "2026-10-01"}],
        )
        assert validate_bundle(bundle) == []

    def test_it_does_not_crash_on_junk(self):
        for junk in (None, [], "x", {}, {"entry": "not-a-list"}):
            assert isinstance(validate_bundle(junk), list)

    def test_subject_references_resolve_inside_the_bundle(self):
        bundle = fhir_bundle(
            patient=_FakePatient(patient_id="CQ-RESOLVE"),
            readings=[{"label": "BP", "value": 120, "unit": "mmHg", "date_time": "2026-10-01"}],
        )
        for entry in bundle["entry"]:
            subject = (entry["resource"].get("subject") or {}).get("reference")
            if subject:
                assert subject == "Patient/CQ-RESOLVE"


# ══════════════════════════════════════════════════════════════════════════
# 2. Live export endpoints
# ══════════════════════════════════════════════════════════════════════════


def _seed_patient(patient_id: str, name: str, phone: str, clinic_id: str = "",
                  with_readings: bool = True) -> None:
    from src.shared.domain.base_entity import uuid7

    async def _insert():
        async with async_session_factory() as session:
            session.add(
                PatientModel(
                    id=uuid7(), patient_id=patient_id, name=name, age=44,
                    gender="Female", date_of_birth="1981-02-02", blood_group="O+",
                    phone=phone,
                    phone_hash=hashlib.sha256(phone.encode()).hexdigest(),
                    address="Test road", status="active", total_visits=2,
                    clinic_id=clinic_id or None,
                    version=1, created_at=NOW, updated_at=NOW,
                )
            )
            session.add(
                OpdPrescriptionModel(
                    patient_id=patient_id, clinic_id=clinic_id or None,
                    doctor_id="chief", diagnosis="Type 2 Diabetes",
                    medicines="Metformin 500mg BD", created_at=NOW,
                )
            )
            if with_readings:
                session.add(
                    PatientReadingModel(
                        patient_id=patient_id, code="bp", label="BP",
                        unit="mmHg", value=128.0, date_time="2026-10-01T09:00:00",
                        source="patient", status="ok", created_at=NOW, updated_at=NOW,
                    )
                )
            await session.commit()

    _run(_insert())


def _seed_card(uid: str, patient_id: str, name: str) -> None:
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


def _seed_clinic(code: str, name: str) -> str:
    from src.shared.domain.base_entity import uuid7

    clinic_id = uuid7()

    async def _insert():
        async with async_session_factory() as session:
            session.add(
                ClinicModel(
                    id=clinic_id, clinic_name=name, clinic_code=code,
                    doctor_name=f"Dr {name}", specialty="Cardiology",
                    city="Jodhpur", state="Rajasthan",
                    open_time="00:01", close_time="23:58",
                    is_license_active=True, is_active=True,
                )
            )
            await session.commit()
        return str(clinic_id)

    return _run(_insert())


@pytest.fixture(scope="module")
def client():
    return TestClient(main_v2.app)


class TestStaffBundleExport:
    def test_the_bundle_endpoint_returns_valid_fhir(self, client):
        clinic = _seed_clinic("FH-A", "FHIR Bundle Clinic")
        _seed_patient("CQ-FHIR-A", "Bundle Patient", "9711111101", clinic_id=clinic)

        response = client.get("/api/v1/abdm/fhir/bundle/CQ-FHIR-A")
        assert response.status_code == 200, response.text
        assert "fhir+json" in response.headers["content-type"]
        bundle = response.json()
        assert bundle["resourceType"] == "Bundle"
        assert validate_bundle(bundle) == []
        assert int(response.headers["X-FHIR-Resources"]) == bundle["total"]

    def test_the_bundle_contains_the_real_record(self, client):
        clinic = _seed_clinic("FH-B", "FHIR Record Clinic")
        _seed_patient("CQ-FHIR-B", "Record Patient", "9711111102", clinic_id=clinic)

        bundle = client.get("/api/v1/abdm/fhir/bundle/CQ-FHIR-B").json()
        summary = bundle_summary(bundle)
        assert summary["counts"]["Patient"] == 1
        assert summary["counts"]["MedicationRequest"] >= 1
        assert summary["counts"]["Observation"] >= 1
        assert summary["counts"]["Organization"] == 1
        assert summary["patient_id"] == "CQ-FHIR-B"

    def test_download_mode_sends_a_filename(self, client):
        _seed_patient("CQ-FHIR-C", "Download Patient", "9711111103")
        response = client.get(
            "/api/v1/abdm/fhir/bundle/CQ-FHIR-C", params={"download": "true"}
        )
        assert response.status_code == 200
        assert "attachment" in response.headers["content-disposition"]
        assert "fhir-CQ-FHIR-C.json" in response.headers["content-disposition"]

    def test_an_unknown_patient_returns_an_operation_outcome(self, client):
        """FHIR's own error shape, not a bare 404 body."""
        response = client.get("/api/v1/abdm/fhir/bundle/CQ-NOBODY")
        assert response.status_code == 404
        body = response.json()
        assert body["resourceType"] == "OperationOutcome"
        assert body["issue"][0]["code"] == "not-found"

    def test_a_patient_with_no_clinic_still_exports(self, client):
        _seed_patient("CQ-FHIR-D", "No Clinic Patient", "9711111104", with_readings=False)
        bundle = client.get("/api/v1/abdm/fhir/bundle/CQ-FHIR-D").json()
        assert validate_bundle(bundle) == []
        # No clinic → no Organization, and that is correct, not a gap to fill.
        assert "Organization" not in bundle_summary(bundle)["counts"]

    def test_the_practitioner_endpoint_emits_a_valid_bundle(self, client):
        clinic = _seed_clinic("FH-E", "FHIR Practitioner Clinic")
        response = client.get(f"/api/v1/abdm/fhir/Practitioner/{clinic}")
        assert response.status_code == 200
        bundle = response.json()
        assert bundle["resourceType"] == "Bundle"
        # Same builder as the full export, so a consumer never has to
        # special-case which endpoint produced a Bundle.
        assert validate_bundle(bundle) == []


class TestPatientFhirExport:
    def test_the_card_link_can_export_its_own_record(self, client):
        _seed_patient("CQ-FHIR-E", "Card Export Patient", "9711111105")
        _seed_card("fhir-card-1", "CQ-FHIR-E", "Card Export Patient")

        response = client.get("/card/fhir-card-1/fhir")
        assert response.status_code == 200, response.text
        assert "fhir+json" in response.headers["content-type"]
        bundle = response.json()
        assert validate_bundle(bundle) == []
        assert bundle_summary(bundle)["patient_id"] == "CQ-FHIR-E"

    def test_the_export_is_logged_as_an_access(self, client):
        """A FHIR export is a full read of the record — it must be auditable."""
        _seed_patient("CQ-FHIR-F", "Audit Export Patient", "9711111106")
        _seed_card("fhir-card-2", "CQ-FHIR-F", "Audit Export Patient")
        client.get("/card/fhir-card-2/fhir")

        async def _rows():
            import sqlalchemy as sa

            async with async_session_factory() as session:
                row = await session.execute(
                    sa.select(HealthCardAccessModel).where(
                        HealthCardAccessModel.uid == "fhir-card-2"
                    )
                )
                return row.scalars().all()

        rows = _run(_rows())
        assert len(rows) == 1
        assert rows[0].outcome == "granted"

    def test_a_revoked_card_cannot_export(self, client):
        _seed_patient("CQ-FHIR-G", "Revoked Export Patient", "9711111107")
        _seed_card("fhir-card-3", "CQ-FHIR-G", "Revoked Export Patient")

        async def _revoke():
            import sqlalchemy as sa

            async with async_session_factory() as session:
                row = await session.execute(
                    sa.select(HealthCardModel).where(HealthCardModel.uid == "fhir-card-3")
                )
                card = row.scalars().first()
                card.active = 0
                card.revoked_at = datetime.now(timezone.utc)
                await session.commit()

        _run(_revoke())
        assert client.get("/card/fhir-card-3/fhir").status_code == 404

    def test_an_unknown_card_export_is_a_clean_404(self, client):
        assert client.get("/card/no-such-card/fhir").status_code == 404

    def test_the_denied_export_is_also_logged(self, client):
        client.get("/card/fhir-card-missing/fhir")

        async def _rows():
            import sqlalchemy as sa

            async with async_session_factory() as session:
                row = await session.execute(
                    sa.select(HealthCardAccessModel).where(
                        HealthCardAccessModel.uid == "fhir-card-missing"
                    )
                )
                return row.scalars().all()

        rows = _run(_rows())
        assert len(rows) == 1
        assert rows[0].outcome == "denied"


class TestNoCredentialsNeeded:
    def test_the_export_works_with_abdm_unconfigured(self, client):
        """ABD-03 is the one Block 8 item that is not blocked — prove it."""
        import os as _os

        assert not _os.getenv("ABDM_CLIENT_ID"), "this test assumes no live credentials"
        _seed_patient("CQ-FHIR-H", "Offline Patient", "9711111108")
        response = client.get("/api/v1/abdm/fhir/bundle/CQ-FHIR-H")
        assert response.status_code == 200
        assert validate_bundle(response.json()) == []

    def test_status_still_reports_the_missing_credentials_honestly(self, client):
        body = client.get("/api/v1/abdm/status").json()
        # The scaffold must never pretend to be linked.
        assert body.get("configured") in (False, 0, None) or body.get("linked") in (False, 0, None)
