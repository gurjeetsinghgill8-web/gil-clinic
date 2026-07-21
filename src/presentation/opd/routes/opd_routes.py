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
    LicenseModel,
    OpdPrescriptionModel,
    PendingScanModel,
    SettingsModel,
    SpecialtyUpgradeModel,
    TemplateModel,
)

# ── Patient Model (queue system) ─────────────────────────────────────────────
from src.infrastructure.patient.models.patient_model import PatientModel

# ── AI Engine ────────────────────────────────────────────────────────────────
from src.ai_engine.groq_client import call_groq, call_groq_vision, parse_ai_json
from src.ai_engine.prompts import gp_prompt, specialty_prompt, drug_review_prompt, cme_prompt

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
    if not token:
        return None
    return _read_opd_session(token)


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

async def _get_settings(doctor_id: str) -> dict:
    """Get settings for a doctor — returns defaults if not found."""
    defaults = {
        "clinic_name": "My Clinic", "doc_name": "Doctor",
        "doc_subtitle": "MBBS", "doc_degree": "", "doc_reg_no": "",
        "doc_email": "", "doc_phone": "", "clinic_address": "",
        "doc_extra_quals": "", "groq_api_key": "",
    }
    try:
        async with async_session_factory() as session:
            row = await session.execute(
                sa.select(SettingsModel).where(SettingsModel.doctor_id == doctor_id)
            )
            s = row.scalar_one_or_none()
            if s:
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
                    "groq_api_key": s.groq_api_key,
                }
    except Exception:
        pass
    return defaults


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
                         "doc_extra_quals", "groq_api_key"]:
                if key in body:
                    setattr(s, key, str(body[key]))

            await session.commit()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


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
            for row in rows.scalars():
                key = f"{row.patient_name}_{row.phone}"
                if key not in seen:
                    seen.add(key)
                    results.append({
                        "patient_name": row.patient_name,
                        "phone": row.phone,
                        "date": row.created_at.strftime("%Y-%m-%d %H:%M") if row.created_at else "",
                        "vitals": row.vitals,
                        "complaints": row.complaints,
                        "medicines": row.medicines,
                        "diagnosis": row.diagnosis,
                        "investigations": row.investigations,
                        "fee": row.fee,
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
                        results.append({
                            "patient_name": row.name,
                            "phone": row.phone,
                            "patient_id": row.patient_id,
                            "age": row.age,
                            "gender": row.gender,
                            "source": "queue",
                        })
    except Exception as e:
        logger.error("Search error: %s", e)

    return results[:20]


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

    if not patient_name:
        return {"ok": False, "error": "Patient name required"}

    settings = await _get_settings(doctor_id)

    # Build prompt
    prompt = gp_prompt(
        patient_name=patient_name,
        vitals=vitals,
        notes=complaints,
        doc_name=settings.get("doc_name", "Doctor"),
        past_context=past_context,
    )

    # Call Groq
    groq_key = settings.get("groq_api_key") or os.getenv("GROQ_API_KEY", "")
    if not groq_key:
        return {"ok": False, "error": "Groq API key not configured. Set in Settings."}

    os.environ["GROQ_API_KEY"] = groq_key
    result = call_groq([prompt], temp=0.3)

    if not result:
        return {"ok": False, "error": "AI Generation failed. Check API key."}

    return {"ok": True, "prescription": result}


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

    settings = await _get_settings(sess["doctor_id"])
    groq_key = settings.get("groq_api_key") or os.getenv("GROQ_API_KEY", "")
    if not groq_key:
        return {"ok": False, "error": "Groq API key not configured."}
    os.environ["GROQ_API_KEY"] = groq_key

    prompt = drug_review_prompt(vitals=vitals, prescription=prescription)
    result = call_groq([prompt], temp=0.3)
    return {"ok": bool(result), "review": result or "Failed to generate."}


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

    settings = await _get_settings(sess["doctor_id"])
    groq_key = settings.get("groq_api_key") or os.getenv("GROQ_API_KEY", "")
    if not groq_key:
        return {"ok": False, "error": "Groq API key not configured."}
    os.environ["GROQ_API_KEY"] = groq_key

    prompt = cme_prompt(topic)
    result = call_groq([prompt], temp=0.3)
    return {"ok": bool(result), "content": result or "Failed to generate."}


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

    if not patient_name:
        return {"ok": False, "error": "Patient name required"}

    try:
        async with async_session_factory() as session:
            rx = OpdPrescriptionModel(
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
    "❤️ Cardiology":      {"persona": "Cardiologist (DM Cardiology)", "guidelines": "ACC/AHA 2024, ESC 2023, CSI", "focus": "HTN, HF, IHD, arrhythmias"},
    "🦴 Orthopedics":     {"persona": "Orthopedic Surgeon (MS Ortho)", "guidelines": "AAOS, NICE Musculoskeletal, IOA", "focus": "joint pain, OA, back pain"},
    "🫁 Pulmonology":     {"persona": "Pulmonologist (DM Pulmonology)", "guidelines": "GOLD 2024, GINA 2024, RNTCP", "focus": "asthma, COPD, TB"},
    "👶 Pediatrics":      {"persona": "Pediatrician (MD Pediatrics)", "guidelines": "IAP 2024, WHO Child Growth", "focus": "fever, infections, growth"},
    "🩸 Diabetology":     {"persona": "Diabetologist (DM Endocrinology)", "guidelines": "ADA 2024, RSSDI, AACE", "focus": "DM1/2, insulin, HbA1c"},
    "🧠 Neurology":       {"persona": "Neurologist (DM Neurology)", "guidelines": "AAN, ESO Stroke, IAN", "focus": "headache, epilepsy, stroke"},
    "👩‍⚕️ Gynecology":    {"persona": "Gynecologist (MS OBG)", "guidelines": "FOGSI, RCOG, WHO", "focus": "PCOD, menstrual, pregnancy"},
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

    settings = await _get_settings(doctor_id)
    groq_key = settings.get("groq_api_key") or os.getenv("GROQ_API_KEY", "")
    if not groq_key:
        return {"ok": False, "error": "Groq API key not configured."}
    os.environ["GROQ_API_KEY"] = groq_key

    results = []
    for key in specialty_keys:
        spec_data = SPECIALTIES.get(key)
        if not spec_data:
            continue

        prompt = specialty_prompt(
            patient_name=patient_name,
            vitals=vitals,
            current_rx=original_rx,
            specialty_name=key,
            specialty_data=spec_data,
        )

        result_text = call_groq([prompt], temp=0.2)

        if result_text:
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

            # Learn drugs
            await _learn_drugs(body.get("medicines", scan.medicines), doctor_id)

            return {"ok": True, "prescription_id": str(rx.id)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/api/scan-ai", include_in_schema=False)
async def api_scan_ai_read(request: Request):
    """AI read a scan image and extract structured data."""
    sess = _require_opd_session(request)

    try:
        body = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON"}

    image_b64 = body.get("image", "")
    if not image_b64:
        return {"ok": False, "error": "No image data"}

    settings = await _get_settings(sess["doctor_id"])
    groq_key = settings.get("groq_api_key") or os.getenv("GROQ_API_KEY", "")
    if not groq_key:
        return {"ok": False, "error": "Groq API key not configured."}
    os.environ["GROQ_API_KEY"] = groq_key

    # Decode base64 to bytes for AI
    import base64
    try:
        image_bytes = base64.b64decode(image_b64)
    except Exception:
        return {"ok": False, "error": "Invalid base64 image"}

    from PIL import Image
    import io
    try:
        img = Image.open(io.BytesIO(image_bytes))
    except Exception:
        return {"ok": False, "error": "Cannot decode image"}

    result = call_groq_vision(img, context="Extract all prescription details.")
    parsed = parse_ai_json(result)

    return {
        "ok": True,
        "raw": result,
        "parsed": parsed,
    }


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
