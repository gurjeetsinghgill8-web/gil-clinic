"""
OPD Routes — Smart OPD Doctor Portal + Admin Portal.

Complete OPD system inside GIL Clinic FastAPI:
  GET  /opd/              → OPD home (redirect to login or dashboard)
  GET  /opd/login          → PIN-based doctor login
  POST /opd/login          → authenticate via PIN
  GET  /opd/logout         → clear session
  GET  /opd/dashboard      → doctor dashboard (new Rx, roster, settings)
  POST /opd/api/generate-rx → AI generate prescription
  POST /opd/api/save-rx    → save prescription
  POST /opd/api/pdf-rx     → generate PDF
  GET  /opd/api/search     → search patients
  GET  /opd/api/drugs      → drug autocomplete
  POST /opd/api/settings   → save settings
  GET  /opd/api/settings   → get settings
  POST /opd/api/templates  → save template
  GET  /opd/api/templates  → get templates
  DELETE /opd/api/templates → delete template
  POST /opd/api/upgrade    → specialty upgrade
  GET  /opd/api/starred    → get starred upgrades
  POST /opd/api/scan       → batch scan upload
  GET  /opd/api/scans      → get pending scans
  POST /opd/api/scan-approve → approve scan entry
  GET  /opd/admin          → admin portal
  POST /opd/api/license    → create license
  GET  /opd/api/licenses   → list licenses
  DELETE /opd/api/license  → delete license
"""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
import os
import re
import uuid
from pathlib import Path
from typing import Optional

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.ext.asyncio import AsyncSession

# ── Session ───────────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "gil-clinic-secret-2024-change-in-prod")
_signer = URLSafeTimedSerializer(SECRET_KEY)
SESSION_COOKIE = "opd_session"
SESSION_MAX_AGE = 60 * 60 * 12  # 12 hours

# Built-in PINs (same as master file)
CHIEF_PIN = os.getenv("OPD_CHIEF_PIN", "5554")
JUNIOR_PIN = os.getenv("OPD_JUNIOR_PIN", "1234")
ADMIN_PIN = os.getenv("OPD_ADMIN_PIN", "1010")

logger = logging.getLogger(__name__)

# ── Jinja2 template engine ───────────────────────────────────────────────────
import jinja2
_TEMPLATES_DIR = Path(__file__).parents[4] / "templates"
_jinja_loader = jinja2.FileSystemLoader(str(_TEMPLATES_DIR))
_jinja_env = jinja2.Environment(loader=_jinja_loader, auto_reload=True)
_jinja_env.cache = {}

def _render(name: str, **context) -> str:
    template = _jinja_env.get_template(name)
    return template.render(**context)

# ── DB session ───────────────────────────────────────────────────────────────
from src.shared.infrastructure.database import async_session_factory, get_session

# ── OPD Models ───────────────────────────────────────────────────────────────
from src.infrastructure.opd.models.opd_models import (
    DrugHistoryModel,
    LabReportModel,
    LicenseModel,
    OpdPrescriptionModel,
    PendingScanModel,
    SettingsModel,
    SpecialtyUpgradeModel,
    TemplateModel,
)

# ── Patient Model (queue system) ─────────────────────────────────────────────
from src.infrastructure.patient.models.patient_model import PatientModel
from src.infrastructure.queue.models.queue_entry_model import QueueEntryModel

# ── AI Engine ────────────────────────────────────────────────────────────────
from src.ai_engine.groq_client import parse_ai_json  # noqa: F401 (legacy parser reuse)
from src.ai_engine.provider_router import (
    ai_config_summary,
    decrypt_key,
    encrypt_key,
    is_key_set,
    mask_value,
    route_chat,
    route_transcribe,
    route_vision,
    sanitize_output,
)
from src.ai_engine.usage import log_ai_usage
from src.ai_engine.prompts import (
    gp_prompt_assistant, gp_prompt_suggest, gp_prompt_followup,
    specialty_prompt, drug_review_prompt, cme_prompt, research_prompt,
)

# ── PDF Generator ────────────────────────────────────────────────────────────
from src.utils.pdf_generator import make_rx_pdf, make_cme_pdf


