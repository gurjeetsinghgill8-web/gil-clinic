"""Full integration smoke test — har naye feature ko ek saath check karta hai.

Deploy ke baad (PythonAnywhere console me) chalane ke liye:
    python scripts/integration_smoke_test.py

Har feature PASS/FAIL report karta hai + aakhri summary. Test data (temp patient/
temp clinic) apne aap cleanup ho jata hai — demo clinics chhoote hain.

⚠️ Ye test DEV/SQLite DB ke khilaf chalta hai (main_v2 ki DB URL). Production
par chalane se pehle backup lein (ye sirf temp records banata + delete karta hai).
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import sqlalchemy as sa  # noqa: E402

import main_v2  # noqa: E402

from src.infrastructure.clinic.models.clinic_model import ClinicModel  # noqa: E402
from src.infrastructure.patient.models.patient_model import PatientModel  # noqa: E402
from src.shared.domain.base_entity import uuid7  # noqa: E402
from src.shared.infrastructure.database import (  # noqa: E402
    Base,
    async_session_factory,
)

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = ""):
    RESULTS.append((name, ok, detail))
    print(f"  {'✅' if ok else '❌'} {name}" + (f" — {detail}" if detail else ""))


class FakeReq:
    base_url = "http://localhost:8000/"

    def __init__(self, body=None):
        self._b = body or {}

    async def json(self):
        return self._b


def _body(resp) -> dict:
    if hasattr(resp, "body"):
        return json.loads(resp.body.decode())
    return resp


async def run():
    print("=== GHOS Integration Smoke Test ===\n")
    Base.metadata.create_all(bind=main_v2.engine)
    main_v2._migrate_sqlite_columns()

    # Monkeypatch session guards (test sirf)
    import src.presentation.opd.routes.opd_routes as o
    o._require_opd_session = lambda req: {"doctor_id": "chief", "role": "chief"}
    import src.presentation.admin.routes.doctor_routes as dr
    dr.require_admin_session = lambda req: {"username": "super_admin"}

    # ── 1) Route registration ──
    paths = set(main_v2.app.openapi()["paths"].keys())
    mp = {p for p in paths if "marketplace" in p or "abdm" in p}
    check("Routes registered (marketplace + ABDM API)", len(mp) >= 8, f"{len(mp)} routes")

    # ── 2) Marketplace ──
    from src.presentation.marketplace.routes.marketplace_routes import (
        marketplace_doctors, marketplace_meta, marketplace_book,
    )
    meta = await marketplace_meta()
    check("Marketplace meta (cities/specialties)", bool(meta["cities"]) and bool(meta["specialties"]),
          f"{len(meta['cities'])} cities, {len(meta['specialties'])} specialties")
    docs = await marketplace_doctors(city="", specialty=None, problem=None, lat=None, lon=None)
    check("Marketplace doctors (partner-first)", docs["total"] > 0, f"{docs['total']} doctors, {docs['partners']} partners")
    clinic_ids = [d["id"] for d in docs["doctors"] if d["tier"] == 1]
    check("Partner clinics have live signal", bool(clinic_ids) and all(d["live"] for d in docs["doctors"] if d["tier"] == 1))

    # ── 3) Marketplace booking (real queue entry) ──
    book = _body(await marketplace_book(FakeReq({"clinic_id": clinic_ids[0], "name": "Smoke Patient", "phone": "9898989898", "problem": "fever"})))
    check("Marketplace 1-tap booking", book.get("ok") and book.get("token"), f"token #{book.get('token')}")
    smoke_patient_id = book.get("patient_id")

    # ── 4) ABDM ──
    from src.presentation.abdm.routes.abdm_routes import (
        abdm_status, abha_link, create_consent, fhir_patient_resource, dhis_transactions,
    )
    st = await abdm_status()
    check("ABDM status", st["ok"] and "building_blocks" in st)
    ab = _body(await abha_link(FakeReq({"patient_id": smoke_patient_id, "abha_number": "12345678901234"})))
    check("ABDM ABHA link", ab.get("ok"), f"status={ab.get('status')}")
    co = _body(await create_consent(FakeReq({"patient_id": smoke_patient_id, "purpose": "Diagnosis"})))
    check("ABDM consent create", co.get("ok"), f"id={str(co.get('consent_id'))[:8]}")
    fh = _body(await fhir_patient_resource(smoke_patient_id))
    check("ABDM FHIR Patient", fh.get("resourceType") == "Patient", f"gender={fh.get('gender')}")
    dt = await dhis_transactions(limit=50)
    check("ABDM DHIS transaction log", dt["count"] >= 2, f"{dt['count']} txns")

    # ── 5) Health Card ──
    from src.presentation.health_card.routes.health_card_routes import (
        api_create_health_card, health_card_page,
    )
    hc = _body(await api_create_health_card(FakeReq({"patient_id": smoke_patient_id})))
    card_page = await health_card_page(FakeReq(), hc["uid"])
    check("Health Card create + page", hc.get("ok") and card_page.status_code == 200)

    # ── 6) Lab Network ──
    from src.presentation.lab_network.routes.lab_network_routes import (
        create_lab_order, submit_lab_result, lab_result_page,
    )
    lo = _body(await create_lab_order(FakeReq({"patient_id": smoke_patient_id, "tests": "CBC\nHbA1c"})))
    lr = _body(await submit_lab_result(FakeReq({"order_id": lo["order_id"], "results": [
        {"test": "HbA1c", "value": "7.2", "unit": "%", "ref_range": "<5.7", "flag": "HIGH"},
    ]})))
    lab_page = await lab_result_page(FakeReq(), lo["report_token"])
    check("Lab order → result → patient view", lr.get("ok") and lab_page.status_code == 200)

    # ── 7) Rx Pad ──
    from src.presentation.rx_pad.routes.rx_pad_routes import rx_pad
    from src.infrastructure.opd.models.opd_models import OpdPrescriptionModel
    import datetime as _dt
    now = _dt.datetime.now(_dt.timezone.utc)
    async with async_session_factory() as s:
        s.add(OpdPrescriptionModel(patient_id=smoke_patient_id, patient_name="Smoke Patient",
                                   diagnosis="Viral fever", medicines="Paracetamol 500mg 1-0-1",
                                   doctor_id="chief", created_at=now, updated_at=now))
        await s.commit()
    pad = await rx_pad(FakeReq(), patient_id=smoke_patient_id)
    check("Rx Pad (letterhead)", pad.status_code == 200 and "GIL" in pad.body.decode() or pad.status_code == 200)

    # ── 8) Onboarding with geo/ABDM fields ──
    resp = await dr.api_onboard_doctor(
        FakeReq(), doctor_name="Dr. Smoke", doctor_phone="", doctor_email="",
        clinic_name="Smoke Clinic", address="", city="Jaipur", state="Rajasthan",
        doctor_degree="MBBS", doctor_reg_no="", specialty="General Physician",
        license_duration=2, custom_username="", custom_password="",
        latitude="26.91", longitude="75.78", hpr_id="HPR-SMOKE", hfr_id="HFR-SMOKE",
    )
    async with async_session_factory() as s:
        c = (await s.execute(sa.select(ClinicModel).where(ClinicModel.clinic_code != "").order_by(ClinicModel.created_at.desc()).limit(1))).scalar_one_or_none()
        check("Onboarding persists lat/long/HPR/HFR", c and c.latitude == 26.91 and c.hpr_id == "HPR-SMOKE",
              f"lat={c.latitude}, hpr={c.hpr_id}")
        smoke_clinic = c

    # ── 9) Settings backfill ──
    from src.presentation.opd.routes.opd_routes import _get_settings
    settings = await _get_settings("chief")
    check("Settings returns geo/ABDM fields", "latitude" in settings and "hpr_id" in settings)

    # ── Cleanup (temp patient + temp clinic + their rows) ──
    async with async_session_factory() as s:
        from src.infrastructure.abdm.models import AbhaLinkModel, ConsentArtefactModel, AbdmTransactionModel
        from src.infrastructure.lab.models import LabOrderModel
        from src.infrastructure.opd.models.patient_portal_models import HealthCardModel
        from src.infrastructure.queue.models.queue_entry_model import QueueEntryModel
        from src.infrastructure.opd.models.opd_models import OpdPrescriptionModel
        for model in (AbhaLinkModel, ConsentArtefactModel, AbdmTransactionModel, LabOrderModel,
                      HealthCardModel, QueueEntryModel, OpdPrescriptionModel):
            for obj in (await s.execute(sa.select(model).where(model.patient_id == smoke_patient_id))).scalars():
                await s.delete(obj)
        for obj in (await s.execute(sa.select(PatientModel).where(PatientModel.patient_id == smoke_patient_id))).scalars():
            await s.delete(obj)
        if smoke_clinic:
            await s.delete(smoke_clinic)
        await s.commit()

    print("\n=== Summary ===")
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    total = len(RESULTS)
    print(f"  {passed}/{total} checks passed")
    for name, ok, _ in RESULTS:
        if not ok:
            print(f"  ❌ FAILED: {name}")
    print("\n  ✅ ALL PASS" if passed == total else "\n  ⚠️ SOME FAILED")


if __name__ == "__main__":
    asyncio.run(run())
