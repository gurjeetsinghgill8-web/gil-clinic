"""Universal Health Card routes — portable, shareable patient summary.

PUBLIC (uid = secret, read-only):
    GET /card/{uid}                     → full health card (vitals + prescriptions)

DOCTOR (opd_session cookie):
    POST /opd/api/health-card           → create a card for a patient → shareable link
    POST /opd/api/health-card/revoke    → withdraw a card (GRW-01 / DPDP)
    GET  /opd/api/health-card/access    → who viewed it, and when (GRW-01)

Card = identity + latest vitals + prescription history, QR + WhatsApp share.
Read-only (koi write endpoint nahi); `active=0` ya expiry se revoke hota hai.

**Every view is logged** (GRW-01). DPDP gives a patient the right to know who
accessed their data and the right to withdraw consent; both need a record, and
neither can be reconstructed later. A denied view is logged too — a card being
guessed at repeatedly is exactly the signal an operator needs to see.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
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
    HealthCardAccessModel,
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


async def _log_access(
    session,
    *,
    card: Optional[HealthCardModel],
    uid: str,
    request: Request,
    outcome: str,
    reason: str = "",
) -> None:
    """Record one health-card access attempt (GRW-01).

    Never raises: an audit write must not be able to break the page a patient
    is trying to open. But it also never silently skips on a *denied* attempt,
    because a card being probed repeatedly is the signal worth alerting on.

    The IP is hashed, not stored: it identifies a returning reader for the
    access log without becoming a second piece of personal data to protect.
    """
    try:
        forwarded = request.headers.get("x-forwarded-for", "")
        raw_ip = (forwarded.split(",")[0].strip() if forwarded else
                  (request.client.host if request.client else ""))
        ip_hash = hashlib.sha256(raw_ip.encode()).hexdigest()[:32] if raw_ip else ""
        agent = (request.headers.get("user-agent") or "")[:200]

        # Is the viewer a logged-in clinician? Then the log can name them,
        # which is far more useful than "anonymous" when a patient asks.
        viewer = "anonymous"
        try:
            from src.presentation.opd.routes.opd_routes import _require_opd_session

            sess = _require_opd_session(request)
            role = str(sess.get("role") or sess.get("doctor_id") or "doctor")
            name = str(sess.get("name") or "")
            viewer = f"staff:{role}:{name}".strip(":") if name else f"staff:{role}"
        except Exception:
            viewer = "public-link"

        session.add(
            HealthCardAccessModel(
                card_id=int(card.id) if card is not None else 0,
                uid=str(uid or "")[:80],
                patient_id=str(card.patient_id if card is not None else "")[:30],
                viewer=viewer[:120],
                ip_hash=ip_hash,
                user_agent=agent,
                outcome=outcome,
                denial_reason=reason[:100],
            )
        )
    except Exception as exc:  # pragma: no cover - auditing must never break a view
        logger.debug("health card access log failed: %s", exc)


@router.get("/card/{uid}", include_in_schema=False)
async def health_card_page(request: Request, uid: str):
    async with async_session_factory() as session:
        card = await _card(session, uid)
        if card is None:
            await _log_access(
                session,
                card=None,
                uid=uid,
                request=request,
                outcome="denied",
                reason="not_found_or_revoked",
            )
            await session.commit()
            return _error_page(
                "Health Card kaam nahi kar raha",
                "Link adhoora, expire ya clinic ne band kar diya ho sakta hai. "
                "Kripya naya card maangein.",
                404,
            )
        card.view_count = (card.view_count or 0) + 1
        # GRW-01: the view is recorded at view time. It cannot be
        # reconstructed later, and "who saw my record?" is a patient right.
        await _log_access(
            session, card=card, uid=uid, request=request, outcome="granted"
        )
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


@router.get("/card/{uid}/fhir", include_in_schema=False)
async def health_card_fhir_export(request: Request, uid: str, download: bool = True):
    """ABD-03 — the card holder's record as a FHIR R4 Bundle.

    Reachable from the card link the patient already holds, so "give me my
    records in a portable format" needs no login, no support ticket and no
    ABDM credentials. The same access log applies: a FHIR export is a read of
    the record and is recorded as one.
    """
    from src.infrastructure.abdm.fhir import fhir_bundle, bundle_summary
    from src.presentation.abdm.routes.abdm_routes import _collect_patient_record

    async with async_session_factory() as session:
        card = await _card(session, uid)
        if card is None:
            await _log_access(
                session, card=None, uid=uid, request=request,
                outcome="denied", reason="fhir_not_found_or_revoked",
            )
            await session.commit()
            return _error_page(
                "Health Card kaam nahi kar raha",
                "Link adhoora, expire ya revoke ho chuka hai.",
                404,
            )
        # A FHIR export is a read of the whole record — log it as one.
        await _log_access(
            session, card=card, uid=uid, request=request, outcome="granted"
        )
        card.view_count = (card.view_count or 0) + 1
        await session.commit()
        record = await _collect_patient_record(session, card.patient_id)

    if not record:
        return _error_page(
            "Patient record nahi mila",
            "Is card ka patient record database me nahi mila.",
            404,
        )

    bundle = fhir_bundle(**record)
    count = bundle_summary(bundle)["total"]
    safe_id = "".join(ch for ch in card.patient_id if ch.isalnum() or ch in "-_")
    response = JSONResponse(bundle, media_type="application/fhir+json")
    if download:
        response.headers["Content-Disposition"] = (
            f'attachment; filename="fhir-{safe_id or "patient"}.json"'
        )
    response.headers["X-FHIR-Resources"] = str(count)
    return response


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


# ══════════════════════════════════════════════════════════════════════════
# GRW-01 — Revocation + access log (DPDP)
# ══════════════════════════════════════════════════════════════════════════


@doctor_router.post("/health-card/revoke", include_in_schema=False)
async def api_revoke_health_card(request: Request):
    """Withdraw a shared health card.

    Body: ``{uid}`` or ``{patient_id}``, plus optional ``{reason}``.

    Revoking is recorded — who, when, why — because a consent withdrawal that
    leaves no trace is not auditable, and the clinic may later have to *prove*
    it stopped sharing. Revoking an already-revoked card is a no-op, not an
    error: a patient asking twice should not see a failure.
    """
    from src.presentation.opd.routes.opd_routes import _require_opd_session  # lazy

    sess = _require_opd_session(request)
    try:
        body = await request.json()
    except Exception:
        body = {}
    body = body or {}
    uid = str(body.get("uid") or "").strip()
    patient_id = str(body.get("patient_id") or "").strip()
    reason = str(body.get("reason") or "").strip()[:200]

    if not uid and not patient_id:
        return JSONResponse(
            {"ok": False, "error": "uid ya patient_id chahiye."}, status_code=400
        )

    now = _dt.datetime.now(_dt.timezone.utc)
    revoked_by = str(sess.get("name") or sess.get("role") or "clinic")

    async with async_session_factory() as session:
        stmt = sa.select(HealthCardModel).where(HealthCardModel.active == 1)
        if uid:
            stmt = stmt.where(HealthCardModel.uid == uid)
        else:
            stmt = stmt.where(HealthCardModel.patient_id == patient_id)
        rows = list((await session.execute(stmt)).scalars().all())

        if not rows:
            return JSONResponse(
                {
                    "ok": False,
                    "error": "Koi active health card nahi mila — shayad pehle hi revoke ho chuka hai.",
                },
                status_code=404,
            )

        for card in rows:
            card.active = 0
            card.revoked_at = now
            card.revoked_by = revoked_by
            card.revoked_reason = reason or "patient request"

        affected = len(rows)
        touched_patients = sorted({c.patient_id for c in rows})
        await session.commit()

    return {
        "ok": True,
        "revoked": affected,
        "patient_ids": touched_patients,
        "revoked_by": revoked_by,
        "message": (
            f"{affected} health card revoke ho gaya. "
            "Purana link ab khulega nahi — koi naya link banayein."
        ),
    }


@doctor_router.get("/health-card/access", include_in_schema=False)
async def api_health_card_access(
    request: Request,
    uid: str = "",
    patient_id: str = "",
    limit: int = 50,
):
    """Who opened this health card, and when — the patient's right to know.

    Returns the access log newest-first plus a summary (total views, distinct
    viewers, denied attempts). Denied attempts are included deliberately: a
    card being probed repeatedly is the pattern worth noticing early.
    """
    from src.presentation.opd.routes.opd_routes import _require_opd_session  # lazy

    _require_opd_session(request)

    uid = (uid or "").strip()
    patient_id = (patient_id or "").strip()
    if not uid and not patient_id:
        return JSONResponse(
            {"ok": False, "error": "uid ya patient_id chahiye."}, status_code=400
        )
    try:
        cap = max(1, min(500, int(limit)))
    except (TypeError, ValueError):
        cap = 50

    async with async_session_factory() as session:
        stmt = sa.select(HealthCardAccessModel)
        if uid:
            stmt = stmt.where(HealthCardAccessModel.uid == uid)
        else:
            stmt = stmt.where(HealthCardAccessModel.patient_id == patient_id)
        stmt = stmt.order_by(HealthCardAccessModel.created_at.desc()).limit(cap)
        rows = list((await session.execute(stmt)).scalars().all())

        card = None
        if uid:
            crow = await session.execute(
                sa.select(HealthCardModel).where(HealthCardModel.uid == uid).limit(1)
            )
            card = crow.scalars().first()

    # Distinct viewers, but never echo a full IP — the hash is truncated and is
    # for pattern recognition, not identification.
    viewers = sorted({r.viewer for r in rows if r.viewer})
    granted = sum(1 for r in rows if r.outcome == "granted")
    denied = sum(1 for r in rows if r.outcome != "granted")

    return {
        "ok": True,
        "uid": uid,
        "patient_id": patient_id or (card.patient_id if card is not None else ""),
        "card_active": bool(card.active) if card is not None else None,
        "revoked_at": (
            card.revoked_at.isoformat() if card is not None and card.revoked_at else ""
        ),
        "revoked_reason": card.revoked_reason if card is not None else "",
        "summary": {
            "total_views": len(rows),
            "granted": granted,
            "denied": denied,
            "distinct_viewers": len(viewers),
            "viewers": viewers[:20],
            "view_count_on_card": int(card.view_count or 0) if card is not None else 0,
        },
        "access": [
            {
                "viewer": r.viewer,
                "outcome": r.outcome,
                "denial_reason": r.denial_reason,
                "at": r.created_at.isoformat() if r.created_at else "",
            }
            for r in rows
        ],
        "note": (
            "Sirf access ka record hai — koi clinical content is log me nahi hai. "
            "IP address hash karke rakha jata hai, poora nahi."
        ),
    }