# ═══════════════════════════════════════════════════════════════════════════════
# Session Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _create_opd_session(role: str, doctor_id: str, name: str = "", lic_info: dict = None) -> str:
    payload = {
        "role": role,
        "doctor_id": doctor_id,
        "name": name,
        "lic_info": lic_info or {},
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    return _signer.dumps(payload)


def _read_opd_session(token: str) -> Optional[dict]:
    try:
        return _signer.loads(token, max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


def _get_opd_session(request: Request) -> Optional[dict]:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        sess = _read_opd_session(token)
        if sess:
            return sess

    # Fallback to staff session if logged in via staff portal (/staff/login)
    staff_token = request.cookies.get("staff_session")
    if staff_token:
        try:
            from src.presentation.staff.routes.staff_routes import _signer as staff_signer
            staff_sess = staff_signer.loads(staff_token, max_age=60 * 60 * 12)
            if staff_sess:
                return {
                    "role": "chief" if staff_sess.get("role") in ("Admin", "Doctor") else "junior",
                    "doctor_id": staff_sess.get("user_id") or "clinic_default",
                    "name": staff_sess.get("name") or "Chief Doctor",
                    "lic_info": {},
                    "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                }
        except Exception:
            pass
    return None


def _require_opd_session(request: Request) -> dict:
    sess = _get_opd_session(request)
    if not sess:
        raise HTTPException(status_code=302, headers={"Location": "/opd/login"})
    return sess


def _has_chief_access(sess: dict) -> bool:
    return sess.get("role") in ("chief", "admin")


# ═══════════════════════════════════════════════════════════════════════════════
# Router
# ═══════════════════════════════════════════════════════════════════════════════

router = APIRouter(prefix="/opd", tags=["Smart OPD"])


# ═══════════════════════════════════════════════════════════════════════════════
# AUTH PAGES
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/", include_in_schema=False)
async def opd_root(request: Request):
    sess = _get_opd_session(request)
    if sess:
        return RedirectResponse("/opd/dashboard")
    return RedirectResponse("/opd/login")


@router.get("/login", include_in_schema=False)
async def opd_login_page(request: Request, error: str = ""):
    sess = _get_opd_session(request)
    if sess:
        return RedirectResponse("/opd/dashboard")
    return HTMLResponse(content=_render("opd/login.html", error=error))


@router.post("/login", include_in_schema=False)
async def opd_login_submit(request: Request, pin: str = Form(...)):
    pin = pin.strip()
    role, doctor_id, name = None, None, ""

    # Built-in PINs
    if pin == CHIEF_PIN:
        role, doctor_id, name = "chief", "clinic_default", "Chief Doctor"
    elif pin == JUNIOR_PIN:
        role, doctor_id, name = "junior", "clinic_default", "Junior Doctor"
    elif pin == ADMIN_PIN:
        role, doctor_id, name = "admin", "admin", "Admin"

    if not role:
        # Check licenses table
        try:
            async with async_session_factory() as session:
                row = await session.execute(
                    sa.select(LicenseModel).where(
                        LicenseModel.pin == pin,
                        LicenseModel.is_active == 1,
                    )
                )
                lic = row.scalar_one_or_none()
                if lic:
                    # Check expiry
                    today = datetime.date.today()
                    try:
                        expiry = datetime.date.fromisoformat(str(lic.expiry_date)[:10])
                        if expiry < today:
                            return HTMLResponse(
                                content=_render("opd/login.html", error="❌ License expired."),
                                status_code=401,
                            )
                    except ValueError:
                        pass
                    role = "licensed"
                    doctor_id = lic.doctor_id
                    name = lic.doctor_name
        except Exception as e:
            logger.error("License check error: %s", e)

    if not role:
        return HTMLResponse(
            content=_render("opd/login.html", error="❌ Invalid PIN. Try again."),
            status_code=401,
        )

    token = _create_opd_session(role=role, doctor_id=doctor_id, name=name)
    resp = RedirectResponse("/opd/dashboard", status_code=303)
    resp.set_cookie(SESSION_COOKIE, token, max_age=SESSION_MAX_AGE, httponly=True, samesite="lax")
    return resp


@router.get("/logout", include_in_schema=False)
async def opd_logout():
    resp = RedirectResponse("/opd/login")
    resp.delete_cookie(SESSION_COOKIE)
    return resp


# ═══════════════════════════════════════════════════════════════════════════════
# DASHBOARD PAGE
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/dashboard", include_in_schema=False)
async def opd_dashboard(request: Request, tab: str = "rx"):
    sess = _require_opd_session(request)
    role = sess.get("role", "junior")
    doctor_id = sess.get("doctor_id", "clinic_default")
    name = sess.get("name", "Doctor")

    # Get settings
    settings_dict = await _get_settings(doctor_id)

    # Get today's patient count
    today_count = 0
    today_revenue = 0
    try:
        async with async_session_factory() as session:
            today_str = datetime.datetime.now().strftime("%Y-%m-%d")
            rows = await session.execute(
                sa.select(sa.func.count(), sa.func.coalesce(sa.func.sum(OpdPrescriptionModel.fee), "0"))
                .where(
                    OpdPrescriptionModel.doctor_id == doctor_id,
                    OpdPrescriptionModel.created_at >= today_str,
                )
            )
            result = rows.one()
            today_count = result[0] or 0
            try:
                today_revenue = sum(int(x) for x in [result[1]] if str(x).isdigit())
            except Exception:
                today_revenue = 0
    except Exception:
        pass

    # Get templates
    templates = await _get_templates(doctor_id)

    return HTMLResponse(content=_render("opd/dashboard.html",
        request=request,
        session=sess,
        role=role,
        doctor_id=doctor_id,
        doc_name=name,
        settings=settings_dict,
        tab=tab,
        today_count=today_count,
        today_revenue=today_revenue,
        is_chief=_has_chief_access(sess),
        templates=templates,
    ))


# ═══════════════════════════════════════════════════════════════════════════════
# API: SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════

_PROVIDER_FIELDS = ["groq_api_key", "openai_api_key", "anthropic_api_key", "deepseek_api_key", "gemini_api_key"]


async def _get_settings(doctor_id: str, masked: bool = True) -> dict:
    """Get settings for a doctor — returns defaults if not found.

    masked=True  → keys returned as '••••••••' for the UI (never raw).
    masked=False → raw stored values (possibly encrypted) for the AI router.
    """
    defaults = {
        "clinic_name": "My Clinic", "doc_name": "Doctor",
        "doc_subtitle": "MBBS", "doc_degree": "", "doc_reg_no": "",
        "doc_email": "", "doc_phone": "", "clinic_address": "",
        "doc_extra_quals": "", "groq_api_key": "",
        "ai_mode": "auto", "ai_model": "",
        "openai_api_key": "", "anthropic_api_key": "",
        "deepseek_api_key": "", "gemini_api_key": "",
        "has_groq": False, "has_openai": False, "has_anthropic": False,
        "has_deepseek": False, "has_gemini": False,
        "clinic_id": "",
        "wa_reception": "", "wa_manager": "", "wa_doctor": "",
        "wa_dietitian": "",
    }
    try:
        async with async_session_factory() as session:
            row = await session.execute(
                sa.select(SettingsModel).where(SettingsModel.doctor_id == doctor_id)
            )
            s = row.scalar_one_or_none()
            if s:
                key_fields = {
                    "groq_api_key": s.groq_api_key,
                    "openai_api_key": getattr(s, "openai_api_key", ""),
                    "anthropic_api_key": getattr(s, "anthropic_api_key", ""),
                    "deepseek_api_key": getattr(s, "deepseek_api_key", ""),
                    "gemini_api_key": getattr(s, "gemini_api_key", ""),
                }
                return {
                    "clinic_name": s.clinic_name,
                    "doc_name": s.doc_name,
                    "doc_subtitle": s.doc_subtitle,
                    "doc_degree": s.doc_degree,
                    "doc_reg_no": s.doc_reg_no,
                    "doc_email": s.doc_email,
                    "doc_phone": s.doc_phone,
                    "clinic_address": s.clinic_address,
                    "doc_extra_quals": s.doc_extra_quals,
                    "groq_api_key": mask_value(key_fields["groq_api_key"]) if masked else key_fields["groq_api_key"],
                    "openai_api_key": mask_value(key_fields["openai_api_key"]) if masked else key_fields["openai_api_key"],
                    "anthropic_api_key": mask_value(key_fields["anthropic_api_key"]) if masked else key_fields["anthropic_api_key"],
                    "deepseek_api_key": mask_value(key_fields["deepseek_api_key"]) if masked else key_fields["deepseek_api_key"],
                    "gemini_api_key": mask_value(key_fields["gemini_api_key"]) if masked else key_fields["gemini_api_key"],
                    "has_groq": is_key_set(key_fields["groq_api_key"]),
                    "has_openai": is_key_set(key_fields["openai_api_key"]),
                    "has_anthropic": is_key_set(key_fields["anthropic_api_key"]),
                    "has_deepseek": is_key_set(key_fields["deepseek_api_key"]),
                    "has_gemini": is_key_set(key_fields["gemini_api_key"]),
                    "ai_mode": getattr(s, "ai_mode", "auto") or "auto",
                    "ai_model": getattr(s, "ai_model", "") or "",
                    "clinic_id": s.clinic_id or "",
                    "wa_reception": s.wa_reception or "",
                    "wa_manager": s.wa_manager or "",
                    "wa_doctor": s.wa_doctor or "",
                    "wa_dietitian": s.wa_dietitian or "",
                }
    except Exception:
        pass
    return defaults


async def _ai_settings_for(doctor_id: str) -> dict:
    """Settings dict with RAW (encrypted) key values — for provider_router."""
    return await _get_settings(doctor_id, masked=False)


_MASK_PLACEHOLDERS = {"", "••••••••", "********", "****"}


@router.get("/api/settings", include_in_schema=False)
async def api_get_settings(request: Request):
    sess = _require_opd_session(request)
    settings = await _get_settings(sess["doctor_id"])
    return settings


@router.post("/api/settings", include_in_schema=False)
async def api_save_settings(request: Request):
    sess = _require_opd_session(request)
    doctor_id = sess["doctor_id"]
    try:
        body = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON"}

    try:
        async with async_session_factory() as session:
            row = await session.execute(
                sa.select(SettingsModel).where(SettingsModel.doctor_id == doctor_id)
            )
            s = row.scalar_one_or_none()
            if not s:
                s = SettingsModel(doctor_id=doctor_id)
                session.add(s)

            for key in ["clinic_name", "doc_name", "doc_subtitle", "doc_degree",
                         "doc_reg_no", "doc_email", "doc_phone", "clinic_address",
                         "doc_extra_quals",
                         "wa_reception", "wa_manager", "wa_doctor", "wa_dietitian"]:
                if key in body:
                    setattr(s, key, str(body[key]))

            # AI mode + optional model override
            if "ai_mode" in body:
                mode = str(body["ai_mode"]).strip().lower()
                if mode not in ("auto", "puter", "off"):
                    mode = "auto"
                setattr(s, "ai_mode", mode)
            if "ai_model" in body:
                setattr(s, "ai_model", str(body["ai_model"]).strip())

            # Provider keys — encrypt at rest. Mask/empty values are ignored
            # (keeps the existing key); clear_<provider> flags remove a key.
            for fld in _PROVIDER_FIELDS:
                provider = fld.replace("_api_key", "")
                if body.get(f"clear_{provider}"):
                    setattr(s, fld, "")
                    continue
                val = str(body.get(fld, "") or "").strip()
                if not val or val in _MASK_PLACEHOLDERS or val.startswith("enc:v1:"):
                    continue
                setattr(s, fld, encrypt_key(val))

            await session.commit()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════════
# API: AI PROVIDER CONFIG + USAGE (Puter gateway & metering)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/api/ai-config", include_in_schema=False)
async def api_ai_config(request: Request):
    """Public (secret-free) AI config for the browser gateway."""
    sess = _require_opd_session(request)
    settings = await _ai_settings_for(sess["doctor_id"])
    summary = ai_config_summary(settings)
    summary["usage_this_month"] = await _usage_count(sess["doctor_id"], days=30)
    summary["usage_today"] = await _usage_count(sess["doctor_id"], days=1)
    summary["puter_connected"] = True  # client verifies with puter.auth locally
    return summary


async def _usage_count(doctor_id: str, days: int = 30) -> int:
    try:
        from src.infrastructure.opd.models.ai_usage_model import AIUsageModel
        async with async_session_factory() as session:
            since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
            result = await session.execute(
                sa.select(sa.func.count()).select_from(AIUsageModel).where(
                    AIUsageModel.doctor_id == doctor_id,
                    AIUsageModel.created_at >= since,
                )
            )
            return int(result.scalar() or 0)
    except Exception:
        return 0


@router.post("/api/ai-usage", include_in_schema=False)
async def api_ai_usage_post(request: Request):
    """Browser gateway logs Puter-side AI calls here for per-clinic metering."""
    sess = _require_opd_session(request)
    try:
        body = await request.json()
    except Exception:
        body = {}
    await log_ai_usage(
        clinic_id=body.get("clinic_id") or sess.get("clinic_id"),
        doctor_id=sess["doctor_id"],
        feature=str(body.get("feature") or "browser-ai")[:50],
        provider=str(body.get("provider") or "puter")[:40],
        model=str(body.get("model") or "")[:100],
        success=bool(body.get("success", True)),
        error=str(body.get("error") or "")[:500],
    )
    return {"ok": True}


@router.get("/api/ai-usage", include_in_schema=False)
async def api_ai_usage_get(request: Request):
    sess = _require_opd_session(request)
    return {
        "usage_this_month": await _usage_count(sess["doctor_id"], days=30),
        "usage_today": await _usage_count(sess["doctor_id"], days=1),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# API: PATIENTS (Search + List)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/api/search", include_in_schema=False)
async def api_search_patients(request: Request, q: str = Query("")):
    sess = _require_opd_session(request)
    doctor_id = sess["doctor_id"]
    q = q.strip()
    if not q:
        return []

    results = []
    try:
        async with async_session_factory() as session:
            # Search in OPD prescriptions
            like_pattern = f"%{q}%"
            rows = await session.execute(
                sa.select(OpdPrescriptionModel)
                .where(
                    OpdPrescriptionModel.doctor_id == doctor_id,
                    sa.or_(
                        OpdPrescriptionModel.patient_name.ilike(like_pattern),
                        OpdPrescriptionModel.phone.ilike(like_pattern),
                    ),
                )
                .order_by(OpdPrescriptionModel.created_at.desc())
                .limit(50)
            )
            seen = set()
            rx_rows = list(rows.scalars())

            # Batch fetch patient info (age, gender) for OPD prescription patients
            rx_patient_ids = list(set(r.patient_id for r in rx_rows if r.patient_id))
            patient_map = {}
            if rx_patient_ids:
                p_rows = await session.execute(
                    sa.select(PatientModel).where(PatientModel.patient_id.in_(rx_patient_ids))
                )
                for p in p_rows.scalars():
                    patient_map[p.patient_id] = p

            for row in rx_rows:
                key = f"{row.patient_name}_{row.phone}"
                if key not in seen:
                    seen.add(key)
                    pt = patient_map.get(row.patient_id)
                    results.append({
                        "patient_name": row.patient_name,
                        "phone": row.phone,
                        "patient_id": row.patient_id,
                        "visit_id": row.visit_id or "",
                        "age": pt.age if pt else "",
                        "gender": pt.gender if pt else "",
                        "date": row.created_at.strftime("%Y-%m-%d %H:%M") if row.created_at else "",
                        "vitals": row.vitals,
                        "complaints": row.complaints,
                        "medicines": row.medicines,
                        "diagnosis": row.diagnosis,
                        "investigations": row.investigations,
                        "fee": row.fee,
                        "source": "prescription",
                    })

            # Also search queue patients
            if q.isdigit() or len(q) > 3:
                p_rows = await session.execute(
                    sa.select(PatientModel)
                    .where(
                        sa.or_(
                            PatientModel.name.ilike(like_pattern),
                            PatientModel.phone.ilike(like_pattern),
                            PatientModel.patient_id.ilike(like_pattern),
                        )
                    )
                    .limit(20)
                )
                for row in p_rows.scalars():
                    key = f"{row.name}_{row.phone}"
                    if key not in seen:
                        seen.add(key)
                        # Fetch latest queue entry for complaints & visit_id
                        latest_q = await session.execute(
                            sa.select(QueueEntryModel)
                            .where(
                                sa.or_(
                                    QueueEntryModel.patient_id == row.patient_id,
                                    QueueEntryModel.patient_uuid == str(row.id),
                                )
                            )
                            .order_by(QueueEntryModel.created_at.desc())
                            .limit(1)
                        )
                        q_entry = latest_q.scalar_one_or_none()
                        results.append({
                            "patient_name": row.name,
                            "phone": row.phone,
                            "patient_id": row.patient_id,
                            "patient_uuid": str(row.id),
                            "age": row.age,
                            "gender": row.gender,
                            "complaints": q_entry.notes if q_entry else (row.reception_inquiry or ""),
                            "visit_id": q_entry.visit_id if q_entry else "",
                            "source": "queue",
                        })
    except Exception as e:
        logger.error("Search error: %s", e)

    return results[:20]


@router.get("/api/queue-patients", include_in_schema=False)
async def api_queue_patients(request: Request):
    """Get waiting OPD patients for the doctor to pick from queue."""
    sess = _require_opd_session(request)
    try:
        async with async_session_factory() as session:
            today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d")
            rows = await session.execute(
                sa.select(
                    QueueEntryModel, PatientModel
                )
                .select_from(QueueEntryModel)
                .outerjoin(
                    PatientModel,
                    QueueEntryModel.patient_uuid == sa.cast(PatientModel.id, sa.String)
                )
                .where(
                    QueueEntryModel.service_code == "OPD",
                    QueueEntryModel.status == "WAITING",
                    QueueEntryModel.visit_id.like(f"VIS-{today}-%"),
                )
                .order_by(QueueEntryModel.token_number.asc())
                .limit(30)
            )
            patients = []
            for q_entry, p_entry in rows:
                wait_mins = 0
                if q_entry.created_at:
                    now_naive = datetime.datetime.now()
                    created = q_entry.created_at
                    if created.tzinfo is not None:
                        created = created.replace(tzinfo=None)
                    delta = now_naive - created
                    wait_mins = int(delta.total_seconds() / 60)
                patients.append({
                    "patient_id": q_entry.patient_id,
                    "patient_uuid": q_entry.patient_uuid,
                    "patient_name": q_entry.patient_name,
                    "token_number": q_entry.token_number,
                    "visit_id": q_entry.visit_id,
                    "complaints": q_entry.notes or "",
                    "age": p_entry.age if p_entry else "",
                    "gender": p_entry.gender if p_entry else "",
                    "phone": p_entry.phone if p_entry else "",
                    "wait_minutes": wait_mins,
                    "created_at": q_entry.created_at.strftime("%H:%M") if q_entry.created_at else "",
                    "total_visits": p_entry.total_visits if p_entry else 0,
                })
            return {"ok": True, "patients": patients}
    except Exception as e:
        logger.error("Queue patients error: %s", e)
        return {"ok": False, "patients": [], "error": str(e)}


@router.get("/api/patient-history", include_in_schema=False)
async def api_patient_history(request: Request, patient_id: str = Query(""), patient_name: str = Query("")):
    """Get patient visit history — past prescriptions and registration info."""
    sess = _require_opd_session(request)
    doctor_id = sess["doctor_id"]
    try:
        async with async_session_factory() as session:
            result = {}
            # Get patient from registration
            if patient_id:
                p_row = await session.execute(
                    sa.select(PatientModel).where(PatientModel.patient_id == patient_id)
                )
                p = p_row.scalar_one_or_none()
                if p:
                    result["patient"] = {
                        "age": p.age, "gender": p.gender, "phone": p.phone,
                        "total_visits": p.total_visits or 0,
                        "last_visit_at": p.last_visit_at.strftime("%Y-%m-%d %H:%M") if p.last_visit_at else "",
                        "medical_history": p.medical_history or [],
                    }
            # Get past prescriptions
            like_pattern = f"%{patient_name or ''}%"
            rx_rows = await session.execute(
                sa.select(OpdPrescriptionModel)
                .where(
                    OpdPrescriptionModel.doctor_id == doctor_id,
                    sa.or_(
                        OpdPrescriptionModel.patient_name.ilike(like_pattern),
                        OpdPrescriptionModel.patient_id == patient_id,
                    ) if patient_id else OpdPrescriptionModel.patient_name.ilike(like_pattern),
                )
                .order_by(OpdPrescriptionModel.created_at.desc())
                .limit(5)
            )
            result["past_rx"] = [
                {
                    "date": r.created_at.strftime("%Y-%m-%d") if r.created_at else "",
                    "complaints": r.complaints,
                    "diagnosis": r.diagnosis,
                    "medicines": r.medicines,
                    "vitals": r.vitals,
                    "advice": r.advice,
                    "investigations": r.investigations,
                }
                for r in rx_rows.scalars()
            ]
            return {"ok": True, **result}
    except Exception as e:
        logger.error("Patient history error: %s", e)
        return {"ok": False, "error": str(e)}


@router.get("/api/patient-progress", include_in_schema=False)
async def api_patient_progress(request: Request, patient_name: str = Query(""), patient_id: str = Query("")):
    """Get structured vitals trend data for patient progress charts.
    Returns parsed BP/sugar/weight values from last 10 visits."""
    sess = _require_opd_session(request)
    doctor_id = sess["doctor_id"]
    try:
        async with async_session_factory() as session:
            like_pattern = f"%{patient_name or ''}%"
            rx_rows = await session.execute(
                sa.select(OpdPrescriptionModel)
                .where(
                    OpdPrescriptionModel.doctor_id == doctor_id,
                    sa.or_(
                        OpdPrescriptionModel.patient_name.ilike(like_pattern),
                        OpdPrescriptionModel.patient_id == patient_id,
                    ) if patient_id else OpdPrescriptionModel.patient_name.ilike(like_pattern),
                )
                .where(OpdPrescriptionModel.vitals != "")
                .order_by(OpdPrescriptionModel.created_at.desc())
                .limit(10)
            )
            trend = []
            for r in rx_rows.scalars():
                v = str(r.vitals or "").lower()
                entry = {
                    "date": r.created_at.strftime("%d-%b") if r.created_at else "",
                    "vitals": r.vitals or "",
                }
                # Parse BP
                bp = re.search(r"(\d{2,3})\s*/\s*(\d{2,3})", v)
                if bp:
                    entry["sys"] = int(bp.group(1))
                    entry["dia"] = int(bp.group(2))
                # Parse Sugar
                sg = re.search(r"(?:rbs|fbs|pp|sugar|bs|glucose|random)\s*[:=]?\s*(\d{2,4})", v)
                if sg:
                    entry["sugar"] = int(sg.group(1))
                # Parse Weight
                wt = re.search(r"(?:wt|weight)\s*[:=]?\s*(\d{2,3})", v)
                if wt:
                    entry["weight"] = int(wt.group(1))
                # Parse Pulse/HR
                hr = re.search(r"(?:hr|pulse|pr)\s*[:=]?\s*(\d{2,3})", v)
                if hr:
                    entry["hr"] = int(hr.group(1))
                trend.append(entry)
            return {"ok": True, "trend": trend}
    except Exception as e:
        logger.error("Patient progress error: %s", e)
        return {"ok": False, "trend": [], "error": str(e)}


@router.get("/api/roster", include_in_schema=False)
async def api_roster(request: Request, filter: str = Query("today")):
    sess = _require_opd_session(request)
    doctor_id = sess["doctor_id"]

    results = []
    try:
        async with async_session_factory() as session:
            query = sa.select(OpdPrescriptionModel).where(
                OpdPrescriptionModel.doctor_id == doctor_id
            )

            today = datetime.date.today()
            if filter == "today":
                query = query.where(
                    sa.func.date(OpdPrescriptionModel.created_at) == today
                )
            elif filter == "yesterday":
                yesterday = today - datetime.timedelta(days=1)
                query = query.where(
                    sa.func.date(OpdPrescriptionModel.created_at) == yesterday
                )
            elif filter == "last5":
                five_days_ago = today - datetime.timedelta(days=5)
                query = query.where(
                    sa.func.date(OpdPrescriptionModel.created_at) >= five_days_ago
                )

            query = query.order_by(OpdPrescriptionModel.created_at.desc()).limit(200)
            rows = await session.execute(query)
            for row in rows.scalars():
                results.append({
                    "id": str(row.id),
                    "patient_name": row.patient_name,
                    "phone": row.phone,
                    "vitals": row.vitals,
                    "complaints": row.complaints,
                    "medicines": row.medicines,
                    "diagnosis": row.diagnosis,
                    "investigations": row.investigations,
                    "fee": row.fee,
                    "date": row.created_at.strftime("%Y-%m-%d %H:%M") if row.created_at else "",
                    "is_followup": row.is_followup,
                })
    except Exception as e:
        logger.error("Roster error: %s", e)

    # Compute stats
    total_fee = 0
    for r in results:
        try:
            total_fee += int(r.get("fee", 0) or 0)
        except Exception:
            pass

    return {
        "patients": results,
        "total": len(results),
        "total_fee": total_fee,
        "avg_fee": total_fee // max(len(results), 1),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# API: DRUG AUTOCOMPLETE
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/api/drugs", include_in_schema=False)
async def api_drug_suggestions(request: Request, q: str = Query("")):
    sess = _require_opd_session(request)
    doctor_id = sess["doctor_id"]
    q = q.strip()
    if not q or len(q) < 2:
        return []

    try:
        async with async_session_factory() as session:
            rows = await session.execute(
                sa.select(DrugHistoryModel)
                .where(
                    DrugHistoryModel.doctor_id == doctor_id,
                    DrugHistoryModel.drug_name.ilike(f"%{q}%"),
                )
                .order_by(DrugHistoryModel.use_count.desc())
                .limit(10)
            )
            return [
                f"{r.drug_name} {r.dose}".strip()
                for r in rows.scalars()
            ]
    except Exception:
        return []


async def _learn_drugs(rx_text: str, doctor_id: str):
    """Parse Rx text and store each drug in drug_history for autocomplete."""
    if not rx_text or not doctor_id:
        return
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        async with async_session_factory() as session:
            for line in rx_text.split("\n"):
                line = line.strip()
                # Match patterns like: "1. Tab. Metformin 500mg - BD - After meals - 30 Days"
                m = re.match(
                    r"\d+\.\s*(Tab\.|Cap\.|Syp\.|Inj\.|Drop\.|Cream\.|Gel\.)?\s*"
                    r"([A-Za-z][A-Za-z0-9\s\-]+?)"
                    r"(?:\s+(\d+\s*(?:mg|mcg|ml|g|IU|units)))?"
                    r"(?:\s+-\s+(.+?))?(?:\s+-\s+(.+?))?(?:\s+-\s*(\d+\s*Days?))?$",
                    line, re.IGNORECASE,
                )
                if m:
                    drug = (m.group(2) or "").strip()
                    dose = (m.group(3) or "").strip()
                    if drug and len(drug) > 2:
                        existing = await session.execute(
                            sa.select(DrugHistoryModel).where(
                                DrugHistoryModel.doctor_id == doctor_id,
                                DrugHistoryModel.drug_name == drug,
                                DrugHistoryModel.dose == dose,
                            )
                        )
                        dh = existing.scalar_one_or_none()
                        if dh:
                            dh.use_count = (dh.use_count or 0) + 1
                            dh.last_used = now_str
                        else:
                            session.add(DrugHistoryModel(
                                doctor_id=doctor_id,
                                drug_name=drug,
                                dose=dose,
                                use_count=1,
                                last_used=now_str,
                            ))
            await session.commit()
    except Exception as e:
        logger.error("Learn drugs error: %s", e)


# ═══════════════════════════════════════════════════════════════════════════════
# API: PRESCRIPTION
# ═══════════════════════════════════════════════════════════════════════════════

def _puter_text_or_none(body: dict) -> Optional[str]:
    """Return browser-side Puter AI text if present in the request body."""
    for k in ("puter_result", "puter_ocr_result"):
        v = body.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


async def _log_ai(settings: dict, doctor_id: str, feature: str, provider: str,
                  model: str = "", success: bool = True, usage: Optional[dict] = None,
                  error: str = "") -> None:
    usage = usage or {}
    await log_ai_usage(
        clinic_id=settings.get("clinic_id"),
        doctor_id=doctor_id,
        feature=feature,
        provider=provider,
        model=model,
        success=success,
        prompt_tokens=int(usage.get("prompt_tokens") or 0),
        completion_tokens=int(usage.get("completion_tokens") or 0),
        error=error,
    )


@router.post("/api/generate-rx", include_in_schema=False)
async def api_generate_rx(request: Request):
    sess = _require_opd_session(request)
    doctor_id = sess["doctor_id"]

    try:
        body = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON"}

    patient_name = body.get("patient_name", "")
    vitals = body.get("vitals", "")
    complaints = body.get("complaints", "")
    past_context = body.get("past_context", "")
    doctor_medicines = body.get("doctor_medicines", "")
    allow_suggest_drugs = body.get("allow_suggest_drugs", False)
    include_investigations = body.get("include_investigations", True)

    if not patient_name:
        return {"ok": False, "error": "Patient name required"}

    settings = await _ai_settings_for(doctor_id)

    # Choose prompt mode based on whether AI should suggest drugs
    if allow_suggest_drugs:
        prompt = gp_prompt_suggest(
            patient_name=patient_name,
            vitals=vitals,
            notes=complaints,
            doc_name=settings.get("doc_name", "Doctor"),
            doc_degree=settings.get("doc_degree", ""),
            past_context=past_context,
        )
    else:
        prompt = gp_prompt_assistant(
            patient_name=patient_name,
            vitals=vitals,
            notes=complaints,
            doc_name=settings.get("doc_name", "Doctor"),
            doc_degree=settings.get("doc_degree", ""),
            doc_hospital=settings.get("clinic_name", ""),
            past_context=past_context,
            doctor_medicines=doctor_medicines,
        )

    # ── Browser-side Puter result (user-pays) or server-side BYOK routing ──
    puter_text = _puter_text_or_none(body)
    if puter_text:
        result, provider, model_used, usage = sanitize_output(puter_text), "puter", settings.get("ai_model") or "puter", {}
    else:
        routed = route_chat(settings, [prompt], feature="generate-rx", temp=0.3, max_tokens=4000)
        if routed.get("puter_needed"):
            return {"ok": False, "code": routed["code"], "prompt": routed["prompt"], "model": routed["model"]}
        result, provider, model_used, usage = routed.get("text") or "", routed.get("provider") or "", routed.get("model") or "", routed.get("usage") or {}
        if not result:
            await _log_ai(settings, doctor_id, "generate-rx", provider or "none", model_used, success=False, error=routed.get("error") or "")
            return {"ok": False, "error": routed.get("error") or "AI Generation failed. Clinic owner: Settings → AI Provider."}

    await _log_ai(settings, doctor_id, "generate-rx", provider, model_used, success=True, usage=usage)

    # Post-process: strip Investigations section if doctor unchecked the toggle
    if not include_investigations:
        result = re.sub(r'\n\s*Investigations:.*?(?=\n\s*(?:Advice|Follow-up|$))', '', result, flags=re.DOTALL | re.IGNORECASE)
        result = re.sub(r'\n\s*Investigations needed:.*?(?=\n\s*(?:Advice|Follow-up|$))', '', result, flags=re.DOTALL | re.IGNORECASE)

    return {"ok": True, "prescription": result, "mode": "suggest" if allow_suggest_drugs else "assistant", "provider": provider}


@router.post("/api/generate-followup-rx", include_in_schema=False)
async def api_generate_followup_rx(request: Request):
    """Follow-up Rx — uses past prescription context with CONTINUE/MODIFY/STOP markers."""
    sess = _require_opd_session(request)
    doctor_id = sess["doctor_id"]

    try:
        body = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON"}

    patient_name = body.get("patient_name", "")
    vitals = body.get("vitals", "")
    complaints = body.get("complaints", "")
    past_diagnoses = body.get("past_diagnoses", "")
    past_medicines = body.get("past_medicines", "")
    past_advice = body.get("past_advice", "")

    if not patient_name:
        return {"ok": False, "error": "Patient name required"}

    settings = await _ai_settings_for(doctor_id)

    prompt = gp_prompt_followup(
        patient_name=patient_name,
        vitals=vitals,
        complaints=complaints,
        doc_name=settings.get("doc_name", "Doctor"),
        doc_degree=settings.get("doc_degree", ""),
        past_diagnoses=past_diagnoses,
        past_medicines=past_medicines,
        past_advice=past_advice,
    )

    puter_text = _puter_text_or_none(body)
    if puter_text:
        result, provider, model_used, usage = sanitize_output(puter_text), "puter", settings.get("ai_model") or "puter", {}
    else:
        routed = route_chat(settings, [prompt], feature="generate-followup-rx", temp=0.3, max_tokens=4000)
        if routed.get("puter_needed"):
            return {"ok": False, "code": routed["code"], "prompt": routed["prompt"], "model": routed["model"]}
        result, provider, model_used, usage = routed.get("text") or "", routed.get("provider") or "", routed.get("model") or "", routed.get("usage") or {}
        if not result:
            await _log_ai(settings, doctor_id, "generate-followup-rx", provider or "none", model_used, success=False, error=routed.get("error") or "")
            return {"ok": False, "error": routed.get("error") or "AI Generation failed. Clinic owner: Settings → AI Provider."}

    await _log_ai(settings, doctor_id, "generate-followup-rx", provider, model_used, success=True, usage=usage)

    return {"ok": True, "prescription": result, "mode": "followup", "provider": provider}


@router.post("/api/optimize-rx", include_in_schema=False)
async def api_optimize_rx(request: Request):
    """Optimize existing Rx into crisp numbered format — removes paragraphs."""
    sess = _require_opd_session(request)
    doctor_id = sess["doctor_id"]

    try:
        body = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON"}

    prescription = body.get("prescription", "")
    if not prescription.strip():
        return {"ok": False, "error": "No prescription to optimize"}

    settings = await _ai_settings_for(doctor_id)

    from src.ai_engine.prompts import optimize_prompt
    prompt = optimize_prompt(
        patient_name=body.get("patient_name", ""),
        vitals=body.get("vitals", ""),
        complaints=body.get("complaints", ""),
        current_rx=prescription,
        doctor_medicines=body.get("doctor_medicines", ""),
        include_investigations=body.get("include_investigations", True),
    )

    puter_text = _puter_text_or_none(body)
    if puter_text:
        result, provider, model_used, usage = sanitize_output(puter_text), "puter", settings.get("ai_model") or "puter", {}
    else:
        routed = route_chat(settings, [prompt], feature="optimize-rx", temp=0.2, max_tokens=3000)
        if routed.get("puter_needed"):
            return {"ok": False, "code": routed["code"], "prompt": routed["prompt"], "model": routed["model"]}
        result, provider, model_used, usage = routed.get("text") or "", routed.get("provider") or "", routed.get("model") or "", routed.get("usage") or {}
        if not result:
            await _log_ai(settings, doctor_id, "optimize-rx", provider or "none", model_used, success=False, error=routed.get("error") or "")
            return {"ok": False, "error": routed.get("error") or "Optimization failed. Clinic owner: Settings → AI Provider."}

    await _log_ai(settings, doctor_id, "optimize-rx", provider, model_used, success=True, usage=usage)

    return {"ok": True, "prescription": result, "provider": provider}


@router.post("/api/clinical-support", include_in_schema=False)
async def api_clinical_support(request: Request):
    """Clinical Decision Support — DDx, missed Ix, algorithm, referral. Doctor reference only."""
    sess = _require_opd_session(request)
    doctor_id = sess["doctor_id"]

    try:
        body = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON"}

    settings = await _ai_settings_for(doctor_id)

    from src.ai_engine.prompts import clinical_support_prompt
    prompt = clinical_support_prompt(
        patient_name=body.get("patient_name", ""),
        vitals=body.get("vitals", ""),
        complaints=body.get("complaints", ""),
        current_diagnosis=body.get("diagnosis", ""),
        current_medicines=body.get("medicines", ""),
        current_investigations=body.get("investigations", ""),
    )

    puter_text = _puter_text_or_none(body)
    if puter_text:
        result, provider, model_used, usage = sanitize_output(puter_text), "puter", settings.get("ai_model") or "puter", {}
    else:
        routed = route_chat(settings, [prompt], feature="clinical-support", temp=0.3, max_tokens=3000)
        if routed.get("puter_needed"):
            return {"ok": False, "code": routed["code"], "prompt": routed["prompt"], "model": routed["model"]}
        result, provider, model_used, usage = routed.get("text") or "", routed.get("provider") or "", routed.get("model") or "", routed.get("usage") or {}
        if not result:
            await _log_ai(settings, doctor_id, "clinical-support", provider or "none", model_used, success=False, error=routed.get("error") or "")
            return {"ok": False, "error": routed.get("error") or "Clinical support generation failed."}

    await _log_ai(settings, doctor_id, "clinical-support", provider, model_used, success=True, usage=usage)

    return {"ok": True, "support": result, "provider": provider}


@router.post("/api/drug-review", include_in_schema=False)
async def api_drug_review(request: Request):
    sess = _require_opd_session(request)
    if not _has_chief_access(sess):
        return {"ok": False, "error": "Only Chief can access drug review."}

    try:
        body = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON"}

    vitals = body.get("vitals", "")
    prescription = body.get("prescription", "")

    settings = await _ai_settings_for(sess["doctor_id"])

    prompt = drug_review_prompt(vitals=vitals, prescription=prescription)

    puter_text = _puter_text_or_none(body)
    if puter_text:
        result, provider, model_used, usage = sanitize_output(puter_text), "puter", settings.get("ai_model") or "puter", {}
    else:
        routed = route_chat(settings, [prompt], feature="drug-review", temp=0.3, max_tokens=4000)
        if routed.get("puter_needed"):
            return {"ok": False, "code": routed["code"], "prompt": routed["prompt"], "model": routed["model"]}
        result, provider, model_used, usage = routed.get("text") or "", routed.get("provider") or "", routed.get("model") or "", routed.get("usage") or {}
        if not result:
            await _log_ai(settings, sess["doctor_id"], "drug-review", provider or "none", model_used, success=False, error=routed.get("error") or "")
            return {"ok": False, "error": routed.get("error") or "Drug review failed."}

    await _log_ai(settings, sess["doctor_id"], "drug-review", provider, model_used, success=True, usage=usage)
    return {"ok": True, "review": result, "provider": provider}


@router.post("/api/transcribe", include_in_schema=False)
async def api_transcribe(request: Request):
    """Transcribe audio complaints — clinic BYOK providers, Puter (browser), or system fallback."""
    sess = _require_opd_session(request)
    doctor_id = sess["doctor_id"]

    settings = await _ai_settings_for(doctor_id)

    try:
        form = await request.form()
        puter_result = str(form.get("puter_result") or "").strip()
        if puter_result:
            await _log_ai(settings, doctor_id, "transcribe", "puter", settings.get("ai_model") or "puter", success=True)
            return {"ok": True, "text": puter_result}

        audio_file = form.get("audio")
        if not audio_file:
            return {"ok": False, "error": "No audio file"}
        audio_bytes = await audio_file.read()
        filename = audio_file.filename or "audio.webm"

        routed = route_transcribe(settings, audio_bytes, filename, feature="transcribe")
        if routed.get("puter_needed"):
            return {"ok": False, "code": routed["code"]}
        text = routed.get("text") or ""
        if text:
            await _log_ai(settings, doctor_id, "transcribe", routed.get("provider") or "", routed.get("model") or "", success=True)
            return {"ok": True, "text": text}
        await _log_ai(settings, doctor_id, "transcribe", routed.get("provider") or "none", routed.get("model") or "", success=False, error=routed.get("error") or "")
        return {"ok": False, "error": routed.get("error") or "Transcription failed. Clinic owner: Settings → AI Provider."}
    except Exception as e:
        logger.error("Transcribe error: %s", e)
        return {"ok": False, "error": str(e)}


@router.post("/api/cme", include_in_schema=False)
async def api_cme(request: Request):
    sess = _require_opd_session(request)
    if not _has_chief_access(sess):
        return {"ok": False, "error": "Only Chief can access CME."}

    try:
        body = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON"}

    topic = body.get("topic", "")
    if not topic:
        return {"ok": False, "error": "Topic required."}

    settings = await _ai_settings_for(sess["doctor_id"])

    prompt = cme_prompt(topic)

    puter_text = _puter_text_or_none(body)
    if puter_text:
        result, provider, model_used, usage = sanitize_output(puter_text), "puter", settings.get("ai_model") or "puter", {}
    else:
        routed = route_chat(settings, [prompt], feature="cme", temp=0.3, max_tokens=4000)
        if routed.get("puter_needed"):
            return {"ok": False, "code": routed["code"], "prompt": routed["prompt"], "model": routed["model"]}
        result, provider, model_used, usage = routed.get("text") or "", routed.get("provider") or "", routed.get("model") or "", routed.get("usage") or {}
        if not result:
            await _log_ai(settings, sess["doctor_id"], "cme", provider or "none", model_used, success=False, error=routed.get("error") or "")
            return {"ok": False, "error": routed.get("error") or "CME generation failed."}

    await _log_ai(settings, sess["doctor_id"], "cme", provider, model_used, success=True, usage=usage)
    return {"ok": True, "content": result, "provider": provider}


# ═══════════════════════════════════════════════════════════════════════════════
# API: SAVE PRESCRIPTION
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/api/save-rx", include_in_schema=False)
async def api_save_rx(request: Request):
    sess = _require_opd_session(request)
    doctor_id = sess["doctor_id"]

    try:
        body = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON"}

    patient_name = body.get("patient_name", "").strip()
    phone = body.get("phone", "").strip()
    vitals = body.get("vitals", "")
    fee = body.get("fee", "0")
    complaints = body.get("complaints", "")
    diagnosis = body.get("diagnosis", "")
    medicines = body.get("medicines", "")
    investigations = body.get("investigations", "")
    advice = body.get("advice", "")
    follow_up = body.get("follow_up", "")
    patient_id = body.get("patient_id", "")
    visit_id = body.get("visit_id", "")

    if not patient_name:
        return {"ok": False, "error": "Patient name required"}

    try:
        async with async_session_factory() as session:
            # Generate patient_id for direct OPD registrations
            if not patient_id:
                today_str = datetime.datetime.now().strftime("%Y%m%d")
                short_id = uuid.uuid4().hex[:6].upper()
                patient_id = f"OPD-{today_str}-{short_id}"

            rx = OpdPrescriptionModel(
                patient_id=patient_id,
                visit_id=visit_id or None,
                patient_name=patient_name,
                phone=phone,
                doctor_id=doctor_id,
                vitals=vitals,
                complaints=complaints,
                diagnosis=diagnosis,
                medicines=medicines,
                investigations=investigations,
                advice=advice,
                follow_up=follow_up,
                fee=fee,
                ai_generated=body.get("ai_generated", False),
            )
            session.add(rx)
            await session.commit()

            # Auto-learn drug names
            await _learn_drugs(medicines, doctor_id)

            # Update queue entry status if visit_id provided
            if visit_id:
                try:
                    await session.execute(
                        sa.update(QueueEntryModel)
                        .where(QueueEntryModel.visit_id == visit_id)
                        .values(status="COMPLETED", updated_at=datetime.datetime.now(datetime.timezone.utc))
                    )
                    await session.commit()
                except Exception:
                    pass

            return {"ok": True, "id": str(rx.id)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════════
# API: PDF GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/api/pdf-rx", include_in_schema=False)
async def api_pdf_rx(request: Request):
    sess = _require_opd_session(request)
    doctor_id = sess["doctor_id"]

    try:
        body = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON"}

    settings = await _get_settings(doctor_id)

    pdf_bytes = make_rx_pdf(
        pt_name=body.get("patient_name", "Patient"),
        vitals=body.get("vitals", ""),
        rx_text=body.get("prescription", ""),
        investigations=body.get("investigations", ""),
        specialty_label=body.get("specialty_label", ""),
        clinic_name=settings.get("clinic_name", "My Clinic"),
        doc_name=settings.get("doc_name", "Doctor"),
        doc_degree=settings.get("doc_degree", "MBBS"),
        doc_subtitle=settings.get("doc_subtitle", ""),
        doc_reg_no=settings.get("doc_reg_no", ""),
        doc_phone=settings.get("doc_phone", ""),
        doc_email=settings.get("doc_email", ""),
        clinic_address=settings.get("clinic_address", ""),
        doc_extra_quals=settings.get("doc_extra_quals", ""),
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="Rx_{body.get("patient_name", "Patient")}.pdf"',
        },
    )


@router.post("/api/pdf-cme", include_in_schema=False)
async def api_pdf_cme(request: Request):
    sess = _require_opd_session(request)
    if not _has_chief_access(sess):
        return {"ok": False, "error": "Only Chief access."}

    try:
        body = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON"}

    pdf_bytes = make_cme_pdf(
        topic=body.get("topic", "CME"),
        content=body.get("content", ""),
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="CME_{body.get("topic", "Topic")}.pdf"',
        },
    )


# ═══════════════════════════════════════════════════════════════════════════════
# API: TEMPLATES
# ═══════════════════════════════════════════════════════════════════════════════

async def _get_templates(doctor_id: str, category: str = None) -> dict:
    """Get templates grouped by category."""
    try:
        async with async_session_factory() as session:
            query = sa.select(TemplateModel).where(
                TemplateModel.doctor_id == doctor_id
            )
            if category:
                query = query.where(TemplateModel.category == category)
            rows = await session.execute(query)
            result = {}
            for r in rows.scalars():
                cat = r.category or "Rx"
                if cat not in result:
                    result[cat] = {}
                result[cat][r.name] = r.content
            return result
    except Exception:
        return {}


@router.get("/api/templates", include_in_schema=False)
async def api_get_templates(request: Request, category: str = Query(None)):
    sess = _require_opd_session(request)
    return await _get_templates(sess["doctor_id"], category)


@router.post("/api/templates", include_in_schema=False)
async def api_save_template(request: Request):
    sess = _require_opd_session(request)
    doctor_id = sess["doctor_id"]

    try:
        body = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON"}

    category = body.get("category", "Rx")
    name = body.get("name", "").strip()
    content = body.get("content", "").strip()

    if not name:
        return {"ok": False, "error": "Template name required"}

    try:
        async with async_session_factory() as session:
            existing = await session.execute(
                sa.select(TemplateModel).where(
                    TemplateModel.doctor_id == doctor_id,
                    TemplateModel.name == name,
                )
            )
            tmpl = existing.scalar_one_or_none()
            if tmpl:
                tmpl.content = content
                tmpl.category = category
            else:
                session.add(TemplateModel(
                    doctor_id=doctor_id,
                    category=category,
                    name=name,
                    content=content,
                ))
            await session.commit()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.delete("/api/templates", include_in_schema=False)
async def api_delete_template(request: Request, name: str = Query(...)):
    sess = _require_opd_session(request)
    doctor_id = sess["doctor_id"]

    try:
        async with async_session_factory() as session:
            await session.execute(
                sa.delete(TemplateModel).where(
                    TemplateModel.doctor_id == doctor_id,
                    TemplateModel.name == name,
                )
            )
            await session.commit()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════════
# API: SPECIALTY UPGRADE
# ═══════════════════════════════════════════════════════════════════════════════

SPECIALTIES = {
    "❤️ Cardiology": {
        "persona": "Senior Interventional Cardiologist (DM Cardiology, FACC, FESC)",
        "guidelines": "AHA/ACC 2023 Hypertension Guidelines, ESC 2024 Heart Failure Guidelines, ACC/AHA 2023 Chronic Coronary Disease, ESC 2024 Atrial Fibrillation, Braunwald's Heart Disease 12th Ed, CSI India CVD Guidelines",
        "primary_source": "American Heart Association / American College of Cardiology (AHA/ACC) + European Society of Cardiology (ESC)",
        "indian_brands": "Telma (Telmisartan), Cilacar (Cilnidipine), Rozavel (Rosuvastatin), Ecosprin (Aspirin), Clopilet (Clopidogrel), Metolar (Metoprolol), Lanoxin (Digoxin), Lasix (Furosemide), Aldactone (Spironolactone), Cardivas (Carvedilol)",
        "focus": "Hypertension, Heart Failure, IHD, Arrhythmias, Valvular Heart Disease, Dyslipidemia",
    },
    "🦴 Orthopedics": {
        "persona": "Senior Orthopedic Surgeon (MS Ortho, FACS, FIAS)",
        "guidelines": "AAOS 2023 Clinical Practice Guidelines, NICE Musculoskeletal Guidelines NG226, IOA (Indian Orthopedic Association) Guidelines, AO Trauma Foundation, Oxford Textbook of Orthopedics",
        "primary_source": "American Academy of Orthopaedic Surgeons (AAOS) + Indian Orthopedic Association (IOA)",
        "indian_brands": "Calpol (Paracetamol), Voveran (Diclofenac), Myospaz (Chlorzoxazone), Shelcal (Calcium+VitD3), Gemcal (Calcium Citrate), Rejoin (Glucosamine), Naprosyn (Naproxen), Flexon (Ibuprofen+Paracetamol)",
        "focus": "Osteoarthritis, Low Back Pain, Joint Pain, Fractures, Sprains, Osteoporosis, Cervical/Lumbar Spondylosis",
    },
    "🫁 Pulmonology": {
        "persona": "Senior Pulmonologist (DM Pulmonary Medicine, FCCP)",
        "guidelines": "GOLD 2024 COPD Strategy, GINA 2024 Asthma Guidelines, ATS/IDSA CAP Guidelines 2023, RNTCP/NTEP India TB Guidelines, BTS Pleural Disease, Fletcher's Respiratory Medicine",
        "primary_source": "Global Initiative for Chronic Obstructive Lung Disease (GOLD) + Global Initiative for Asthma (GINA) + ATS/IDSA",
        "indian_brands": "Foracort (Formoterol+Budesonide), Duolin (Levosalbutamol+Ipratropium), Montek (Montelukast), Allegra (Fexofenadine), Deriphyllin (Etofylline+Theophylline), Pulmoclear (Acetylcysteine), Ciplox (Ciprofloxacin)",
        "focus": "Asthma, COPD, Tuberculosis, Pneumonia, ILD, Allergic Rhinitis, Bronchiectasis",
    },
    "👶 Pediatrics": {
        "persona": "Senior Pediatrician (MD Pediatrics, FIAP, NNF certified)",
        "guidelines": "IAP 2024 Immunization Schedule, WHO IMCI Guidelines 2023, IAP Growth Charts 2024, NNF Neonatal Care Protocols, AAP Clinical Practice Guidelines, Nelson Textbook of Pediatrics 22nd Ed",
        "primary_source": "Indian Academy of Pediatrics (IAP) + World Health Organization (WHO) + American Academy of Pediatrics (AAP)",
        "indian_brands": "P-250 (Paracetamol), Azee (Azithromycin), Taxim-O (Cefixime), Maxtra (Phenylephrine+CPM), Zincolife (Zinc), Enterogermina (Probiotic), Aristozyme (Digestive enzymes), Nutrolin-B (Multivitamin)",
        "focus": "Fever, URTI, Diarrhea, Growth Monitoring, Immunization, Nutritional Deficiencies, Neonatal care",
    },
    "🩸 Diabetology": {
        "persona": "Senior Diabetologist (DM Endocrinology, CDE certified)",
        "guidelines": "ADA Standards of Care 2024, RSSDI Clinical Practice Guidelines 2024, AACE/ACE Comprehensive Diabetes Algorithm 2024, IDF Global Diabetes Guidelines, Joslin's Diabetes Deskbook",
        "primary_source": "American Diabetes Association (ADA) + Research Society for Study of Diabetes in India (RSSDI)",
        "indian_brands": "Glycomet (Metformin), Glimiprex (Glimepiride), Janumet (Sitagliptin+Metformin), Forxiga (Dapagliflozin), Istavel (Sitagliptin), Volix (Voglibose), Lantus (Insulin Glargine), Humalog (Insulin Lispro)",
        "focus": "Type 2 DM, Type 1 DM, Insulin Management, HbA1c Control, Diabetic Complications, Prediabetes, Metabolic Syndrome",
    },
    "🧠 Neurology": {
        "persona": "Senior Neurologist (DM Neurology, FIAN, FAAN)",
        "guidelines": "AAN Clinical Practice Guidelines 2024, ESO Stroke Guidelines 2024, IHS Migraine Classification ICHD-3, ILAE Epilepsy Guidelines, IAN (Indian Academy of Neurology) Guidelines, Bradley's Neurology 8th Ed",
        "primary_source": "American Academy of Neurology (AAN) + European Stroke Organisation (ESO) + Indian Academy of Neurology (IAN)",
        "indian_brands": "Eptoin (Phenytoin), Valparin (Valproate), Lobazam (Clobazam), Levipil (Levetiracetam), Tryptomer (Amitriptyline), Sibelium (Flunarizine), Strocit (Citicoline), Nootropil (Piracetam)",
        "focus": "Headache/Migraine, Epilepsy, Stroke/TIA, Neuropathy, Vertigo, Parkinsonism, Dementia",
    },
    "👩‍⚕️ Gynecology": {
        "persona": "Senior Gynecologist (MS OBG, FICOG, FOGSI)",
        "guidelines": "FOGSI Clinical Protocols 2024, RCOG Green-top Guidelines 2024, WHO Reproductive Health Guidelines, ACOG Practice Bulletins, Novak's Gynecology 16th Ed",
        "primary_source": "Federation of Obstetric & Gynaecological Societies of India (FOGSI) + Royal College of O&G (RCOG)",
        "indian_brands": "Primolut-N (Norethisterone), Meprate (Medroxyprogesterone), Ovares (Clomiphene), Dronis (Drospirenone+EE), Pause (Estrogen), Folicare (Folic Acid), Shecal (Calcium), M2-Tone (Herbal PCOS)",
        "focus": "PCOD/PCOS, Menstrual Disorders, Menopause, Pregnancy care, Contraception, Vaginal Infections, Fibroid Uterus",
    },
    "👁️ Ophthalmology": {
        "persona": "Senior Ophthalmologist (MS Ophthalmology, FICO, FAICO)",
        "guidelines": "AAO Preferred Practice Patterns 2024, ICO Clinical Guidelines, AIOS (All India Ophthalmological Society) Protocols, NEI Diabetic Retinopathy Guidelines, Yanoff & Duker's Ophthalmology 6th Ed",
        "primary_source": "American Academy of Ophthalmology (AAO) + International Council of Ophthalmology (ICO) + AIOS",
        "indian_brands": "Refresh Tears (Carboxymethylcellulose), Lotepred (Loteprednol), Moxicip (Moxifloxacin), Opticrom (Cromoglycate), Careprost (Bimatoprost), Dorzox (Dorzolamide), Ocurest (Ketorolac)",
        "focus": "Refractive Errors, Cataract, Glaucoma, Conjunctivitis, Diabetic Retinopathy, Dry Eye, Computer Vision Syndrome",
    },
    "👂 ENT": {
        "persona": "Senior ENT Surgeon (MS ENT, FACS, FAOI)",
        "guidelines": "AAO-HNS Clinical Practice Guidelines 2024, AOI (Association of Otolaryngologists of India) Protocols, IACO Guidelines, Cummings Otolaryngology 7th Ed, Scott-Brown's Otorhinolaryngology",
        "primary_source": "American Academy of Oto-HNS (AAO-HNS) + Association of Otolaryngologists of India (AOI)",
        "indian_brands": "Sinarest (Paracetamol+Phenylephrine), Otrivin (Xylometazoline), Allegra (Fexofenadine), Cetzine (Cetirizine), Candid Mouth Paint (Clotrimazole), Betadine Gargle (Povidone-Iodine), Otorex (Ofloxacin ear drops)",
        "focus": "Sinusitis, Allergic Rhinitis, Tonsillitis, Otitis Media, Hearing Loss, Vertigo, Epistaxis, Pharyngitis",
    },
    "🩺 Gastroenterology": {
        "persona": "Senior Gastroenterologist (DM Gastroenterology, FASGE, ISG)",
        "guidelines": "ACG Clinical Guidelines 2024, AGA Clinical Practice Updates 2024, ISG (Indian Society of Gastroenterology) Protocols, INASL Liver Disease Guidelines, Sleisenger & Fordtran's GI Disease 11th Ed",
        "primary_source": "American College of Gastroenterology (ACG) + Indian Society of Gastroenterology (ISG) + INASL",
        "indian_brands": "Pan (Pantoprazole), Razo (Rabeprazole), Ocid (Omeprazole), Domstal (Domperidone), Rifagut (Rifaximin), Udiliv (Ursodeoxycholic Acid), Librax (Chlordiazepoxide+Clidinium), Cremaffin (Liquid Paraffin)",
        "focus": "GERD, IBS, Hepatitis, Fatty Liver/NAFLD, Peptic Ulcer, Constipation, Pancreatitis, Cirrhosis",
    },
    "🧬 Dermatology": {
        "persona": "Senior Dermatologist (MD Dermatology, IADVL, FAAD)",
        "guidelines": "IADVL Clinical Guidelines 2024, AAD Clinical Guidelines 2024, BAD Guidelines, EDF Guidelines, Fitzpatrick's Dermatology 9th Ed, Rook's Textbook of Dermatology",
        "primary_source": "Indian Association of Dermatologists Venereologists & Leprologists (IADVL) + American Academy of Dermatology (AAD)",
        "indian_brands": "T-Bact (Mupirocin), Fucidin (Fusidic Acid), Lobate (Clobetasol), Candid-B (Clotrimazole+Beclomethasone), Acnestar (Benzoyl Peroxide), Isotroin (Isotretinoin), Cetaphil (Moisturizer), Calosoft (Calamine)",
        "focus": "Acne, Eczema/Atopic Dermatitis, Psoriasis, Fungal Infections, Urticaria, Vitiligo, Hair Loss, Contact Dermatitis",
    },
    "🧪 Endocrinology": {
        "persona": "Senior Endocrinologist (DM Endocrinology, FACE, ISE)",
        "guidelines": "AACE/ACE Clinical Guidelines 2024, Endocrine Society Guidelines 2024, RSSDI Diabetes Guidelines, ISE (Indian Society of Endocrinology) Protocols, Williams Textbook of Endocrinology 15th Ed",
        "primary_source": "American Association of Clinical Endocrinology (AACE) + Endocrine Society + Indian Society of Endocrinology (ISE)",
        "indian_brands": "Eltroxin (Levothyroxine), Thyronorm (Thyroxine), Neomercazole (Carbimazole), Glycomet (Metformin), Shelcal CT (Calcium+Calcitriol), Gemcal Plus (Calcium+VitD3), Bonmax (Ibandronic Acid)",
        "focus": "Hypothyroidism, Hyperthyroidism, PCOD, Osteoporosis, Vitamin D Deficiency, Obesity, Pituitary Disorders",
    },
    "🫀 Rheumatology": {
        "persona": "Senior Rheumatologist (DM Rheumatology, FACR, IRA)",
        "guidelines": "ACR Clinical Practice Guidelines 2024, EULAR Recommendations 2024, IRA (Indian Rheumatology Association) Guidelines, BSR Guidelines, Kelley & Firestein's Textbook of Rheumatology 11th Ed",
        "primary_source": "American College of Rheumatology (ACR) + European League Against Rheumatism (EULAR) + IRA",
        "indian_brands": "Saaz (Sulfasalazine), HCQ (Hydroxychloroquine), Folvite (Folic Acid), Omnacortil (Prednisolone), Etoshine (Etoricoxib), Feburic (Febuxostat), Zyloric (Allopurinol), Shelcal (Calcium+VitD3)",
        "focus": "Rheumatoid Arthritis, SLE/Lupus, Gout, Ankylosing Spondylitis, Fibromyalgia, Osteoarthritis, Vasculitis",
    },
    "🧠 Psychiatry": {
        "persona": "Senior Psychiatrist (MD Psychiatry, MIPS, FIPA)",
        "guidelines": "APA Practice Guidelines 2024, IPS (Indian Psychiatric Society) Clinical Guidelines, WHO mhGAP 2.0, NICE Mental Health Guidelines, Kaplan & Sadock's Psychiatry 12th Ed",
        "primary_source": "American Psychiatric Association (APA) + Indian Psychiatric Society (IPS) + WHO mhGAP",
        "indian_brands": "Pexep (Paroxetine), Nexito (Escitalopram), Zapiz (Clonazepam), Petril (Lorazepam), Oleanz (Olanzapine), Sulpitac (Amisulpride), Modalert (Modafinil), Inspiral (Methylphenidate)",
        "focus": "Depression, Anxiety Disorders, Insomnia, Panic Attacks, OCD, Bipolar Disorder, Schizophrenia, Stress Management",
    },
    "🩺 Urology": {
        "persona": "Senior Urologist (MS Urology, MCh, FUSI)",
        "guidelines": "AUA Clinical Guidelines 2024, EAU Guidelines 2024, USI (Urological Society of India) Protocols, Campbell-Walsh Urology 12th Ed, NICE Urology Guidelines",
        "primary_source": "American Urological Association (AUA) + European Association of Urology (EAU) + USI",
        "indian_brands": "Urimax (Tamsulosin), Alfusin (Alfuzosin), Soliten (Solifenacin), Niftran (Nitrofurantoin), Veltam-F (Tamsulosin+Finasteride), Cital (Potassium Citrate), Zupar (Tolterodine), Ciprobid (Ciprofloxacin)",
        "focus": "BPH/Prostate Enlargement, Renal Stones, UTI, Incontinence, Erectile Dysfunction, Hematuria, Phimosis",
    },
    "🩺 Nephrology": {
        "persona": "Senior Nephrologist (DM Nephrology, FISN, FASN)",
        "guidelines": "KDIGO 2024 Clinical Practice Guidelines, ISN Guidelines, RSI (Renal Society of India) Protocols, Brenner & Rector's The Kidney 11th Ed, NICE CKD Guidelines",
        "primary_source": "Kidney Disease Improving Global Outcomes (KDIGO) + International Society of Nephrology (ISN) + RSI",
        "indian_brands": "Cilacar (Cilnidipine), Arkamin (Clonidine), Shelcal (Calcium Carbonate), Phostat (Calcium Acetate), Erypro (Erythropoietin), Orofer-XT (Iron), Nephrocap (Multivitamin renal), Renolog (Sodium Bicarbonate)",
        "focus": "CKD, Dialysis Management, Hypertension, Electrolyte Imbalance, AKI, Nephrotic Syndrome, Renal Stones Prevention",
    },
    "🩺 Oncology": {
        "persona": "Senior Medical Oncologist (DM Oncology, ECMO, ISMPO)",
        "guidelines": "NCCN Clinical Practice Guidelines 2024, ASCO Guidelines 2024, ICMR Cancer Guidelines India, ISMPO (Indian Society of Medical & Paediatric Oncology) Protocols, DeVita's Cancer 12th Ed",
        "primary_source": "National Comprehensive Cancer Network (NCCN) + American Society of Clinical Oncology (ASCO) + ICMR India",
        "indian_brands": "Capecitabine, Tamoxifen, Letrozole, Imatinib, Methotrexate, Ondem (Ondansetron), Wysolone (Prednisolone), Folvite (Folic Acid), Orofer (Iron), Gemcitabine, Paclitaxel",
        "focus": "Cancer Screening, Chemotherapy Management, Palliative Care, Breast Cancer, Lung Cancer, GI Cancers, Lymphoma, Leukemia",
    },
    "🩺 General Surgery": {
        "persona": "Senior General Surgeon (MS Surgery, FACS, FIAGES)",
        "guidelines": "ACS Surgery Guidelines 2024, AMASI (Association of Minimal Access Surgeons of India) Protocols, IAGES Guidelines, Sabiston Textbook of Surgery 21st Ed, Schwartz's Principles of Surgery 11th Ed",
        "primary_source": "American College of Surgeons (ACS) + AMASI + Indian Association of Gastrointestinal Endo-Surgeons (IAGES)",
        "indian_brands": "Taxim (Cefotaxime), Metrogyl (Metronidazole), Pan (Pantoprazole), Emset (Ondansetron), Dynapar (Diclofenac injection), Neosporin (Polymyxin ointment), T-Bact (Mupirocin), Ciprodac (Ciprofloxacin)",
        "focus": "Hernia, Appendicitis, Gallstones/Cholecystitis, Abscess Drainage, Fistula, Piles, Wound Care, Minor Surgical Procedures",
    },
}


@router.post("/api/upgrade", include_in_schema=False)
async def api_specialty_upgrade(request: Request):
    sess = _require_opd_session(request)
    doctor_id = sess["doctor_id"]

    try:
        body = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON"}

    patient_name = body.get("patient_name", "")
    vitals = body.get("vitals", "")
    original_rx = body.get("prescription", "")
    specialty_keys = body.get("specialties", [])

    if not patient_name or not original_rx or not specialty_keys:
        return {"ok": False, "error": "Patient name, prescription, and specialties required."}

    settings = await _ai_settings_for(doctor_id)

    results = []
    puter_text = _puter_text_or_none(body)
    puter_spec = str(body.get("puter_specialty") or "")

    # ── Save a browser-side Puter result for its specialty, if any ──
    if puter_text and puter_spec:
        up_id = None
        try:
            async with async_session_factory() as session:
                upgrade = SpecialtyUpgradeModel(
                    doctor_id=doctor_id,
                    date=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                    patient_name=patient_name,
                    vitals=vitals,
                    original_rx=original_rx,
                    specialty=puter_spec,
                    upgraded_rx=sanitize_output(puter_text),
                    evidence="AI Generated (Puter)",
                )
                session.add(upgrade)
                await session.commit()
                up_id = upgrade.id
        except Exception:
            up_id = None
        results.append({"specialty": puter_spec, "content": sanitize_output(puter_text), "id": up_id})
        await _log_ai(settings, doctor_id, "specialty-upgrade", "puter", settings.get("ai_model") or "puter", success=True)

    for key in specialty_keys:
        if puter_text and puter_spec and key == puter_spec:
            continue  # already saved above
        spec_data = SPECIALTIES.get(key)
        is_custom = spec_data is None
        if is_custom:
            # Custom specialty (e.g. "Sports Medicine") — generic expert persona
            spec_data = {}

        prompt = specialty_prompt(
            patient_name=patient_name,
            vitals=vitals,
            current_rx=original_rx,
            specialty_name=key,
            specialty_data=spec_data,
            custom_name=key if is_custom else "",
        )

        routed = route_chat(settings, [prompt], feature="specialty-upgrade", temp=0.2, max_tokens=4000)
        if routed.get("puter_needed"):
            return {"ok": False, "code": routed["code"], "prompt": routed["prompt"],
                    "model": routed["model"], "puter_specialty": key, "partial_results": results}
        result_text = routed.get("text") or ""
        provider = routed.get("provider") or ""
        model_used = routed.get("model") or ""
        usage = routed.get("usage") or {}
        if not result_text:
            await _log_ai(settings, doctor_id, "specialty-upgrade", provider or "none", model_used, success=False, error=routed.get("error") or "")
            continue
        await _log_ai(settings, doctor_id, "specialty-upgrade", provider, model_used, success=True, usage=usage)

        # Save upgrade
        try:
            async with async_session_factory() as session:
                upgrade = SpecialtyUpgradeModel(
                    doctor_id=doctor_id,
                    date=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                    patient_name=patient_name,
                    vitals=vitals,
                    original_rx=original_rx,
                    specialty=key,
                    upgraded_rx=result_text,
                    evidence="AI Generated",
                )
                session.add(upgrade)
                await session.commit()
                up_id = upgrade.id
        except Exception:
            up_id = None

        results.append({
            "specialty": key,
            "content": result_text,
            "id": up_id,
        })

    return {"ok": True, "results": results}


@router.get("/api/starred", include_in_schema=False)
async def api_get_starred(request: Request):
    sess = _require_opd_session(request)
    doctor_id = sess["doctor_id"]

    try:
        async with async_session_factory() as session:
            rows = await session.execute(
                sa.select(SpecialtyUpgradeModel)
                .where(
                    SpecialtyUpgradeModel.doctor_id == doctor_id,
                    SpecialtyUpgradeModel.is_starred == 1,
                )
                .order_by(SpecialtyUpgradeModel.id.desc())
            )
            results = []
            for r in rows.scalars():
                results.append({
                    "id": r.id,
                    "date": r.date,
                    "patient_name": r.patient_name,
                    "vitals": r.vitals,
                    "original_rx": r.original_rx,
                    "specialty": r.specialty,
                    "upgraded_rx": r.upgraded_rx,
                    "evidence": r.evidence,
                    "star_note": r.star_note,
                })
            return results
    except Exception as e:
        logger.error("Starred error: %s", e)
        return []


@router.post("/api/star", include_in_schema=False)
async def api_star_upgrade(request: Request):
    sess = _require_opd_session(request)
    try:
        body = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON"}

    upgrade_id = body.get("id")
    note = body.get("note", "")

    if not upgrade_id:
        return {"ok": False, "error": "Upgrade ID required"}

    try:
        async with async_session_factory() as session:
            await session.execute(
                sa.update(SpecialtyUpgradeModel)
                .where(SpecialtyUpgradeModel.id == upgrade_id)
                .values(is_starred=1, star_note=note)
            )
            await session.commit()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════════
# API: PENDING SCANS (Batch Scan Queue)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/api/scan", include_in_schema=False)
async def api_upload_scan(request: Request):
    sess = _require_opd_session(request)
    doctor_id = sess["doctor_id"]

    try:
        body = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON"}

    image_b64 = body.get("image", "")

    if not image_b64:
        return {"ok": False, "error": "No image data"}

    try:
        async with async_session_factory() as session:
            scan = PendingScanModel(
                doctor_id=doctor_id,
                uploaded_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                image_b64=image_b64,
                status="pending",
            )
            session.add(scan)
            await session.commit()

            return {"ok": True, "id": scan.id}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/api/scans", include_in_schema=False)
async def api_get_scans(request: Request):
    sess = _require_opd_session(request)
    doctor_id = sess["doctor_id"]

    try:
        async with async_session_factory() as session:
            rows = await session.execute(
                sa.select(PendingScanModel)
                .where(
                    PendingScanModel.doctor_id == doctor_id,
                    PendingScanModel.status == "pending",
                )
                .order_by(PendingScanModel.id.desc())
                .limit(50)
            )
            results = []
            for r in rows.scalars():
                results.append({
                    "id": r.id,
                    "uploaded_at": r.uploaded_at,
                    "image_b64": r.image_b64,
                    "patient_name": r.patient_name,
                    "phone": r.phone,
                    "vitals": r.vitals,
                    "complaints": r.complaints,
                    "medicines": r.medicines,
                    "investigations": r.investigations,
                    "status": r.status,
                })
            return results
    except Exception as e:
        logger.error("Get scans error: %s", e)
        return []


@router.post("/api/scan-ai", include_in_schema=False)
async def api_scan_ai(request: Request):
    """Process uploaded handwritten prescription image via multi-provider Vision OCR.

    BYOK: clinic's own vision keys (Gemini → OpenAI → Groq → Anthropic) — clinic pays.
    Puter mode: browser calls puter.ai.img2txt (user-pays) and re-posts the text.
    """
    sess = _require_opd_session(request)
    doctor_id = sess["doctor_id"]

    try:
        body = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON"}

    image_b64 = body.get("image", "")
    if not image_b64:
        return {"ok": False, "error": "No image provided"}

    settings = await _ai_settings_for(doctor_id)

    puter_text = _puter_text_or_none(body)
    if puter_text:
        parsed = parse_ai_json(puter_text)
        await _log_ai(settings, doctor_id, "scan-ai", "puter", settings.get("ai_model") or "puter", success=True)
        return {"ok": True, "parsed": parsed, "raw": puter_text, "provider": "puter"}

    try:
        import base64
        import io
        from PIL import Image

        # Remove data:image/... header if present
        if "," in image_b64:
            image_b64 = image_b64.split(",", 1)[1]

        image_bytes = base64.b64decode(image_b64)
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode not in ('RGB', 'L'):
            img = img.convert('RGB')

        routed = route_vision(settings, img, feature="scan-ai")
        if routed.get("puter_needed"):
            return {"ok": False, "code": routed["code"], "prompt": routed["prompt"], "model": routed["model"]}

        raw_text = routed.get("text") or ""
        provider = routed.get("provider") or ""
        if not raw_text:
            await _log_ai(settings, doctor_id, "scan-ai", provider or "none", routed.get("model") or "", success=False, error=routed.get("error") or "")
            return {"ok": False, "error": routed.get("error") or "No text extracted from image",
                    "hint": "Clinic owner: Settings → AI Provider → add a vision key (Gemini/OpenAI/Groq)."}

        await _log_ai(settings, doctor_id, "scan-ai", provider, routed.get("model") or "", success=True, usage=routed.get("usage") or {})
        parsed = parse_ai_json(raw_text)
        return {"ok": True, "parsed": parsed, "raw": raw_text, "provider": provider}
    except Exception as e:
        logger.error("Scan AI processing error: %s", e)
        return {"ok": False, "error": f"AI scan failed: {str(e)}"}


@router.post("/api/handwriting-ocr", include_in_schema=False)
async def api_handwriting_ocr(request: Request):
    """Process handwritten prescription from Digital Ink Writing Pad.

    BYOK: clinic's own vision keys — clinic pays. Puter mode: browser-side
    puter.ai.img2txt (user-pays) → structure hop → re-post result.
    """
    sess = _require_opd_session(request)
    doctor_id = sess["doctor_id"]

    try:
        body = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON"}

    image_b64 = body.get("image", "")
    if not image_b64:
        return {"ok": False, "error": "No handwriting image provided"}

    settings = await _ai_settings_for(doctor_id)

    def _finish_parsed(parsed: dict, raw: str, provider: str, success: bool = True):
        return {
            "ok": True,
            "parsed": parsed,
            "raw": raw,
            "ocr_method": provider,
        }

    try:
        import base64 as b64_mod
        import io as io_mod
        from PIL import Image

        # ── Browser-side Puter hops ──
        # 1) puter_ocr_result: raw OCR text from puter.ai.img2txt
        # 2) puter_result: structured JSON from a puter.ai.chat structuring hop
        puter_structured = body.get("puter_result")
        puter_ocr = body.get("puter_ocr_result")
        if puter_structured or puter_ocr:
            raw_text = str(puter_structured or puter_ocr or "").strip()
            parsed = parse_ai_json(raw_text)
            if puter_structured or (parsed and isinstance(parsed, dict) and any(parsed.values())):
                await _log_ai(settings, doctor_id, "handwriting-ocr", "puter", settings.get("ai_model") or "puter", success=True)
                return _finish_parsed(parsed, raw_text, "puter")
            # Plain OCR text — ask the browser to structure it via Puter chat
            struct_prompt = _struct_prompt(raw_text)
            return {"ok": False, "code": "PUTER_CHAT", "prompt": struct_prompt, "model": settings.get("ai_model") or "gpt-4o-mini"}

        # ── Server-side path: decode image ──
        img_b64_clean = image_b64
        if "," in img_b64_clean:
            img_b64_clean = img_b64_clean.split(",", 1)[1]

        image_bytes = b64_mod.b64decode(img_b64_clean)
        img = Image.open(io_mod.BytesIO(image_bytes))

        # Normalise to RGB
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        # ── Route through clinic's own vision providers ──
        routed = route_vision(settings, img, feature="handwriting-ocr")
        if routed.get("puter_needed"):
            return {"ok": False, "code": routed["code"], "prompt": routed["prompt"], "model": routed["model"]}

        raw_text = routed.get("text") or ""
        provider = routed.get("provider") or ""
        model_used = routed.get("model") or ""

        if not raw_text or len(raw_text.strip()) < 5:
            await _log_ai(settings, doctor_id, "handwriting-ocr", provider or "none", model_used, success=False, error=routed.get("error") or "")
            return {
                "ok": True,
                "parsed": {},
                "raw": "",
                "ocr_method": provider,
                "error_hint": "no_text_found",
                "message": "Could not read handwriting. Tips: 1) Write clearly with dark pen on white background  2) Ensure good lighting  3) Hold camera steady  4) Clinic owner: Settings → AI Provider → add a vision key."
            }

        parsed = parse_ai_json(raw_text)

        # Plain OCR text (no JSON) — structure it with the clinic's text provider
        if not parsed or not isinstance(parsed, dict) or not any(parsed.values()):
            struct_prompt = _struct_prompt(raw_text)
            struct_routed = route_chat(settings, [struct_prompt], feature="handwriting-ocr-struct", temp=0.1, max_tokens=1500)
            if struct_routed.get("puter_needed"):
                await _log_ai(settings, doctor_id, "handwriting-ocr", provider, model_used, success=True)
                return {"ok": False, "code": struct_routed["code"], "prompt": struct_routed["prompt"], "model": struct_routed["model"]}
            ai_text = struct_routed.get("text") or ""
            parsed = parse_ai_json(ai_text) if ai_text else {}
            raw_text = ai_text or raw_text
            await _log_ai(settings, doctor_id, "handwriting-ocr", struct_routed.get("provider") or provider, struct_routed.get("model") or model_used, success=True, usage=struct_routed.get("usage") or {})
        else:
            await _log_ai(settings, doctor_id, "handwriting-ocr", provider, model_used, success=True, usage=routed.get("usage") or {})

        if not parsed or not isinstance(parsed, dict) or not any(parsed.values()):
            return {
                "ok": True,
                "parsed": {},
                "raw": raw_text,
                "ocr_method": provider,
                "error_hint": "parse_failed",
                "message": f"OCR read text ({provider}) but could not parse structure. Raw text returned."
            }

        return _finish_parsed(parsed, raw_text, provider)

    except Exception as e:
        logger.error("Handwriting OCR error: %s", e)
        return {"ok": False, "error": f"Handwriting recognition failed: {str(e)}"}


def _struct_prompt(raw_text: str) -> str:
    """Structuring prompt for plain OCR text → Rx JSON."""
    return f"""Convert this OCR-extracted text from a doctor's handwritten prescription into structured JSON.

OCR TEXT:
{raw_text}

Return ONLY valid JSON:
{{"vitals":"","complaints":"","diagnosis":"WORKING DIAGNOSIS: think as the world's best internal medicine physician + graduate medical doctor of all subjects. NEVER copy symptoms as diagnosis — write ranked MEDICAL CONDITIONS (most likely first, (suspected)/(rule out) where uncertain, one-line reasoning each). Insufficient data -> ? Query <Condition> — needs <test>.","medicines":"numbered list with drug+dose+freq+duration","investigations":"comma-separated","advice":"","follow_up":""}}"""




@router.post("/api/save-rx", include_in_schema=False)
async def api_save_rx(request: Request):
    """Save OPD Prescription to database and auto-update queue status for inter-department sync."""
    sess = _require_opd_session(request)
    doctor_id = sess["doctor_id"]

    try:
        body = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON"}

    patient_name = body.get("patient_name", "").strip()
    if not patient_name:
        return {"ok": False, "error": "Patient name required"}

    try:
        async with async_session_factory() as session:
            rx = OpdPrescriptionModel(
                patient_name=patient_name,
                phone=body.get("phone", ""),
                doctor_id=doctor_id,
                vitals=body.get("vitals", ""),
                complaints=body.get("complaints", ""),
                medicines=body.get("medicines", ""),
                investigations=body.get("investigations", ""),
                diagnosis=body.get("diagnosis", ""),
                fee=body.get("fee", "0"),
                ai_generated=body.get("ai_generated", False),
            )
            session.add(rx)

            # Auto-update queue entry for OPD to COMPLETED / REPORT_READY for inter-department sync
            visit_id = body.get("visit_id") or body.get("patient_id")
            if visit_id:
                try:
                    from src.infrastructure.queue.models.queue_entry_model import QueueEntryModel
                    stmt = (
                        sa.update(QueueEntryModel)
                        .where(QueueEntryModel.id == visit_id)
                        .values(status="REPORT_READY", updated_at=datetime.datetime.now(datetime.timezone.utc))
                    )
                    await session.execute(stmt)
                except Exception:
                    pass

            await session.commit()
            return {"ok": True, "id": rx.id, "message": "Prescription saved & inter-department queue status updated!"}
    except Exception as e:
        logger.error("Save Rx error: %s", e)
        return {"ok": False, "error": str(e)}


@router.post("/api/transcribe", include_in_schema=False)
async def api_transcribe_audio(request: Request):
    """Transcribe doctor consultation voice dictation (EkaScribe style).

    BYOK: clinic's own audio providers (Groq/OpenAI/Gemini) — clinic pays.
    Puter mode: browser-side puter.ai.speech2txt (user-pays).
    """
    sess = _require_opd_session(request)
    doctor_id = sess["doctor_id"]
    settings = await _ai_settings_for(doctor_id)
    try:
        form = await request.form()
        puter_result = str(form.get("puter_result") or "").strip()
        if puter_result:
            await _log_ai(settings, doctor_id, "transcribe", "puter", settings.get("ai_model") or "puter", success=True)
            return {"ok": True, "text": puter_result}

        audio_file = form.get("audio")
        if not audio_file:
            return {"ok": False, "error": "No audio file provided"}

        audio_bytes = await audio_file.read()
        filename = getattr(audio_file, "filename", "audio.webm") or "audio.webm"

        routed = route_transcribe(settings, audio_bytes, filename, feature="transcribe")
        if routed.get("puter_needed"):
            return {"ok": False, "code": routed["code"]}
        transcription = routed.get("text") or ""
        if not transcription:
            await _log_ai(settings, doctor_id, "transcribe", routed.get("provider") or "none", routed.get("model") or "", success=False, error=routed.get("error") or "")
            return {"ok": False, "error": routed.get("error") or "Transcription empty or failed"}

        await _log_ai(settings, doctor_id, "transcribe", routed.get("provider") or "", routed.get("model") or "", success=True)
        return {"ok": True, "text": transcription}
    except Exception as e:
        logger.error("Voice transcription error: %s", e)
        return {"ok": False, "error": str(e)}


@router.get("/api/search", include_in_schema=False)
async def api_search_patients(request: Request, q: str = Query("")):
    """Unified Patient Search & Recall Engine.
    
    Searches patients across Queue, Patient Master, and Prescriptions by
    Name, Phone Number, Disease/Diagnosis, Token Number, or Patient ID.
    """
    sess = _require_opd_session(request)
    query_str = q.strip()
    if not query_str or len(query_str) < 2:
        return []

    results = []
    seen_ids = set()

    try:
        async with async_session_factory() as session:
            # 1. Search in Queue Entries (Today's active patients)
            from src.infrastructure.queue.models.queue_entry_model import QueueEntryModel
            q_stmt = sa.select(QueueEntryModel).where(
                sa.or_(
                    QueueEntryModel.patient_name.ilike(f"%{query_str}%"),
                    QueueEntryModel.patient_id.ilike(f"%{query_str}%"),
                    QueueEntryModel.token_number.ilike(f"%{query_str}%"),
                    QueueEntryModel.service_code.ilike(f"%{query_str}%"),
                    QueueEntryModel.notes.ilike(f"%{query_str}%"),
                )
            ).order_by(QueueEntryModel.created_at.desc()).limit(20)

            q_rows = (await session.execute(q_stmt)).scalars().all()
            for r in q_rows:
                key = f"q_{r.id}"
                if key not in seen_ids:
                    seen_ids.add(key)
                    results.append({
                        "patient_name": r.patient_name,
                        "patient_id": r.patient_id,
                        "patient_uuid": r.patient_uuid,
                        "phone": "",
                        "vitals": "",
                        "complaints": r.notes or "",
                        "diagnosis": "",
                        "token_number": r.token_number,
                        "service_code": r.service_code,
                        "status": r.status,
                        "date": r.created_at.strftime("%Y-%m-%d") if r.created_at else "",
                        "source": "queue",
                    })

            # 2. Search in PatientModel (Master Patients)
            from src.infrastructure.patient.models.patient_model import PatientModel
            p_stmt = sa.select(PatientModel).where(
                sa.or_(
                    PatientModel.name.ilike(f"%{query_str}%"),
                    PatientModel.phone.ilike(f"%{query_str}%"),
                    PatientModel.patient_id.ilike(f"%{query_str}%"),
                )
            ).order_by(PatientModel.updated_at.desc()).limit(20)

            p_rows = (await session.execute(p_stmt)).scalars().all()
            for p in p_rows:
                key = f"p_{p.id}"
                if key not in seen_ids:
                    seen_ids.add(key)
                    results.append({
                        "patient_name": p.name,
                        "patient_id": p.patient_id,
                        "patient_uuid": str(p.id),
                        "phone": p.phone or "",
                        "age": p.age,
                        "gender": p.gender,
                        "vitals": "",
                        "complaints": "",
                        "diagnosis": "",
                        "date": p.last_visit_at.strftime("%Y-%m-%d") if p.last_visit_at else "",
                        "source": "patient",
                    })

            # 3. Search in OpdPrescriptionModel (Past Prescriptions & Diseases)
            rx_stmt = sa.select(OpdPrescriptionModel).where(
                sa.or_(
                    OpdPrescriptionModel.patient_name.ilike(f"%{query_str}%"),
                    OpdPrescriptionModel.phone.ilike(f"%{query_str}%"),
                    OpdPrescriptionModel.diagnosis.ilike(f"%{query_str}%"),
                    OpdPrescriptionModel.complaints.ilike(f"%{query_str}%"),
                    OpdPrescriptionModel.medicines.ilike(f"%{query_str}%"),
                    OpdPrescriptionModel.investigations.ilike(f"%{query_str}%"),
                )
            ).order_by(OpdPrescriptionModel.id.desc()).limit(20)

            rx_rows = (await session.execute(rx_stmt)).scalars().all()
            for rx in rx_rows:
                key = f"rx_{rx.id}"
                if key not in seen_ids:
                    seen_ids.add(key)
                    results.append({
                        "patient_name": rx.patient_name,
                        "patient_id": "",
                        "phone": rx.phone or "",
                        "vitals": rx.vitals or "",
                        "complaints": rx.complaints or "",
                        "diagnosis": rx.diagnosis or "",
                        "medicines": rx.medicines or "",
                        "investigations": rx.investigations or "",
                        "date": rx.date or "",
                        "source": "prescription",
                    })

            return results
    except Exception as e:
        logger.error("Search error: %s", e)
        return []


@router.post("/api/scan-approve", include_in_schema=False)
async def api_approve_scan(request: Request):
    sess = _require_opd_session(request)
    doctor_id = sess["doctor_id"]

    try:
        body = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON"}

    scan_id = body.get("id")
    if not scan_id:
        return {"ok": False, "error": "Scan ID required"}

    try:
        async with async_session_factory() as session:
            row = await session.execute(
                sa.select(PendingScanModel).where(PendingScanModel.id == scan_id)
            )
            scan = row.scalar_one_or_none()
            if not scan:
                return {"ok": False, "error": "Scan not found"}

            # Save as prescription
            rx = OpdPrescriptionModel(
                patient_name=body.get("patient_name", scan.patient_name),
                phone=body.get("phone", scan.phone),
                doctor_id=doctor_id,
                vitals=body.get("vitals", scan.vitals),
                complaints=body.get("complaints", scan.complaints),
                medicines=body.get("medicines", scan.medicines),
                investigations=body.get("investigations", scan.investigations),
                ai_generated=True,
            )
            session.add(rx)

            # Mark scan as approved
            scan.status = "approved"
            scan.patient_name = body.get("patient_name", scan.patient_name)
            scan.phone = body.get("phone", scan.phone)
            scan.vitals = body.get("vitals", scan.vitals)
            scan.complaints = body.get("complaints", scan.complaints)
            scan.medicines = body.get("medicines", scan.medicines)
            scan.investigations = body.get("investigations", scan.investigations)

            await session.commit()

            # C3 space management: data prescription mein save ho gaya —
            # original image (bada base64) ab delete (PA ka 512MB bachata hai)
            try:
                await session.execute(
                    sa.delete(PendingScanModel).where(PendingScanModel.id == scan_id)
                )
                await session.commit()
            except Exception:
                pass

            # Learn drugs
            await _learn_drugs(body.get("medicines", scan.medicines), doctor_id)

            return {"ok": True, "prescription_id": str(rx.id)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════════
# API: AI LAB INTELLIGENCE — Upload + OCR + Structured Extraction + Clinical Analysis
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/api/lab-report-analyze", include_in_schema=False)
async def api_lab_report_analyze(request: Request):
    """Full AI Lab Intelligence pipeline:
    1. Upload lab report image (camera/gallery/PDF)
    2. OCR + structured extraction of lab values
    3. Abnormality detection (HIGH/LOW/CRITICAL vs reference ranges)
    4. Clinical interpretation (AI-generated observations)
    5. Follow-up test recommendations
    6. Save everything to opd_lab_reports table

    BYOK: clinic's own keys pay for vision + text calls.
    Puter mode: browser hops (img2txt → structure chat → interpretation chat
    → recommendations chat) — all billed to the clinic's Puter account.
    """
    sess = _require_opd_session(request)
    doctor_id = sess.get("doctor_id", "")

    try:
        body = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON"}

    image_b64 = body.get("image", "")
    patient_name = body.get("patient_name", "").strip()
    patient_id = body.get("patient_id", "").strip()
    phone = body.get("phone", "").strip()
    report_date = body.get("report_date", datetime.date.today().isoformat())
    report_type = body.get("report_type", "pathology")
    patient_age = body.get("age", "")
    patient_gender = body.get("gender", "")
    stage = str(body.get("stage") or "")

    if not image_b64 and stage not in ("interpretation", "recommendations"):
        return {"ok": False, "error": "No report image provided"}

    if not patient_name:
        return {"ok": False, "error": "Patient name required to save lab report"}

    settings = await _ai_settings_for(doctor_id)

    try:
        import base64 as b64_mod
        import io as io_mod
        from PIL import Image
        from src.ai_engine.prompts import (
            lab_report_ocr_prompt,
            lab_clinical_interpretation_prompt,
            lab_recommendations_prompt,
        )

        img_b64_clean = image_b64
        if "," in img_b64_clean:
            img_b64_clean = img_b64_clean.split(",", 1)[1]

        puter_text = _puter_text_or_none(body)
        puter_ocr = body.get("puter_ocr_result")

        # ═══ Step 2: OCR + Structured Extraction ═══
        structured: list = []
        raw_ocr: str = ""

        if stage in ("interpretation", "recommendations"):
            # Later hops: lab data already structured and saved — rebuild from
            # the body snapshot the gateway echoed back.
            structured = json.loads(body.get("_structured") or "[]")
            raw_ocr = body.get("_raw_ocr") or ""
        elif puter_text or puter_ocr:
            raw_ocr = str(puter_text or puter_ocr or "").strip()
            structured = parse_ai_json(raw_ocr) if isinstance(parse_ai_json(raw_ocr), list) else []
            if not structured:
                # Structure the plain OCR text via a Puter chat hop
                await _log_ai(settings, doctor_id, "lab-ocr", "puter", settings.get("ai_model") or "puter", success=True)
                struct_prompt = (
                    f"{lab_report_ocr_prompt()}\n\n"
                    f"OCR TEXT:\n{raw_ocr}\n\nReturn ONLY the JSON array."
                )
                return {"ok": False, "code": "PUTER_CHAT", "stage": "ocr", "prompt": struct_prompt,
                        "model": settings.get("ai_model") or "gpt-4o-mini"}
        else:
            # Server-side: decode image + vision routing with lab prompt
            if image_b64:
                image_bytes = b64_mod.b64decode(img_b64_clean)
                img = Image.open(io_mod.BytesIO(image_bytes))
                routed = route_vision(settings, img, feature="lab-ocr", prompt_text=lab_report_ocr_prompt())
                if routed.get("puter_needed"):
                    return {"ok": False, "code": routed["code"], "prompt": routed["prompt"], "model": routed["model"]}
                raw_ocr = routed.get("text") or ""
                provider = routed.get("provider") or ""
                model_used = routed.get("model") or ""
                struct_routed = None
                structured = parse_ai_json(raw_ocr) if isinstance(parse_ai_json(raw_ocr), list) else []
                if not structured:
                    # Text-only structuring fallback
                    struct_prompt = f"{lab_report_ocr_prompt()}\n\nOCR TEXT:\n{raw_ocr}\n\nReturn ONLY the JSON array."
                    struct_routed = route_chat(settings, [struct_prompt], feature="lab-ocr-struct", temp=0.1, max_tokens=2000)
                    if struct_routed.get("puter_needed"):
                        await _log_ai(settings, doctor_id, "lab-ocr", provider, model_used, success=True)
                        return {"ok": False, "code": struct_routed["code"], "stage": "ocr", "prompt": struct_routed["prompt"],
                                "model": struct_routed["model"]}
                    raw_ocr = struct_routed.get("text") or raw_ocr
                    structured = parse_ai_json(raw_ocr) if isinstance(parse_ai_json(raw_ocr), list) else []
                await _log_ai(settings, doctor_id, "lab-ocr", provider or (struct_routed.get("provider") if struct_routed else ""),
                              model_used, success=True,
                              usage=(struct_routed.get("usage") if struct_routed else {}) or routed.get("usage") or {})
            if not isinstance(structured, list):
                structured = []
                logger.warning("Lab OCR failed to extract structured values")

        # ═══ Step 3: Classify abnormalities ═══
        abnormal_items = []
        investigation_names = []
        for item in structured:
            name = item.get("name", "")
            status = item.get("status", "NORMAL")
            if name:
                investigation_names.append(f"{name}: {item.get('value','')} {item.get('unit','')} [{status}]")
            if status in ("HIGH", "LOW", "CRITICAL"):
                abnormal_items.append(item)

        investigation_summary = "; ".join(investigation_names) if investigation_names else ""

        # ═══ Step 4: Clinical Interpretation (only if abnormalities found) ═══
        ai_clinical_notes = ""
        ai_risk_flags = ""
        if abnormal_items:
            abnormal_json = json.dumps(abnormal_items, indent=2)
            clinical_prompt_text = lab_clinical_interpretation_prompt(
                abnormal_json, patient_name, patient_age, patient_gender
            )
            if stage == "interpretation" and puter_text:
                ai_clinical_notes = sanitize_output(puter_text)
                risk_match = re.search(
                    r"🏷️ RISK FLAGS?\n?(.*?)(?=\n\s*(?:⚠️|$))",
                    ai_clinical_notes, re.DOTALL | re.IGNORECASE
                )
                if risk_match:
                    ai_risk_flags = risk_match.group(1).strip()
                await _log_ai(settings, doctor_id, "lab-interpret", "puter", settings.get("ai_model") or "puter", success=True)
            else:
                routed = route_chat(settings, [clinical_prompt_text], feature="lab-interpret", temp=0.3, max_tokens=2000)
                if routed.get("puter_needed"):
                    return {"ok": False, "code": routed["code"], "stage": "interpretation", "prompt": routed["prompt"],
                            "model": routed["model"], "_structured": json.dumps(structured), "_raw_ocr": raw_ocr}
                ai_clinical_notes = routed.get("text") or ""
                if ai_clinical_notes:
                    risk_match = re.search(
                        r"🏷️ RISK FLAGS?\n?(.*?)(?=\n\s*(?:⚠️|$))",
                        ai_clinical_notes, re.DOTALL | re.IGNORECASE
                    )
                    if risk_match:
                        ai_risk_flags = risk_match.group(1).strip()
                await _log_ai(settings, doctor_id, "lab-interpret", routed.get("provider") or "", routed.get("model") or "",
                              success=bool(ai_clinical_notes), usage=routed.get("usage") or {}, error=routed.get("error") or "")

        # ═══ Step 5: Follow-up Recommendations ═══
        ai_recommendations = ""
        if abnormal_items:
            rec_prompt_text = lab_recommendations_prompt(
                json.dumps(abnormal_items, indent=2), patient_name
            )
            if stage == "recommendations" and puter_text:
                ai_recommendations = sanitize_output(puter_text)
                await _log_ai(settings, doctor_id, "lab-recommend", "puter", settings.get("ai_model") or "puter", success=True)
            else:
                routed = route_chat(settings, [rec_prompt_text], feature="lab-recommend", temp=0.3, max_tokens=1500)
                if routed.get("puter_needed"):
                    return {"ok": False, "code": routed["code"], "stage": "recommendations", "prompt": routed["prompt"],
                            "model": routed["model"], "_structured": json.dumps(structured), "_raw_ocr": raw_ocr}
                ai_recommendations = routed.get("text") or ""
                await _log_ai(settings, doctor_id, "lab-recommend", routed.get("provider") or "", routed.get("model") or "",
                              success=bool(ai_recommendations), usage=routed.get("usage") or {}, error=routed.get("error") or "")

        # ═══ Step 6: Save to database ═══
        structured_json = json.dumps(structured, ensure_ascii=False)

        async with async_session_factory() as session:
            report = LabReportModel(
                clinic_id=sess.get("clinic_id"),
                doctor_id=doctor_id,
                patient_id=patient_id,
                patient_name=patient_name,
                phone=phone,
                report_date=report_date,
                report_type=report_type,
                source_image_b64=img_b64_clean,
                ocr_raw_text=raw_ocr or "",
                structured_values=structured_json,
                ai_clinical_notes=ai_clinical_notes,
                ai_recommendations=ai_recommendations,
                ai_risk_flags=ai_risk_flags,
                investigation_summary=investigation_summary,
                status="active",
            )
            session.add(report)
            await session.commit()
            report_id = str(report.id)

        return {
            "ok": True,
            "report_id": report_id,
            "structured_values": structured,
            "abnormal_count": len(abnormal_items),
            "total_tests": len(structured),
            "ai_clinical_notes": ai_clinical_notes,
            "ai_recommendations": ai_recommendations,
            "ai_risk_flags": ai_risk_flags,
            "investigation_summary": investigation_summary,
            "ocr_raw": raw_ocr or "",
        }

    except Exception as e:
        logger.error("Lab report analyze error: %s", e)
        return {"ok": False, "error": f"AI lab analysis failed: {str(e)}"}


@router.get("/api/lab-reports", include_in_schema=False)
async def api_get_lab_reports(
    request: Request,
    patient_name: str = Query(""),
    patient_id: str = Query(""),
):
    """Get all lab reports for a patient. Search by name or patient_id."""
    sess = _require_opd_session(request)
    doctor_id = sess.get("doctor_id", "")

    if not patient_name and not patient_id:
        return {"ok": False, "error": "patient_name or patient_id required"}

    try:
        async with async_session_factory() as session:
            query = sa.select(LabReportModel).where(
                LabReportModel.status == "active"
            )
            if patient_id:
                query = query.where(LabReportModel.patient_id == patient_id)
            elif patient_name:
                query = query.where(
                    LabReportModel.patient_name.ilike(f"%{patient_name}%")
                )
            query = query.order_by(LabReportModel.created_at.desc())

            rows = await session.execute(query)
            results = []
            for r in rows.scalars():
                try:
                    structured = json.loads(r.structured_values) if r.structured_values else []
                except Exception:
                    structured = []

                results.append({
                    "id": str(r.id),
                    "patient_id": r.patient_id,
                    "patient_name": r.patient_name,
                    "report_date": r.report_date,
                    "report_type": r.report_type,
                    "structured_values": structured,
                    "ai_clinical_notes": r.ai_clinical_notes,
                    "ai_recommendations": r.ai_recommendations,
                    "ai_risk_flags": r.ai_risk_flags,
                    "investigation_summary": r.investigation_summary,
                    "created_at": r.created_at.isoformat() if r.created_at else "",
                })
            return {"ok": True, "reports": results}
    except Exception as e:
        logger.error("Get lab reports error: %s", e)
        return {"ok": False, "error": str(e)}


@router.get("/api/lab-trends", include_in_schema=False)
async def api_get_lab_trends(
    request: Request,
    patient_name: str = Query(""),
    patient_id: str = Query(""),
):
    """Get longitudinal trend data for a patient's investigations.
    Returns each parameter with all historical values for trend arrows.
    """
    sess = _require_opd_session(request)

    if not patient_name and not patient_id:
        return {"ok": False, "error": "patient_name or patient_id required"}

    try:
        async with async_session_factory() as session:
            query = sa.select(LabReportModel).where(
                LabReportModel.status == "active"
            )
            if patient_id:
                query = query.where(LabReportModel.patient_id == patient_id)
            else:
                query = query.where(
                    LabReportModel.patient_name.ilike(f"%{patient_name}%")
                )
            query = query.order_by(LabReportModel.report_date.asc())

            rows = await session.execute(query)
            reports = rows.scalars().all()

            if not reports:
                return {"ok": True, "trends": {}, "message": "No reports found"}

            # Build trend map: { "HbA1c": [{"date":"2026-01","value":"8.2","unit":"%","status":"HIGH"}, ...] }
            trend_map = {}
            for r in reports:
                try:
                    structured = json.loads(r.structured_values) if r.structured_values else []
                except Exception:
                    continue

                for item in structured:
                    name = item.get("name", "")
                    if not name:
                        continue
                    if name not in trend_map:
                        trend_map[name] = []
                    trend_map[name].append({
                        "date": r.report_date,
                        "value": item.get("value", ""),
                        "unit": item.get("unit", ""),
                        "status": item.get("status", "NORMAL"),
                        "ref_range": item.get("ref_range", ""),
                    })

            # Compute trend direction
            trend_results = {}
            for name, values in trend_map.items():
                if len(values) < 2:
                    trend_results[name] = {
                        "values": values,
                        "direction": "→",
                        "trend": "stable",
                        "message": "Single reading — need more data for trend",
                    }
                    continue

                # Compare first vs last value
                try:
                    first_val = float(values[0]["value"])
                    last_val = float(values[-1]["value"])
                except (ValueError, TypeError):
                    trend_results[name] = {
                        "values": values,
                        "direction": "→",
                        "trend": "stable",
                        "message": "Non-numeric values — cannot compute trend",
                    }
                    continue

                if last_val > first_val * 1.05:
                    direction = "↑"
                    trend = "worsening" if values[-1].get("status") in ("HIGH", "CRITICAL") else "increasing"
                elif last_val < first_val * 0.95:
                    direction = "↓"
                    trend = "improving" if values[0].get("status") in ("HIGH", "CRITICAL") else "decreasing"
                else:
                    direction = "→"
                    trend = "stable"

                change_pct = abs((last_val - first_val) / first_val * 100) if first_val != 0 else 0
                trend_results[name] = {
                    "values": values,
                    "direction": direction,
                    "trend": trend,
                    "change_percent": round(change_pct, 1),
                    "first_value": values[0]["value"],
                    "last_value": values[-1]["value"],
                    "first_date": values[0]["date"],
                    "last_date": values[-1]["date"],
                }

            return {"ok": True, "trends": trend_results}
    except Exception as e:
        logger.error("Get lab trends error: %s", e)
        return {"ok": False, "error": str(e)}


@router.get("/api/lab-abnormal", include_in_schema=False)
async def api_get_lab_abnormal(
    request: Request,
    patient_name: str = Query(""),
    patient_id: str = Query(""),
    limit: int = Query(20),
):
    """Get latest abnormal findings for a patient (or all patients if no filter).
    Returns only HIGH/LOW/CRITICAL values from the most recent reports.
    """
    sess = _require_opd_session(request)
    doctor_id = sess.get("doctor_id", "")

    try:
        async with async_session_factory() as session:
            query = sa.select(LabReportModel).where(
                LabReportModel.status == "active"
            )
            if patient_id:
                query = query.where(LabReportModel.patient_id == patient_id)
            elif patient_name:
                query = query.where(
                    LabReportModel.patient_name.ilike(f"%{patient_name}%")
                )
            else:
                # All patients for this doctor
                query = query.where(LabReportModel.doctor_id == doctor_id)

            query = query.order_by(LabReportModel.created_at.desc()).limit(limit)
            rows = await session.execute(query)
            reports = rows.scalars().all()

            abnormal_findings = []
            for r in reports:
                try:
                    structured = json.loads(r.structured_values) if r.structured_values else []
                except Exception:
                    continue

                for item in structured:
                    if item.get("status") in ("HIGH", "LOW", "CRITICAL"):
                        abnormal_findings.append({
                            "report_id": str(r.id),
                            "patient_name": r.patient_name,
                            "patient_id": r.patient_id,
                            "report_date": r.report_date,
                            "test_name": item.get("name", ""),
                            "value": item.get("value", ""),
                            "unit": item.get("unit", ""),
                            "ref_range": item.get("ref_range", ""),
                            "status": item.get("status", ""),
                        })

            return {"ok": True, "abnormal_findings": abnormal_findings}
    except Exception as e:
        logger.error("Get lab abnormal error: %s", e)
        return {"ok": False, "error": str(e)}


@router.delete("/api/lab-report/{report_id}", include_in_schema=False)
async def api_delete_lab_report(request: Request, report_id: str):
    """Archive (soft-delete) a lab report."""
    sess = _require_opd_session(request)

    try:
        async with async_session_factory() as session:
            row = await session.execute(
                sa.select(LabReportModel).where(LabReportModel.id == report_id)
            )
            report = row.scalar_one_or_none()
            if not report:
                return {"ok": False, "error": "Lab report not found"}

            report.status = "archived"
            await session.commit()
            return {"ok": True, "message": "Lab report archived"}
    except Exception as e:
        logger.error("Delete lab report error: %s", e)
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════════
# API: BULK IMPORT
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/api/bulk-import", include_in_schema=False)
async def api_bulk_import(request: Request):
    """Bulk import patients from JSON array. Detects duplicates by phone."""
    sess = _require_opd_session(request)
    if sess.get("role") != "admin":
        return {"ok": False, "error": "Admin only"}

    try:
        body = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON"}

    patients = body.get("patients", [])
    if not patients or not isinstance(patients, list):
        return {"ok": False, "error": "patients array required"}

    imported = 0
    duplicates = 0
    errors = 0

    try:
        async with async_session_factory() as session:
            for p in patients:
                name = str(p.get("name", "")).strip()
                phone = str(p.get("phone", "")).strip()
                if not name:
                    errors += 1
                    continue

                # Check duplicate by phone
                if phone:
                    existing = await session.execute(
                        sa.select(OpdPrescriptionModel).where(
                            OpdPrescriptionModel.phone == phone,
                            OpdPrescriptionModel.patient_name.ilike(f"%{name[:10]}%"),
                        ).limit(1)
                    )
                    if existing.scalar_one_or_none():
                        duplicates += 1
                        continue

                now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M")
                rx = OpdPrescriptionModel(
                    patient_name=name,
                    phone=phone,
                    age=str(p.get("age", "")),
                    gender=str(p.get("gender", "")),
                    complaints=str(p.get("complaints", "")),
                    vitals=str(p.get("vitals", "")),
                    diagnosis=str(p.get("diagnosis", "")),
                    medicines=str(p.get("medicines", "")),
                    address=str(p.get("address", "")),
                    doctor_id=sess["doctor_id"],
                    created_at=now_str,
                )
                session.add(rx)
                imported += 1

            await session.commit()
    except Exception as e:
        logger.error("Bulk import error: %s", e)
        return {"ok": False, "error": str(e)}

    return {"ok": True, "imported": imported, "duplicates": duplicates, "errors": errors}


# ═══════════════════════════════════════════════════════════════════════════════
# API: LICENSES (Admin)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/api/licenses", include_in_schema=False)
async def api_get_licenses(request: Request):
    sess = _require_opd_session(request)
    if sess.get("role") != "admin":
        return {"ok": False, "error": "Admin only"}

    try:
        async with async_session_factory() as session:
            rows = await session.execute(
                sa.select(LicenseModel).order_by(LicenseModel.id.desc())
            )
            results = []
            for r in rows.scalars():
                results.append({
                    "id": r.id,
                    "doctor_id": r.doctor_id,
                    "doctor_name": r.doctor_name,
                    "doctor_email": r.doctor_email,
                    "doctor_phone": r.doctor_phone,
                    "pin": r.pin,
                    "clinic_name": r.clinic_name,
                    "specialty": r.specialty,
                    "expiry_date": r.expiry_date,
                    "is_active": r.is_active,
                    "created_date": r.created_date,
                    "notes": r.notes,
                })
            return results
    except Exception:
        return []


@router.post("/api/license", include_in_schema=False)
async def api_create_license(request: Request):
    sess = _require_opd_session(request)
    if sess.get("role") != "admin":
        return {"ok": False, "error": "Admin only"}

    try:
        body = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON"}

    doctor_id = body.get("doctor_id", "").strip()
    name = body.get("doctor_name", "").strip()
    pin = body.get("pin", "").strip()

    if not doctor_id or not name or not pin:
        return {"ok": False, "error": "doctor_id, doctor_name, and pin required."}

    try:
        async with async_session_factory() as session:
            lic = LicenseModel(
                doctor_id=doctor_id,
                doctor_name=name,
                doctor_email=body.get("doctor_email", ""),
                doctor_phone=body.get("doctor_phone", ""),
                pin=pin,
                clinic_name=body.get("clinic_name", ""),
                specialty=body.get("specialty", ""),
                expiry_date=body.get("expiry_date", "2030-12-31"),
                created_date=datetime.date.today().isoformat(),
                notes=body.get("notes", ""),
            )
            session.add(lic)

            # Auto-create settings
            sett = SettingsModel(
                doctor_id=doctor_id,
                clinic_name=body.get("clinic_name", ""),
                doc_name=name,
                doc_subtitle=body.get("specialty", "MBBS"),
            )
            session.add(sett)

            await session.commit()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.delete("/api/license", include_in_schema=False)
async def api_delete_license(request: Request, id: int = Query(...)):
    sess = _require_opd_session(request)
    if sess.get("role") != "admin":
        return {"ok": False, "error": "Admin only"}

    try:
        async with async_session_factory() as session:
            await session.execute(
                sa.delete(LicenseModel).where(LicenseModel.id == id)
            )
            await session.commit()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════════
# API: ADMIN STATS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/api/admin/stats", include_in_schema=False)
async def api_admin_stats(request: Request):
    sess = _require_opd_session(request)
    if sess.get("role") != "admin":
        return {"ok": False, "error": "Admin only"}

    try:
        async with async_session_factory() as session:
            total_rx = await session.execute(sa.select(sa.func.count()).select_from(OpdPrescriptionModel))
            total_patients = await session.execute(sa.select(sa.func.count()).select_from(PatientModel))
            total_licenses = await session.execute(sa.select(sa.func.count()).select_from(LicenseModel))

            return {
                "total_prescriptions": total_rx.scalar() or 0,
                "total_queue_patients": total_patients.scalar() or 0,
                "total_licenses": total_licenses.scalar() or 0,
            }
    except Exception:
        return {"total_prescriptions": 0, "total_queue_patients": 0, "total_licenses": 0}


# ═══════════════════════════════════════════════════════════════════════════════
# RESEARCH AGENT (Upgrade 6 — Chief-Only)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/api/research", include_in_schema=False)
async def api_research(request: Request):
    """Research agent — analyzes practice data. Chief-only."""
    sess = _require_opd_session(request)
    doctor_id = sess["doctor_id"]
    if not _has_chief_access(sess):
        return {"ok": False, "error": "Only Chief can access research."}

    try:
        body = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON"}

    question = body.get("question", "").strip()
    if not question:
        return {"ok": False, "error": "Research question required"}

    try:
        async with async_session_factory() as session:
            # Fetch last 150 prescriptions for analysis
            rx_rows = await session.execute(
                sa.select(OpdPrescriptionModel)
                .where(OpdPrescriptionModel.doctor_id == doctor_id)
                .order_by(OpdPrescriptionModel.created_at.desc())
                .limit(150)
            )
            rx_list = list(rx_rows.scalars())

            # Count patients and revenue
            patient_ids = set()
            total_revenue = 0
            for r in rx_list:
                if r.patient_id:
                    patient_ids.add(r.patient_id)
                try:
                    total_revenue += int(r.fee or 0)
                except (ValueError, TypeError):
                    pass

            # Build sample data string (compressed)
            sample_lines = []
            for r in rx_list[:100]:
                parts = [f"Pt: {r.patient_name or ''}"]
                if r.diagnosis:
                    parts.append(f"Dx: {r.diagnosis[:100]}")
                if r.medicines:
                    meds = r.medicines[:80].replace("\n", "; ")
                    parts.append(f"Rx: {meds}")
                if r.fee:
                    parts.append(f"Fee: ₹{r.fee}")
                if r.created_at:
                    parts.append(f"Date: {r.created_at.strftime('%d-%b')}")
                sample_lines.append(" | ".join(parts))
            patient_data = "\n".join(sample_lines[:80])

            # Fetch starred specialty upgrades
            star_rows = await session.execute(
                sa.select(SpecialtyUpgradeModel)
                .where(SpecialtyUpgradeModel.doctor_id == doctor_id)
                .where(SpecialtyUpgradeModel.is_starred == 1)
                .order_by(SpecialtyUpgradeModel.created_at.desc())
                .limit(20)
            )
            starred_list = list(star_rows.scalars())
            starred_data_lines = []
            for s in starred_list[:10]:
                parts = [f"Pt: {s.patient_name or ''}", f"Spec: {s.specialty or ''}"]
                if s.upgraded_rx:
                    parts.append(f"Rx: {s.upgraded_rx[:80]}")
                if s.star_note:
                    parts.append(f"Note: {s.star_note[:80]}")
                starred_data_lines.append(" | ".join(parts))
            starred_data = "\n".join(starred_data_lines[:10]) or "No starred cases."

            settings = await _ai_settings_for(doctor_id)
            prompt = research_prompt(
                doc_name=settings.get("doc_name", "Doctor"),
                patient_count=len(patient_ids),
                total_revenue=total_revenue,
                patient_data=patient_data,
                starred_data=starred_data,
                question=question,
            )

            puter_text = _puter_text_or_none(body)
            if puter_text:
                result, provider, model_used, usage = sanitize_output(puter_text), "puter", settings.get("ai_model") or "puter", {}
            else:
                routed = route_chat(settings, [prompt], feature="research", temp=0.3, max_tokens=4000)
                if routed.get("puter_needed"):
                    return {"ok": False, "code": routed["code"], "prompt": routed["prompt"], "model": routed["model"]}
                result, provider, model_used, usage = routed.get("text") or "", routed.get("provider") or "", routed.get("model") or "", routed.get("usage") or {}
                if not result:
                    await _log_ai(settings, doctor_id, "research", provider or "none", model_used, success=False, error=routed.get("error") or "")
                    return {"ok": False, "error": routed.get("error") or "Research query failed."}

            await _log_ai(settings, doctor_id, "research", provider, model_used, success=True, usage=usage)

            stats = {
                "total_prescriptions": len(rx_list),
                "unique_patients": len(patient_ids),
                "total_revenue": total_revenue,
                "starred_cases": len(starred_list),
            }
            return {"ok": True, "result": result, "stats": stats, "provider": provider}

    except Exception as e:
        logger.error("Research error: %s", e)
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN PORTAL PAGE
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/admin", include_in_schema=False)
async def opd_admin_portal(request: Request):
    sess = _require_opd_session(request)
    if sess.get("role") != "admin":
        return HTMLResponse(content="<h2>❌ Admin access only</h2><a href='/opd/login'>Login</a>", status_code=403)

    return HTMLResponse(content=_render("opd/admin.html",
        request=request,
        session=sess,
    ))
