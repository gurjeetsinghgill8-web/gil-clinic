"""
Staff Dashboard Routes — FastAPI HTML routes for GIL Clinic staff.

Serves the complete staff dashboard:
  GET  /staff/           → redirect to login or home
  GET  /staff/login      → login page
  POST /staff/login      → authenticate, set session cookie
  GET  /staff/logout     → clear session, redirect to login
  GET  /staff/home       → department overview grid
  GET  /staff/reception  → reception dashboard
  GET  /staff/ecg        → ECG technician dashboard
  GET  /staff/echo       → Echo technician dashboard
  GET  /staff/tmt        → TMT technician dashboard
  GET  /staff/opd        → OPD dashboard
  GET  /staff/doctor     → doctor dashboard
  GET  /staff/manager    → manager overview
  GET  /staff/billing    → billing page
  GET  /staff/tv         → TV display (redirect to existing)
  GET  /staff/patient-status → patient self-check (NO LOGIN)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Cookie, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

# ── Queue DB access (used by _get_queue helper) ──────────────────────────────
from src.application.queue.use_cases.list_queue_use_case import ListQueueUseCase
from src.infrastructure.persistence.queue.repositories.queue_repository import (
    SqlAlchemyQueueRepository,
)
from src.application.common.command import Command
from src.shared.infrastructure.database import async_session_factory

# ── Templates ─────────────────────────────────────────────────────────────────
_TEMPLATES_DIR = Path(__file__).parents[4] / "templates"
# Disable Jinja2 cache (avoids LRUCache bug on some Python versions)
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
templates.env.cache = None  # type: ignore[assignment]

# ── Session ───────────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "gil-clinic-secret-2024-change-in-prod")
_signer = URLSafeTimedSerializer(SECRET_KEY)
SESSION_COOKIE = "gc_session"
SESSION_MAX_AGE = 60 * 60 * 12  # 12 hours

# Simple PIN auth — role → PIN map
# In production: load from database; for clinic this is sufficient
STAFF_PINS: dict[str, str] = {
    "Reception":  os.getenv("PIN_RECEPTION",  "1234"),
    "ECG":        os.getenv("PIN_ECG",        "1234"),
    "Echo":       os.getenv("PIN_ECHO",       "1234"),
    "TMT":        os.getenv("PIN_TMT",        "1234"),
    "Doctor":     os.getenv("PIN_DOCTOR",     "5678"),
    "Manager":    os.getenv("PIN_MANAGER",    "9999"),
    "Admin":      os.getenv("PIN_ADMIN",      "0000"),
}

# Department config — maps role → queue department ID
DEPT_CONFIG = {
    "ECG":   {"id": "ECG",        "name": "ECG Lab",    "icon": "💓"},
    "Echo":  {"id": "Echo",       "name": "Echo Lab",   "icon": "🫀"},
    "TMT":   {"id": "TMT",        "name": "TMT",        "icon": "🏃"},
    "OPD":   {"id": "OPD",        "name": "OPD",        "icon": "🩺"},
    "XRay":  {"id": "X-Ray",      "name": "X-Ray",      "icon": "🦴"},
}

# Services available at reception
SERVICES = [
    {"id": "ECG",      "name": "ECG",      "icon": "💓"},
    {"id": "Echo",     "name": "Echo",     "icon": "🫀"},
    {"id": "TMT",      "name": "TMT",      "icon": "🏃"},
    {"id": "OPD",      "name": "OPD",      "icon": "🩺"},
    {"id": "X-Ray",    "name": "X-Ray",    "icon": "🦴"},
    {"id": "Lab",      "name": "Lab Test", "icon": "🧪"},
]

# Under construction departments
UNDER_CONSTRUCTION = [
    {"name": "Pharmacy",      "icon": "💊"},
    {"name": "HR & Payroll",  "icon": "👥"},
    {"name": "Inventory",     "icon": "📦"},
    {"name": "GST / Finance", "icon": "💼"},
    {"name": "Multi-Branch",  "icon": "🏢"},
    {"name": "AI Dietician",  "icon": "🥗"},
    {"name": "AI Prescription","icon": "📝"},
    {"name": "WhatsApp Alerts","icon": "💬"},
    {"name": "Video Consult", "icon": "📹"},
    {"name": "IPD Ward",      "icon": "🛏️"},
    {"name": "Vendor Mgmt",   "icon": "🤝"},
    {"name": "Analytics Pro", "icon": "📈"},
]


# ── Jinja2 Filters ─────────────────────────────────────────────────────────────
def format_time(value):
    """Format ISO timestamp or datetime to HH:MM AM/PM."""
    try:
        if isinstance(value, str):
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        elif isinstance(value, datetime):
            dt = value
        else:
            return str(value)
        ist = dt.astimezone(tz=None)
        return ist.strftime("%I:%M %p")
    except Exception:
        return str(value)


templates.env.filters["format_time"] = format_time


# ── Session Helpers ────────────────────────────────────────────────────────────
def create_session(role: str, name: str) -> str:
    payload = {"role": role, "name": name, "ts": datetime.now(timezone.utc).isoformat()}
    return _signer.dumps(payload)


def read_session(token: str) -> Optional[dict]:
    try:
        return _signer.loads(token, max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


def get_session(request: Request) -> Optional[dict]:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    return read_session(token)


def require_session(request: Request) -> dict:
    sess = get_session(request)
    if not sess:
        raise HTTPException(status_code=302, headers={"Location": "/staff/login"})
    return sess


# ── Queue helpers — fetch queue data via direct DB session ─────────────────────
async def _get_queue(request: Request, department: str | None = None,
                      status_filter: str | None = None) -> list[dict]:
    """Fetch queue entries directly via async session + repository.

    Uses async_session_factory directly instead of FastAPI Depends,
    so it can be called from any route handler.

    NOTE: The clinic only has a "Cardiology" department in the data model.
    The DEPT_CONFIG IDs (ECG, Echo, TMT, OPD) are service_codes, not actual
    department names. When a department is passed, it is treated as a
    service_code filter instead.
    """
    try:
        async with async_session_factory() as session:
            repo = SqlAlchemyQueueRepository(session)
            use_case = ListQueueUseCase(queue_repo=repo)

            # DEPT_CONFIG IDs (ECG, Echo, TMT, OPD) are service_codes, not
            # actual departments. All entries have department="Cardiology".
            # So we omit the department filter (use case defaults to
            # "Cardiology" → all entries), then filter by service_code if a
            # specific department view was requested.
            service_code_filter = None
            if department:
                service_code_filter = department

            cmd_data = {"status": status_filter}
            cmd = Command(data=cmd_data)
            result = await use_case.run(cmd)
            if result.is_fail:
                return []
            entries = result.data.get("entries", [])

            # Filter by service_code if department was specified
            if service_code_filter:
                entries = [
                    e for e in entries
                    if e.get("service_code", "").upper() == service_code_filter.upper()
                ]

            # Add wait_minutes helper
            now = datetime.now(timezone.utc)
            for e in entries:
                try:
                    created = datetime.fromisoformat(
                        str(e.get("created_at", "")).replace("Z", "+00:00")
                    )
                    e["wait_minutes"] = int((now - created).total_seconds() / 60)
                except Exception:
                    e["wait_minutes"] = 0
            return entries
    except Exception:
        return []


async def _get_stats(request: Request) -> dict:
    """Get today's queue summary stats."""
    try:
        all_entries = await _get_queue(request)
        waiting = sum(1 for e in all_entries if e.get("status") in ("WAITING", "CALLED"))
        in_progress = sum(1 for e in all_entries if e.get("status") == "IN_PROGRESS")
        completed = sum(1 for e in all_entries if e.get("status") in ("COMPLETED", "REPORT_READY", "DELIVERED"))
        patients = len(set(e.get("patient_id") for e in all_entries))
        return {"waiting": waiting, "in_progress": in_progress, "completed": completed, "total_patients": patients}
    except Exception:
        return {"waiting": 0, "in_progress": 0, "completed": 0, "total_patients": 0}


