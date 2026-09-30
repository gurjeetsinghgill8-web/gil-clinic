"""ABDM compliance API — scaffold, ready to plug NHA sandbox credentials.

    GET  /api/v1/abdm/status                       → config status (masked)
    POST /api/v1/abdm/abha/link                    → link ABHA number to patient
    GET  /api/v1/abdm/fhir/Patient/{pid}           → FHIR R4 Patient
    GET  /api/v1/abdm/fhir/Practitioner/{cid}      → FHIR Practitioner + Organization
    POST /api/v1/abdm/consent                      → create consent artefact
    GET  /api/v1/abdm/consent/{pid}                → list consent
    POST /api/v1/abdm/consent/{id}/revoke          → revoke consent
    GET  /api/v1/abdm/dhis/transactions            → DHIS incentive transaction log
    GET  /abdm                                      → human status page

Real NHA calls abhi stubbed hain (credentials ke bina crash nahi hota) — local
records ban jaate hain aur transactions DHIS claim ke liye log hote hain.
"""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

from src.infrastructure.abdm.fhir import (
    fhir_organization,
    fhir_patient,
    fhir_practitioner,
)
from src.infrastructure.abdm.models import (
    AbdmTransactionModel,
    AbhaLinkModel,
    ConsentArtefactModel,
)
from src.infrastructure.abdm.settings import abdm_config
from src.infrastructure.clinic.models.clinic_model import ClinicModel
from src.infrastructure.patient.models.patient_model import PatientModel
from src.shared.infrastructure.database import async_session_factory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/abdm", tags=["ABDM"])

_TEMPLATES_DIR = Path(__file__).parents[4] / "templates"


# ═════════════════════════════════════════════════════════════════════════════
# Status
# ═════════════════════════════════════════════════════════════════════════════
@router.get("/status")
async def abdm_status():
    """Config status — kya NHA credentials set hain, kaun se building blocks ready."""
    cfg = abdm_config()
    return {
        "ok": True,
        "enabled": cfg["enabled"],
        "configured": cfg["configured"],
        "sandbox_url": cfg["sandbox_url"],
        "client_id": cfg["client_id"] or None,
        "client_secret_set": cfg["client_secret_set"],
        "hip_id": cfg["hip_id"] or None,
        "hiu_id": cfg["hiu_id"] or None,
        "facility_id": cfg["facility_id"] or None,
        "building_blocks": ["ABHA", "HPR", "HFR", "HIP/HIU", "Consent Manager", "FHIR R4", "DHIS"],
        "note": (
            "NHA credentials set nahi hain — abhi local scaffold mode me hai. "
            "ABDM_ENABLED + ABDM_CLIENT_ID/SECRET set karke sandbox se connect karein."
            if not cfg["configured"]
            else "NHA credentials set — sandbox connect ready."
        ),
    }


