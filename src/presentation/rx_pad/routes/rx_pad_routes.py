"""Smart Prescription Pad — customized, print-ready Rx (GAP-06 + GAP-10).

Doctor session ke saath:
    GET /opd/api/rx-pad?patient_id=...   → print-ready prescription pad (HTML)

Pad doctor ke apne branding (clinic name, name, degree, reg no, address, phone)
ke saath banta hai — EKA DOC / Tatvacare ka "customized prescription pad" equivalent.
Print (Ctrl+P / Save as PDF) + WhatsApp share dono is page par hain.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import jinja2
import sqlalchemy as sa
from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse

from src.infrastructure.opd.models.opd_models import OpdPrescriptionModel
from src.infrastructure.patient.models.patient_model import PatientModel
from src.shared.infrastructure.database import async_session_factory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/opd/api", tags=["Rx Pad"])

_TEMPLATES_DIR = Path(__file__).parents[4] / "templates"
_jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)), auto_reload=True
)
_jinja_env.cache = {}


def _render(name: str, **context: Any) -> str:
    return _jinja_env.get_template(name).render(**context)


def _error_page(title: str, message: str) -> HTMLResponse:
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{title}</title>
<style>body{{font-family:system-ui,sans-serif;background:#f1f5f9;margin:0;display:flex;
align-items:center;justify-content:center;min-height:100vh;padding:20px}}
.card{{background:#fff;border-radius:14px;padding:26px;max-width:430px;text-align:center;
box-shadow:0 4px 18px rgba(15,23,42,.08)}}h1{{font-size:19px}}p{{color:#475569;font-size:14px}}</style>
</head><body><div class="card"><div style="font-size:40px">📝</div><h1>{title}</h1><p>{message}</p></div></body></html>"""
    return HTMLResponse(content=html, status_code=400)


@router.get("/rx-pad", include_in_schema=False)
async def rx_pad(request: Request, patient_id: str = Query("")):
    """Print-ready prescription pad for the latest saved Rx of a patient."""
    from src.presentation.opd.routes.opd_routes import (  # lazy (no import cycle)
        _get_settings,
        _require_opd_session,
    )

    sess = _require_opd_session(request)
    doctor_id = sess.get("doctor_id") or "chief"
    if not patient_id.strip():
        return _error_page("Patient nahi mila", "Pehle patient select karke Rx save karein.")

    async with async_session_factory() as session:
        rx_row = await session.execute(
            sa.select(OpdPrescriptionModel)
            .where(OpdPrescriptionModel.patient_id == patient_id)
            .order_by(OpdPrescriptionModel.created_at.desc())
            .limit(1)
        )
        rx = rx_row.scalar_one_or_none()
        if rx is None:
            return _error_page("Rx nahi mila", "Is patient ki koi saved prescription nahi hai. Pehle Rx save karein.")

        p_row = await session.execute(
            sa.select(PatientModel).where(PatientModel.patient_id == patient_id).limit(1)
        )
        patient = p_row.scalar_one_or_none()

    settings = await _get_settings(doctor_id, masked=True)

    # Build a plain-text Rx for WhatsApp share
    lines = [
        f"{settings.get('clinic_name') or 'Clinic'} — Prescription",
        f"Dr. {settings.get('doc_name') or 'Doctor'} ({settings.get('doc_degree') or settings.get('doc_subtitle') or ''})",
        f"Patient: {rx.patient_name or patient_id}",
    ]
    if rx.diagnosis:
        lines.append(f"Diagnosis: {rx.diagnosis}")
    if rx.medicines:
        lines.append(f"Rx: {rx.medicines}")
    if rx.advice:
        lines.append(f"Advice: {rx.advice}")
    if rx.follow_up:
        lines.append(f"Follow-up: {rx.follow_up}")
    rx_text = "\n".join(lines)

    from src.utils.public_url import public_base_url

    pad_url = f"{public_base_url(request)}/opd/api/rx-pad?patient_id={patient_id}"

    return HTMLResponse(
        _render(
            "rx_pad.html",
            clinic_name=settings.get("clinic_name") or "My Clinic",
            doc_name=settings.get("doc_name") or "Doctor",
            doc_degree=settings.get("doc_degree") or settings.get("doc_subtitle") or "MBBS",
            doc_reg_no=settings.get("doc_reg_no") or "",
            doc_extra_quals=settings.get("doc_extra_quals") or "",
            clinic_address=settings.get("clinic_address") or "",
            doc_phone=settings.get("doc_phone") or "",
            patient_name=rx.patient_name or (patient.name if patient else patient_id),
            patient_id=patient_id,
            age=patient.age if patient else rx.vitals or "",
            gender=patient.gender if patient else "",
            diagnosis=rx.diagnosis or "",
            medicines=rx.medicines or "",
            investigations=rx.investigations or "",
            advice=rx.advice or "",
            follow_up=rx.follow_up or "",
            vitals=rx.vitals or "",
            date=rx.created_at.strftime("%d %b %Y, %I:%M %p") if rx.created_at else "",
            rx_text=rx_text,
            pad_url=pad_url,
        )
    )
