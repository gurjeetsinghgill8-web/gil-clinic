"""Universal Health Card routes — portable, shareable patient summary.

PUBLIC (uid = secret, read-only):
    GET /card/{uid}                     → full health card (vitals + prescriptions)

DOCTOR (opd_session cookie):
    POST /opd/api/health-card           → create a card for a patient → shareable link

Card = identity + latest vitals + prescription history, QR + WhatsApp share.
Read-only (koi write endpoint nahi); `active=0` ya expiry se revoke hota hai.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
from pathlib import Path
from typing import Any, Optional

import jinja2
import sqlalchemy as sa
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from src.infrastructure.opd.models.opd_models import OpdPrescriptionModel
from src.infrastructure.opd.models.patient_portal_models import (
    HealthCardModel,
    PatientReadingModel,
)
from src.infrastructure.patient.models.patient_model import PatientModel
from src.shared.infrastructure.database import async_session_factory
from src.utils import patient_tokens as tk
from src.utils.patient_metrics import latest_reading_by_key

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health Card"])
doctor_router = APIRouter(prefix="/opd/api", tags=["Health Card (Doctor)"])

DEFAULT_CLINIC = "GIL CLINIC"

_TEMPLATES_DIR = Path(__file__).parents[4] / "templates"
_jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)), auto_reload=True
)
_jinja_env.cache = {}


def _render(name: str, **context: Any) -> str:
    return _jinja_env.get_template(name).render(**context)


def _error_page(title: str, message: str, status_code: int = 400) -> HTMLResponse:
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{title}</title>
<style>body{{font-family:system-ui,'Segoe UI',Roboto,Arial,sans-serif;background:#f1f5f9;margin:0;
display:flex;align-items:center;justify-content:center;min-height:100vh;padding:20px}}
.card{{background:#fff;border-radius:14px;padding:26px 22px;max-width:430px;text-align:center;
box-shadow:0 4px 18px rgba(15,23,42,.08)}}
h1{{font-size:19px;margin:8px 0 6px}}p{{color:#475569;font-size:14px;line-height:1.6;margin:6px 0}}
.icon{{font-size:44px}}</style></head>
<body><div class="card"><div class="icon">🪪</div><h1>{title}</h1><p>{message}</p></div></body></html>"""
    return HTMLResponse(content=html, status_code=status_code)


async def _card(session, uid: str) -> Optional[HealthCardModel]:
    row = await session.execute(sa.select(HealthCardModel).where(HealthCardModel.uid == uid))
    card = row.scalar_one_or_none()
    if card is None or not card.active:
        return None
    if tk.is_expired(card.expires_at):
        return None
    return card


async def _prescriptions(session, patient_id: str, limit: int = 8) -> list[dict[str, Any]]:
    rows = await session.execute(
        sa.select(OpdPrescriptionModel)
        .where(OpdPrescriptionModel.patient_id == patient_id)
        .order_by(OpdPrescriptionModel.created_at.desc())
        .limit(limit)
    )
    out = []
    for p in rows.scalars():
        out.append(
            {
                "diagnosis": (p.diagnosis or "").strip(),
                "medicines": (p.medicines or "").strip(),
                "complaints": (p.complaints or "").strip(),
                "vitals": (p.vitals or "").strip(),
                "advice": (p.advice or "").strip(),
                "follow_up": (p.follow_up or "").strip(),
                "doctor_id": p.doctor_id or "",
                "specialty": p.specialty or "",
                "created_at": p.created_at.strftime("%d %b %Y") if p.created_at else "",
            }
        )
    return out