# ═════════════════════════════════════════════════════════════════════════════
# ABHA link
# ═════════════════════════════════════════════════════════════════════════════
@router.post("/abha/link")
async def abha_link(request: Request):
    """Patient ka ABHA number link karo (local record + transaction log).

    Body: {patient_id, abha_number, abha_address?, clinic_id?}
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    patient_id = str(body.get("patient_id") or "").strip()
    abha_number = str(body.get("abha_number") or "").strip()
    clinic_id = str(body.get("clinic_id") or "").strip() or None
    abha_address = str(body.get("abha_address") or "").strip()
    if not patient_id or not abha_number:
        return JSONResponse({"ok": False, "error": "patient_id aur abha_number chahiye"}, status_code=400)

    async with async_session_factory() as session:
        row = await session.execute(
            sa.select(AbhaLinkModel).where(AbhaLinkModel.patient_id == patient_id)
        )
        link = row.scalar_one_or_none()
        if link is None:
            link = AbhaLinkModel(patient_id=patient_id, abha_number=abha_number,
                                 abha_address=abha_address, clinic_id=clinic_id, status="pending")
            session.add(link)
        else:
            link.abha_number = abha_number
            link.abha_address = abha_address or link.abha_address
            link.status = "pending"
        session.add(
            AbdmTransactionModel(
                patient_id=patient_id, clinic_id=clinic_id, txn_type="abha_create",
                status="pending", request_id=uuid.uuid4().hex,
                payload_json=json.dumps({"abha_number": abha_number}),
            )
        )
        await session.commit()

    return JSONResponse(
        {
            "ok": True,
            "patient_id": patient_id,
            "abha_number": abha_number,
            "status": "pending",
            "note": "ABHA link local record ban gaya. NHA sandbox connect hone par real "
                    "verification + ABHA creation hoga (abhi stubbed).",
        }
    )


# ═════════════════════════════════════════════════════════════════════════════
# FHIR R4 resources
# ═════════════════════════════════════════════════════════════════════════════
@router.get("/fhir/Patient/{patient_id}")
async def fhir_patient_resource(patient_id: str):
    """PatientModel → FHIR R4 Patient resource."""
    async with async_session_factory() as session:
        row = await session.execute(
            sa.select(PatientModel).where(PatientModel.patient_id == patient_id).limit(1)
        )
        p = row.scalar_one_or_none()
    if p is None:
        return JSONResponse({"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "not-found", "diagnostics": "Patient not found"}]}, status_code=404)
    return JSONResponse(fhir_patient(p))


@router.get("/fhir/Practitioner/{clinic_id}")
async def fhir_practitioner_resource(clinic_id: str):
    """ClinicModel → FHIR Practitioner + Organization (bundle)."""
    try:
        cid = uuid.UUID(clinic_id)
    except (ValueError, AttributeError, TypeError):
        return JSONResponse({"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "invalid", "diagnostics": "Invalid clinic id"}]}, status_code=400)
    async with async_session_factory() as session:
        c = await session.get(ClinicModel, cid)
    if c is None:
        return JSONResponse({"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "not-found", "diagnostics": "Clinic not found"}]}, status_code=404)
    return JSONResponse(
        {
            "resourceType": "Bundle",
            "type": "collection",
            "entry": [
                {"resource": fhir_practitioner(c)},
                {"resource": fhir_organization(c)},
            ],
        }
    )


# ═════════════════════════════════════════════════════════════════════════════
# Consent (ABDM Consent Manager + DPDP)
# ═════════════════════════════════════════════════════════════════════════════
@router.post("/consent")
async def create_consent(request: Request):
    """Consent artefact banao. Body: {patient_id, purpose, data_types?, clinic_id?}"""
    try:
        body = await request.json()
    except Exception:
        body = {}
    patient_id = str(body.get("patient_id") or "").strip()
    purpose = str(body.get("purpose") or "").strip()
    clinic_id = str(body.get("clinic_id") or "").strip() or None
    data_types = str(body.get("data_types") or "").strip()
    if not patient_id or not purpose:
        return JSONResponse({"ok": False, "error": "patient_id aur purpose chahiye"}, status_code=400)

    cfg = abdm_config()
    async with async_session_factory() as session:
        artefact = ConsentArtefactModel(
            patient_id=patient_id, purpose=purpose, clinic_id=clinic_id,
            hip_id=cfg["hip_id"], hiu_id=cfg["hiu_id"], data_types=data_types,
            status="granted",
        )
        session.add(artefact)
        session.add(
            AbdmTransactionModel(
                patient_id=patient_id, clinic_id=clinic_id, txn_type="consent_grant",
                status="success", request_id=uuid.uuid4().hex,
                payload_json=json.dumps({"purpose": purpose}),
            )
        )
        await session.commit()
        consent_id = str(artefact.id)

    return JSONResponse({"ok": True, "consent_id": consent_id, "status": "granted", "purpose": purpose})


@router.get("/consent/{patient_id}")
async def list_consent(patient_id: str):
    async with async_session_factory() as session:
        rows = await session.execute(
            sa.select(ConsentArtefactModel)
            .where(ConsentArtefactModel.patient_id == patient_id)
            .order_by(ConsentArtefactModel.granted_at.desc())
            .limit(50)
        )
        out = [
            {
                "id": str(c.id), "purpose": c.purpose, "status": c.status,
                "data_types": c.data_types, "granted_at": c.granted_at.isoformat() if c.granted_at else "",
                "expires_at": c.expires_at.isoformat() if c.expires_at else "",
            }
            for c in rows.scalars()
        ]
    return {"ok": True, "consents": out, "count": len(out)}


@router.post("/consent/{consent_id}/revoke")
async def revoke_consent(consent_id: str):
    """Consent revoke karo (DPDP right-to-revoke)."""
    try:
        cid = uuid.UUID(consent_id)
    except (ValueError, AttributeError, TypeError):
        return JSONResponse({"ok": False, "error": "Invalid consent id"}, status_code=400)
    async with async_session_factory() as session:
        c = await session.get(ConsentArtefactModel, cid)
        if c is None:
            return JSONResponse({"ok": False, "error": "Consent nahi mila"}, status_code=404)
        c.status = "revoked"
        from datetime import datetime, timezone

        c.revoked_at = datetime.now(timezone.utc)
        await session.commit()
    return JSONResponse({"ok": True, "status": "revoked"})


# ═════════════════════════════════════════════════════════════════════════════
# DHIS transaction log
# ═════════════════════════════════════════════════════════════════════════════
@router.get("/dhis/transactions")
async def dhis_transactions(limit: int = Query(default=100, le=1000)):
    async with async_session_factory() as session:
        rows = await session.execute(
            sa.select(AbdmTransactionModel).order_by(AbdmTransactionModel.created_at.desc()).limit(limit)
        )
        out = [
            {
                "id": str(t.id), "patient_id": t.patient_id, "txn_type": t.txn_type,
                "status": t.status, "created_at": t.created_at.isoformat() if t.created_at else "",
            }
            for t in rows.scalars()
        ]
    return {"ok": True, "transactions": out, "count": len(out)}


# ═════════════════════════════════════════════════════════════════════════════
# Human status page
# ═════════════════════════════════════════════════════════════════════════════
# ── Human status page (top-level, outside the /api/v1 prefix) ────────────────
page_router = APIRouter(tags=["ABDM"])


@page_router.get("/abdm", include_in_schema=False)
async def abdm_page():
    import jinja2

    cfg = abdm_config()
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)), auto_reload=True)
    return HTMLResponse(content=env.get_template("abdm_status.html").render(**cfg))