# ── Router ─────────────────────────────────────────────────────────────────────
router = APIRouter(prefix="/staff", tags=["Staff Dashboard"])


@router.get("/", include_in_schema=False)
async def staff_root(request: Request):
    sess = get_session(request)
    if sess:
        return RedirectResponse("/staff/home")
    return RedirectResponse("/staff/login")


# ── Auth ───────────────────────────────────────────────────────────────────────

@router.get("/login", include_in_schema=False)
async def login_page(request: Request):
    sess = get_session(request)
    if sess:
        return RedirectResponse("/staff/home")
    return templates.TemplateResponse("dashboard/login.html", {"request": request})


@router.post("/login", include_in_schema=False)
async def login_submit(
    request: Request,
    role: str = Form(...),
    name: str = Form(""),
    pin: str = Form(...),
):
    expected_pin = STAFF_PINS.get(role)
    if not expected_pin or pin.strip() != expected_pin:
        return templates.TemplateResponse("dashboard/login.html", {
            "request": request,
            "error": "❌ Wrong PIN. Please try again."
        })

    token = create_session(role=role, name=name or role)
    resp = RedirectResponse("/staff/home", status_code=303)
    resp.set_cookie(
        SESSION_COOKIE, token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return resp


@router.get("/logout", include_in_schema=False)
async def logout(request: Request):
    resp = RedirectResponse("/staff/login")
    resp.delete_cookie(SESSION_COOKIE)
    return resp


# ── Home ────────────────────────────────────────────────────────────────────────

@router.get("/home", include_in_schema=False)
async def home(request: Request):
    sess = get_session(request)
    if not sess:
        return RedirectResponse("/staff/login")
    stats = await _get_stats(request)
    return templates.TemplateResponse("dashboard/home.html", {
        "request": request,
        "active_page": "home",
        "session_user": sess,
        "stats": stats,
        "under_construction": UNDER_CONSTRUCTION,
    })


# ── Reception ──────────────────────────────────────────────────────────────────

@router.get("/reception", include_in_schema=False)
async def reception(request: Request):
    sess = get_session(request)
    if not sess:
        return RedirectResponse("/staff/login")
    queue_entries = await _get_queue(request)
    return templates.TemplateResponse("dashboard/reception.html", {
        "request": request,
        "active_page": "reception",
        "session_user": sess,
        "queue_entries": queue_entries,
        "services": SERVICES,
    })


# ── Department Technician Dashboards ──────────────────────────────────────────

async def _dept_page(request: Request, dept_key: str, active_page: str):
    sess = get_session(request)
    if not sess:
        return RedirectResponse("/staff/login")
    cfg = DEPT_CONFIG.get(dept_key, {"id": dept_key, "name": dept_key, "icon": "🏥"})
    all_entries = await _get_queue(request, department=cfg["id"])
    current = next((e for e in all_entries if e.get("status") == "IN_PROGRESS"), None)
    queue = [e for e in all_entries if e.get("status") != "DELIVERED"]
    return templates.TemplateResponse("dashboard/department.html", {
        "request": request,
        "active_page": active_page,
        "session_user": sess,
        "dept_id": cfg["id"],
        "dept_name": cfg["name"],
        "dept_icon": cfg["icon"],
        "current_patient": current,
        "queue": queue,
    })


@router.get("/ecg",  include_in_schema=False)
async def ecg(request: Request):  return await _dept_page(request, "ECG",  "ecg")

@router.get("/echo", include_in_schema=False)
async def echo(request: Request): return await _dept_page(request, "Echo", "echo")

@router.get("/tmt",  include_in_schema=False)
async def tmt(request: Request):  return await _dept_page(request, "TMT",  "tmt")

@router.get("/opd",  include_in_schema=False)
async def opd(request: Request):  return await _dept_page(request, "OPD",  "opd")


# ── Doctor ─────────────────────────────────────────────────────────────────────

@router.get("/doctor", include_in_schema=False)
async def doctor(request: Request):
    sess = get_session(request)
    if not sess:
        return RedirectResponse("/staff/login")
    return RedirectResponse("/api/v1/queue/doctor-dashboard-page")


# ── Manager ────────────────────────────────────────────────────────────────────

@router.get("/manager", include_in_schema=False)
async def manager(request: Request):
    sess = get_session(request)
    if not sess:
        return RedirectResponse("/staff/login")
    return RedirectResponse("/api/v1/queue/manager-dashboard")


# ── Billing ────────────────────────────────────────────────────────────────────

@router.get("/billing", include_in_schema=False)
async def billing(request: Request):
    sess = get_session(request)
    if not sess:
        return RedirectResponse("/staff/login")
    return templates.TemplateResponse("dashboard/base.html", {
        "request": request,
        "active_page": "billing",
        "session_user": sess,
    })


# ── TV Display ────────────────────────────────────────────────────────────────

@router.get("/tv", include_in_schema=False)
async def tv_display(request: Request):
    return RedirectResponse("/api/v1/queue/tv-display")


# ── Patient Status (NO LOGIN REQUIRED) ────────────────────────────────────────

@router.get("/patient-status", include_in_schema=False)
async def patient_status(request: Request, q: str = Query("")):
    sess = get_session(request)
    patient_entries = []
    query = q.strip()

    if query:
        all_entries = await _get_queue(request)
        patient_entries = [
            e for e in all_entries
            if query.lower() in str(e.get("patient_id", "")).lower()
            or query == str(e.get("token_number", ""))
        ]

    return templates.TemplateResponse("dashboard/patient_status.html", {
        "request": request,
        "active_page": "patient_status",
        "session_user": sess,
        "patient_entries": patient_entries,
        "query": query,
    })