@router.get("/card/{uid}", include_in_schema=False)
async def health_card_page(request: Request, uid: str):
    async with async_session_factory() as session:
        card = await _card(session, uid)
        if card is None:
            return _error_page(
                "Health Card kaam nahi kar raha",
                "Link adhoora, expire ya clinic ne band kar diya ho sakta hai. "
                "Kripya naya card maangein.",
                404,
            )
        card.view_count = (card.view_count or 0) + 1
        await session.commit()

        patient = None
        prow = await session.execute(
            sa.select(PatientModel).where(PatientModel.patient_id == card.patient_id).limit(1)
        )
        patient = prow.scalar_one_or_none()

        readings = []
        rrows = await session.execute(
            sa.select(PatientReadingModel)
            .where(PatientReadingModel.patient_id == card.patient_id)
            .order_by(PatientReadingModel.date_time.desc())
            .limit(500)
        )
        readings = [r.to_dict() for r in rrows.scalars()]
        prescriptions = await _prescriptions(session, card.patient_id)

    latest = latest_reading_by_key(readings)
    vitals = [
        {"label": r.get("label") or k, "value": r.get("value"), "unit": r.get("unit") or "",
         "status": r.get("status") or "ok"}
        for k, r in latest.items()
    ]

    phone_masked = ""
    if patient and patient.phone:
        phone_masked = "••••••" + patient.phone[-4:]

    # allergies / history from patient JSON fields (if present)
    allergies = []
    history = []
    if patient is not None:
        try:
            mh = patient.medical_history or []
            if isinstance(mh, list):
                for item in mh:
                    if isinstance(item, dict) and item.get("allergy"):
                        allergies.append(str(item.get("allergy")))
                    elif isinstance(item, dict) and item.get("condition"):
                        history.append(str(item.get("condition")))
        except Exception:
            pass

    from src.utils.public_url import public_base_url

    card_url = f"{public_base_url(request)}/card/{uid}"

    return HTMLResponse(
        _render(
            "health_card.html",
            clinic_name=DEFAULT_CLINIC,
            uid=uid,
            card_url=card_url,
            patient_name=card.patient_name or (patient.name if patient else "Patient"),
            patient_id=card.patient_id,
            age=patient.age if patient else "",
            gender=patient.gender if patient else "",
            blood_group=(patient.blood_group or "") if patient else "",
            phone_masked=phone_masked,
            vitals=vitals,
            allergies=allergies,
            history=history,
            prescriptions=prescriptions,
            reading_count=len(readings),
            created_at=card.created_at.strftime("%d %b %Y") if card.created_at else "",
        )
    )


@doctor_router.post("/health-card", include_in_schema=False)
async def api_create_health_card(request: Request):
    """Doctor ke OPD dashboard se — patient ka Universal Health Card banao.

    Body: {patient_id, phone?, patient_name?}
    """
    from src.presentation.opd.routes.opd_routes import _require_opd_session  # lazy

    sess = _require_opd_session(request)
    try:
        body = await request.json()
    except Exception:
        body = {}
    patient_id = str(body.get("patient_id") or "").strip()
    patient_name = str(body.get("patient_name") or "").strip()
    phone = str(body.get("phone") or "").strip()
    if not patient_id:
        return JSONResponse({"ok": False, "error": "patient_id chahiye"}, status_code=400)

    async with async_session_factory() as session:
        patient = None
        prow = await session.execute(
            sa.select(PatientModel).where(PatientModel.patient_id == patient_id).limit(1)
        )
        patient = prow.scalar_one_or_none()
        if patient is not None:
            patient_name = patient_name or patient.name
            phone = phone or patient.phone or ""

        row = await session.execute(
            sa.select(HealthCardModel)
            .where(HealthCardModel.patient_id == patient_id, HealthCardModel.active == 1)
            .order_by(HealthCardModel.created_at.desc())
            .limit(1)
        )
        card = row.scalar_one_or_none()
        if card is None or tk.is_expired(card.expires_at):
            card = HealthCardModel(
                uid=tk.new_token(28),
                patient_id=patient_id,
                patient_name=patient_name or "Patient",
                phone=phone,
                created_by=sess.get("doctor_id") or "",
                expires_at=tk.share_expiry(30),
            )
            session.add(card)
        else:
            card.patient_name = patient_name or card.patient_name
        await session.commit()
        uid = card.uid

    from src.utils.public_url import public_base_url

    url = f"{public_base_url(request)}/card/{uid}"
    message = (
        f"Namaste Doctor, ye {patient_name or 'patient'} ka Universal Health Card hai "
        f"(vitals + prescription history). Read-only link:\n{url}"
    )
    return JSONResponse(
        {
            "ok": True,
            "url": url,
            "uid": uid,
            "patient_id": patient_id,
            "whatsapp_url": "https://wa.me/?text=" + _quote(message),
            "message": message,
        }
    )


def _quote(text: str) -> str:
    from urllib.parse import quote

    return quote(text, safe="")
