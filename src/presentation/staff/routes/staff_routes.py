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

import hashlib
import json
import logging
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import sqlalchemy as sa
from fastapi import APIRouter, Cookie, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

logger = logging.getLogger(__name__)

# ── Jinja2 template engine (direct, bypasses Starlette's wrapper) ────────────
import jinja2
_TEMPLATES_DIR = Path(__file__).parents[4] / "templates"
_jinja_loader = jinja2.FileSystemLoader(str(_TEMPLATES_DIR))
_jinja_env = jinja2.Environment(loader=_jinja_loader, auto_reload=True)
_jinja_env.cache = {}  # plain dict cache (avoids LRUCache bug)

def _render(name: str, **context) -> str:
    """Render a Jinja2 template and return HTML string."""
    template = _jinja_env.get_template(name)
    return template.render(**context)

# ── Queue DB access (used by _get_queue helper) ──────────────────────────────
from src.application.queue.use_cases.list_queue_use_case import ListQueueUseCase
from src.infrastructure.persistence.queue.repositories.queue_repository import (
    SqlAlchemyQueueRepository,
)
from src.application.common.command import Command
from src.shared.infrastructure.database import async_session_factory

# ── Session ───────────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "gil-clinic-secret-2024-change-in-prod")
_signer = URLSafeTimedSerializer(SECRET_KEY)
SESSION_COOKIE = "gc_session"
SESSION_MAX_AGE = 60 * 60 * 12  # 12 hours

# ── Public Patient Tracking Token (no login required) ────────────────────────
# Uses URLSafeSerializer (not timed) — token encodes patient_id, signed with SECRET_KEY.
# Patient receives this in WhatsApp: /track/<token>
from itsdangerous import URLSafeSerializer
_track_signer = URLSafeSerializer(SECRET_KEY, salt="patient-public-track-v1")

def _app_base_url() -> str:
    """APP_BASE_URL re-read every call — tunnel URL badle to restart ki zaroorat nahi."""
    return os.getenv("APP_BASE_URL", "http://localhost:8000")


def make_tracking_token(patient_id: str) -> str:
    """Create a signed public tracking token for a patient."""
    return _track_signer.dumps({"pid": patient_id})


def decode_tracking_token(token: str) -> Optional[str]:
    """Decode a public tracking token. Returns patient_id or None if invalid."""
    try:
        data = _track_signer.loads(token)
        return data.get("pid")
    except Exception:
        return None

# Simple PIN auth — role → PIN map
# In production: load from database; for clinic this is sufficient
STAFF_PINS: dict[str, str] = {
    "Reception":  os.getenv("PIN_RECEPTION")  or "1234",
    "ECG":        os.getenv("PIN_ECG")        or "1234",
    "Echo":       os.getenv("PIN_ECHO")       or "1234",
    "TMT":        os.getenv("PIN_TMT")        or "1234",
    "Doctor":     os.getenv("PIN_DOCTOR")     or "5678",
    "Manager":    os.getenv("PIN_MANAGER")    or "9999",
    "Admin":      os.getenv("PIN_ADMIN")      or "0000",
    "Dietitian":  os.getenv("PIN_DIETITIAN")  or "1234",
    "Dietician":  os.getenv("PIN_DIETITIAN")  or "1234",
}

# Department config — maps role → queue department ID
DEPT_CONFIG = {
    "ECG":   {"id": "ECG",        "name": "ECG Lab",    "icon": "💓"},
    "Echo":  {"id": "Echo",       "name": "Echo Lab",   "icon": "🫀"},
    "TMT":   {"id": "TMT",        "name": "TMT",        "icon": "🏃"},
    "OPD":   {"id": "OPD",        "name": "OPD",        "icon": "🩺"},
    "XRay":  {"id": "X-Ray",      "name": "X-Ray",      "icon": "🦴"},
    "Dietitian": {"id": "Dietitian", "name": "Dietitian", "icon": "🥗"},
}

# Services available at reception
SERVICES = [
    {"id": "ECG",      "name": "ECG",      "icon": "💓"},
    {"id": "Echo",     "name": "Echo",     "icon": "🫀"},
    {"id": "TMT",      "name": "TMT",      "icon": "🏃"},
    {"id": "OPD",      "name": "OPD",      "icon": "🩺"},
    {"id": "X-Ray",    "name": "X-Ray",    "icon": "🦴"},
    {"id": "Lab",      "name": "Lab Test", "icon": "🧪"},
    {"id": "Dietitian","name": "Dietitian","icon": "🥗"},
]

# Service → real department name. FIX: entries used to be created with
# department="Cardiology" for every service, which broke department views.
_SERVICE_DEPARTMENT = {
    "ECG": "ECG", "ECHO": "Echo", "TMT": "TMT", "OPD": "OPD",
    "X-RAY": "X-Ray", "XRAY": "X-Ray", "LAB": "Lab", "DIETITIAN": "Dietitian",
}


def department_for_service(code: str) -> str:
    """Map a service code to its department (fallback: the code itself)."""
    c = (code or "").strip()
    return _SERVICE_DEPARTMENT.get(c, _SERVICE_DEPARTMENT.get(c.upper(), c.upper() or "Cardiology"))

# Under construction departments
UNDER_CONSTRUCTION = [
    {"name": "Pharmacy",      "icon": "💊"},
    {"name": "HR & Payroll",  "icon": "👥"},
    {"name": "Inventory",     "icon": "📦"},
    {"name": "GST / Finance", "icon": "💼"},
    {"name": "Multi-Branch",  "icon": "🏢"},
    {"name": "WhatsApp Alerts","icon": "💬"},
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


_jinja_env.filters["format_time"] = format_time


# ── Session Helpers ────────────────────────────────────────────────────────────
def create_session(role: str, name: str, user_id: str = "", assigned_opds: str = "") -> str:
    payload = {
        "role": role, "name": name,
        "user_id": user_id, "assigned_opds": assigned_opds,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
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

            # Filter by service_code OR department (legacy rows use "Cardiology"
            # department with a service_code; new rows carry the real department)
            if service_code_filter:
                entries = [
                    e for e in entries
                    if e.get("service_code", "").upper() == service_code_filter.upper()
                    or e.get("department", "").upper() == service_code_filter.upper()
                ]

            # Collect patient_uuids & patient_ids to batch-fetch phone numbers
            patient_ids = list({e.get("patient_id", "") for e in entries if e.get("patient_id")})
            phone_map: dict[str, str] = {}
            if patient_ids:
                try:
                    from src.infrastructure.patient.models.patient_model import PatientModel
                    # NOTE: query by patient_id (String) only — PatientModel.id is
                    # a UUID column and passing raw strings raised
                    # "'str' object has no attribute 'hex'" on SQLite.
                    stmt = sa.select(PatientModel.patient_id, PatientModel.phone).where(
                        PatientModel.patient_id.in_(patient_ids)
                    )
                    rows = (await session.execute(stmt)).all()
                    for r in rows:
                        phone_map[str(r[0])] = r[1] or ""
                except Exception as ex:
                    logger.error("Phone lookup error: %s", ex)
            for e in entries:
                try:
                    created = datetime.fromisoformat(
                        str(e.get("created_at", "")).replace("Z", "+00:00")
                    )
                    e["wait_minutes"] = int((now - created).total_seconds() / 60)
                except Exception:
                    e["wait_minutes"] = 0
                # Attach phone number for WhatsApp sharing
                pid = e.get("patient_id", "")
                phone = phone_map.get(pid, "")
                e["patient_phone"] = phone
                e["phone"] = phone
            return entries
    except Exception as exc:
        logger.exception("_get_queue failed: %s", exc)
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

# Public router — no /staff prefix, for patient-facing routes (/track/{token})
public_router = APIRouter(tags=["Patient Tracking"])


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
    return HTMLResponse(content=_render("dashboard/login.html", request=request))


@router.post("/login", include_in_schema=False)
async def login_submit(
    request: Request,
    role: str = Form(...),
    name: str = Form(""),
    pin: str = Form(...),
):
    expected_pin = STAFF_PINS.get(role)
    if not expected_pin:
        for r_key, r_pin in STAFF_PINS.items():
            if r_key.lower() == role.lower():
                expected_pin = r_pin
                break
    if not expected_pin:
        expected_pin = "1234"

    # Strict PIN check — only the configured PIN for this role is accepted
    user_pin = pin.strip()
    if user_pin != expected_pin:
        return HTMLResponse(content=_render("dashboard/login.html", request=request, error="❌ Wrong PIN. Please try again."))

    token = create_session(role=role, name=name or role)
    target_url = "/staff/dietician" if role.lower() in ("dietitian", "dietician") else "/staff/home"
    resp = RedirectResponse(target_url, status_code=303)
    resp.set_cookie(
        SESSION_COOKIE, token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=True,
    )
    return resp


@router.get("/logout", include_in_schema=False)
async def logout(request: Request):
    resp = RedirectResponse("/staff/login")
    resp.delete_cookie(SESSION_COOKIE)
    return resp


# ── Phone + Password Login (for receptionists, doctors) ─────────────────────

@router.post("/phone-login", include_in_schema=False)
async def phone_login_submit(
    request: Request,
    phone: str = Form(""),
    password: str = Form(""),
):
    phone = phone.strip()
    if not phone or not password:
        return HTMLResponse(content=_render("dashboard/login.html", request=request, error="❌ Phone and password required."))

    try:
        from src.infrastructure.staff.models.staff_user_model import StaffUserModel
        async with async_session_factory() as session:
            row = await session.execute(
                sa.select(StaffUserModel).where(
                    StaffUserModel.phone == phone,
                    StaffUserModel.is_active == True,
                )
            )
            user = row.scalar_one_or_none()

            if not user or not user.password_hash:
                return HTMLResponse(content=_render("dashboard/login.html", request=request, error="❌ Invalid phone or password."))

            # Verify password
            import hashlib
            input_hash = hashlib.sha256(password.encode()).hexdigest()
            if input_hash != user.password_hash:
                return HTMLResponse(content=_render("dashboard/login.html", request=request, error="❌ Wrong password."))

            token = create_session(
                role=user.role.capitalize(),
                name=user.name,
                user_id=user.id,
                assigned_opds=user.assigned_opds,
            )
            resp = RedirectResponse("/staff/home", status_code=303)
            resp.set_cookie(
                SESSION_COOKIE, token,
                max_age=SESSION_MAX_AGE,
                httponly=True,
                samesite="lax",
            )
            return resp
    except Exception as exc:
        return HTMLResponse(content=_render("dashboard/login.html", request=request, error=f"❌ Login error: {exc}"))


# ── Seed Default Staff Users (one-time setup) ──────────────────────────────

@router.get("/seed-staff", include_in_schema=False)
async def seed_staff_users(request: Request):
    """Create default staff users for testing. ADMIN ONLY."""
    sess = get_session(request)
    if not sess or sess.get("role") not in ("admin", "Admin", "manager", "Manager"):
        return RedirectResponse("/staff/login", status_code=302)
    try:
        from src.infrastructure.staff.models.staff_user_model import StaffUserModel
        import hashlib

        defaults = [
            {
                "name": "Admin User",
                "phone": "9999999999",
                "password": "admin123",
                "pin": "1010",
                "role": "admin",
                "assigned_opds": '["ECG","Echo","TMT","OPD","X-Ray","Lab"]',
            },
            {
                "name": "Receptionist Bablu",
                "phone": "9876543210",
                "password": "reception123",
                "pin": "",
                "role": "receptionist",
                "assigned_opds": '["ECG","Echo","TMT","OPD","X-Ray","Lab"]',
            },
            {
                "name": "Dr. Singh (Cardio)",
                "phone": "9876543211",
                "password": "doctor123",
                "pin": "5554",
                "role": "doctor",
                "assigned_opds": '["OPD"]',
            },
        ]

        async with async_session_factory() as session:
            created = 0
            for u in defaults:
                existing = await session.execute(
                    sa.select(StaffUserModel).where(StaffUserModel.phone == u["phone"])
                )
                if existing.scalar_one_or_none():
                    continue
                user = StaffUserModel(
                    name=u["name"],
                    phone=u["phone"],
                    password_hash=hashlib.sha256(u["password"].encode()).hexdigest() if u["password"] else "",
                    pin=u["pin"],
                    role=u["role"],
                    assigned_opds=u["assigned_opds"],
                    is_active=True,
                )
                session.add(user)
                created += 1
            await session.commit()

        return HTMLResponse(content=f"""<html><body style="font-family:sans-serif;padding:40px">
<h2>✅ Staff Users Seeded</h2>
<p>Created: {created} users</p>
<ul>
<li><b>Admin</b> — 9999999999 / admin123 (full access)</li>
<li><b>Receptionist</b> — 9876543210 / reception123 (all OPDs)</li>
<li><b>Dr. Singh</b> — PIN 5554 (OPD only)</li>
</ul>
<p><a href="/staff/login">Go to Login →</a></p>
</body></html>""")
    except Exception as exc:
        return HTMLResponse(content=f"<html><body><h2>❌ Error</h2><pre>{exc}</pre></body></html>", status_code=500)


# ── Home ────────────────────────────────────────────────────────────────────────

@router.get("/home", include_in_schema=False)
async def home(request: Request):
    sess = get_session(request)
    if not sess:
        return RedirectResponse("/staff/login")
    stats = await _get_stats(request)
    return HTMLResponse(content=_render("dashboard/home.html",
        request=request, active_page="home", session_user=sess,
        stats=stats, under_construction=UNDER_CONSTRUCTION,
    ))


# ── Reception ──────────────────────────────────────────────────────────────────

@router.get("/reception", include_in_schema=False)
async def reception(request: Request):
    sess = get_session(request)
    if not sess:
        return RedirectResponse("/staff/login")
    queue_entries = await _get_queue(request)
    return HTMLResponse(content=_render("dashboard/reception.html",
        request=request, active_page="reception", session_user=sess,
        queue_entries=queue_entries, services=SERVICES,
    ))


# ── Department Technician Dashboards ──────────────────────────────────────────

async def _dept_page(request: Request, dept_key: str, active_page: str):
    sess = get_session(request)
    if not sess:
        return RedirectResponse("/staff/login")
    cfg = DEPT_CONFIG.get(dept_key, {"id": dept_key, "name": dept_key, "icon": "🏥"})
    all_entries = await _get_queue(request, department=cfg["id"])
    current = next((e for e in all_entries if e.get("status") == "IN_PROGRESS"), None)
    queue = [e for e in all_entries if e.get("status") != "DELIVERED"]
    return HTMLResponse(content=_render("dashboard/department.html",
        request=request, active_page=active_page, session_user=sess,
        dept_id=cfg["id"], dept_name=cfg["name"], dept_icon=cfg["icon"],
        current_patient=current, queue=queue,
    ))


@router.get("/ecg",  include_in_schema=False)
async def ecg(request: Request):  return await _dept_page(request, "ECG", "ecg")

@router.get("/echo", include_in_schema=False)
async def echo(request: Request): return await _dept_page(request, "Echo", "echo")

@router.get("/tmt",  include_in_schema=False)
async def tmt(request: Request):  return await _dept_page(request, "TMT", "tmt")

@router.get("/xray", include_in_schema=False)
async def xray(request: Request): return await _dept_page(request, "XRay", "xray")

@router.get("/lab", include_in_schema=False)
async def lab(request: Request):  return await _dept_page(request, "Lab", "lab")

@router.get("/opd",  include_in_schema=False)
async def opd(request: Request):  return await _dept_page(request, "OPD",  "opd")

@router.get("/dietitian", include_in_schema=False)
async def dietitian(request: Request): return RedirectResponse("/staff/dietician")


# ── Doctor ─────────────────────────────────────────────────────────────────────

@router.get("/doctor", include_in_schema=False)
async def doctor(request: Request):
    sess = get_session(request)
    if not sess:
        return RedirectResponse("/staff/login")
    return RedirectResponse("/opd/dashboard")


# ── Clinic Live Board (B5 — sab departments ek screen par) ─────────────────────

async def _live_board_snapshot(request: Request) -> dict:
    """Build a per-department live snapshot from today's queue."""
    entries = await _get_queue(request)
    dept_cfgs = list(DEPT_CONFIG.values()) + [{"id": "Lab", "name": "Lab Test", "icon": "🧪"}]
    departments = []
    for cfg in dept_cfgs:
        rows = [
            e for e in entries
            if e.get("service_code", "").upper() == cfg["id"].upper()
            or e.get("department", "").upper() == cfg["id"].upper()
        ]
        waiting = [e for e in rows if e.get("status") == "WAITING"]
        called = [e for e in rows if e.get("status") == "CALLED"]
        current = next((e for e in rows if e.get("status") == "IN_PROGRESS"), None)
        report_ready = [e for e in rows if e.get("status") in ("REPORT_READY", "COMPLETED")]
        departments.append({
            "id": cfg["id"],
            "name": cfg["name"],
            "icon": cfg["icon"],
            "waiting": len(waiting),
            "called": len(called),
            "current": current.get("patient_name") if current else None,
            "current_token": current.get("token_number") if current else None,
            "report_ready": len(report_ready),
            "top": [
                {"name": e.get("patient_name"), "token": e.get("token_number")}
                for e in (waiting + called)[:4]
            ],
        })
    total_waiting = sum(d["waiting"] for d in departments)
    total_report_ready = sum(d["report_ready"] for d in departments)
    return {
        "departments": departments,
        "total_waiting": total_waiting,
        "total_report_ready": total_report_ready,
    }


@router.get("/live-board", include_in_schema=False)
async def live_board_page(request: Request):
    sess = get_session(request)
    if not sess:
        return RedirectResponse("/staff/login")
    snap = await _live_board_snapshot(request)
    return HTMLResponse(content=_render("dashboard/live_board.html",
        request=request, active_page="live_board", session_user=sess,
        departments=snap["departments"],
        total_waiting=snap["total_waiting"],
        total_report_ready=snap["total_report_ready"],
    ))


@router.get("/api/live-board", include_in_schema=False)
async def api_live_board(request: Request):
    """JSON snapshot for the Live Board page (polled)."""
    sess = get_session(request)
    if not sess:
        return {"ok": False, "error": "Not logged in"}
    snap = await _live_board_snapshot(request)
    return {"ok": True, **snap}


# ── Manager ────────────────────────────────────────────────────────────────────

@router.get("/manager", include_in_schema=False)
async def manager(request: Request):
    return RedirectResponse("/staff/home")  # DISABLED

@router.get("/billing", include_in_schema=False)
async def billing(request: Request):
    return RedirectResponse("/staff/home")  # DISABLED

@router.get("/tv", include_in_schema=False)
async def tv_display(request: Request):
    return RedirectResponse("/staff/home")  # DISABLED


# ── Patient Status (REQUIRES LOGIN) ─────────────────────────────────────────

@router.get("/patient-status", include_in_schema=False)
async def patient_status(request: Request, q: str = Query("")):
    sess = get_session(request)
    if not sess:
        return RedirectResponse("/staff/login", status_code=302)
    patient_entries = []
    query = q.strip()

    if query:
        all_entries = await _get_queue(request)
        patient_entries = [
            e for e in all_entries
            if query.lower() in str(e.get("patient_id", "")).lower()
            or query == str(e.get("token_number", ""))
            or query.lower() in str(e.get("patient_name", "")).lower()
        ]
        # Also search by phone in PatientModel
        if not patient_entries and len(query) >= 10:
            try:
                from src.infrastructure.patient.models.patient_model import PatientModel
                async with async_session_factory() as session:
                    row = await session.execute(
                        sa.select(PatientModel).where(PatientModel.phone.contains(query))
                    )
                    p = row.scalar_one_or_none()
                    if p:
                        patient_entries = [
                            e for e in all_entries
                            if e.get("patient_id") == p.patient_id
                        ]
            except Exception:
                pass

    return HTMLResponse(content=_render("dashboard/patient_status.html",
        request=request, active_page="patient_status", session_user=sess,
        patient_entries=patient_entries, query=query,
    ))


# ── Staff API — Patient Registration (bypasses identity auth) ────────────────

@router.post("/api/register", include_in_schema=False)
async def staff_register_patient(request: Request):
    """Register a new patient and create queue entries — single endpoint.

    Uses staff session for auth (no identity token needed).
    Bypasses complex domain layer — inserts directly via SQLAlchemy models.
    """
    sess = get_session(request)
    if not sess:
        return {"ok": False, "error": "Not logged in"}

    try:
        body = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON body"}

    name = (body.get("name") or "").strip()
    phone = (body.get("phone") or "").strip()
    age = body.get("age", 30)
    gender = body.get("gender", "Male")
    services = body.get("services", [])
    complaints = (body.get("complaints") or "").strip()
    visit_type = body.get("visit_type", "New Visit")

    if not name:
        return {"ok": False, "error": "Patient name is required"}
    if phone and len(phone) < 10:
        return {"ok": False, "error": "Valid phone number (10+ digits) is required"}
    if not services:
        return {"ok": False, "error": "Select at least one test/service"}

    try:
        from src.infrastructure.patient.models.patient_model import PatientModel
        from src.infrastructure.queue.models.queue_entry_model import QueueEntryModel
        from src.shared.domain.base_entity import uuid7

        now = datetime.now(timezone.utc)
        date_prefix = now.strftime("%Y%m%d")
        phone_hash = hashlib.sha256(phone.encode()).hexdigest() if phone else ""

        async with async_session_factory() as session:
            existing_patient = None
            if phone:
                existing = await session.execute(
                    sa.select(PatientModel).where(PatientModel.phone_hash == phone_hash)
                )
                existing_patient = existing.scalar_one_or_none()

            if existing_patient:
                patient_id = existing_patient.patient_id
                patient_uuid = str(existing_patient.id)
                patient_name = existing_patient.name
                # ── Update visit tracking ──
                existing_patient.total_visits = (existing_patient.total_visits or 0) + 1
                existing_patient.last_visit_at = now
                # ── Create queue entries ──
                visit_id = f"VIS-{date_prefix}-{uuid7().hex[:6]}"
                entries_created = []
                for idx, code in enumerate(services):
                    token = await _next_token(session, code, date_prefix)
                    q = QueueEntryModel(
                        id=uuid7(),
                        visit_id=visit_id,
                        patient_id=patient_id,
                        patient_uuid=patient_uuid,
                        patient_name=patient_name,
                        service_code=code.upper(),
                        token_number=token,
                        department=department_for_service(code),
                        room="",
                        status="WAITING",
                        priority=0,
                        display_order=0,
                        notes=complaints,
                        created_by="reception",
                        updated_by="reception",
                        version=1,
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(q)
                    entries_created.append({"service": code, "token": token})
                await session.commit()
                # Generate WhatsApp notification data (with live tracking link)
                tracking_token = make_tracking_token(patient_id)
                tracking_url = f"{_tracking_base(request)}/track/{tracking_token}"
                whatsapp_links = []
                if phone:
                    from src.infrastructure.notification.whatsapp_cloud_api import (
                        build_patient_token_message, build_wa_me_url,
                    )
                    for entry in entries_created:
                        msg = build_patient_token_message(
                            patient_name, str(entry["token"]), entry["service"],
                            tracking_url=tracking_url,
                        )
                        whatsapp_links.append({
                            "service": entry["service"],
                            "token": entry["token"],
                            "url": build_wa_me_url(phone, msg),
                        })
                return {"ok": True, "patient_id": patient_id, "visit_id": visit_id,
                        "entries": entries_created, "whatsapp": whatsapp_links,
                        "tracking_url": tracking_url,
                        "message": f"{patient_name} — new test(s) added"}

            # ── New patient — create patient + queue entries ──
            seq_result = await session.execute(
                sa.select(sa.func.count(PatientModel.id)).where(
                    PatientModel.patient_id.like(f"CQ-{date_prefix}-%")
                )
            )
            seq = (seq_result.scalar() or 0) + 1
            patient_id = f"CQ-{date_prefix}-{seq:03d}"
            patient_uuid_obj = uuid7()

            patient = PatientModel(
                id=patient_uuid_obj,
                patient_id=patient_id,
                name=name,
                age=age,
                gender=gender,
                date_of_birth=f"{now.year - age}-01-01",
                phone=phone,
                phone_hash=phone_hash,
                address="",
                status="active",
                total_visits=1,
                last_visit_at=now,
                reception_inquiry=complaints,
                version=1,
                created_at=now,
                updated_at=now,
            )
            session.add(patient)

            # Create queue entries for each service
            visit_id = f"VIS-{date_prefix}-{uuid7().hex[:6]}"
            entries_created = []
            for code in services:
                token = await _next_token(session, code, date_prefix)
                q = QueueEntryModel(
                    id=uuid7(),
                    visit_id=visit_id,
                    patient_id=patient_id,
                    patient_uuid=str(patient_uuid_obj),
                    patient_name=name,
                    service_code=code.upper(),
                    token_number=token,
                    department=department_for_service(code),
                    room="",
                    status="WAITING",
                    priority=0,
                    display_order=0,
                    notes=complaints,
                    created_by="reception",
                    updated_by="reception",
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
                session.add(q)
                entries_created.append({"service": code, "token": token})

            await session.commit()
            # Generate WhatsApp notification data (with live tracking link)
            tracking_token = make_tracking_token(patient_id)
            tracking_url = f"{_tracking_base(request)}/track/{tracking_token}"
            whatsapp_links = []
            if phone:
                from src.infrastructure.notification.whatsapp_cloud_api import (
                    build_patient_token_message, build_wa_me_url,
                )
                for entry in entries_created:
                    msg = build_patient_token_message(
                        name, str(entry["token"]), entry["service"],
                        tracking_url=tracking_url,
                    )
                    whatsapp_links.append({
                        "service": entry["service"],
                        "token": entry["token"],
                        "url": build_wa_me_url(phone, msg),
                    })
            return {"ok": True, "patient_id": patient_id, "visit_id": visit_id,
                    "entries": entries_created, "whatsapp": whatsapp_links,
                    "tracking_url": tracking_url,
                    "message": f"{name} registered! Patient ID: {patient_id}"}

    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _tracking_base(request: Request) -> str:
    """Base URL for patient tracking links.

    Priority:
      1. APP_BASE_URL — jab wo public URL par set ho (tunnel/VM/domain).
         Staff LAN IP se app kholein tab bhi patient ko public link milega.
      2. Host header of the current request — jab staff public URL se
         directly app khole (APP_BASE_URL set nahi ho).
    """
    cfg = _app_base_url().strip().rstrip("/")
    if cfg and not cfg.startswith("http://localhost") and not cfg.startswith("http://127."):
        return cfg
    try:
        base = str(request.base_url).rstrip("/")
        if base:
            return base
    except Exception:
        pass
    return "http://localhost:8000"


async def _next_token(session, service_code: str, date_prefix: str) -> int:
    """Get next token number for a service today."""
    from src.infrastructure.queue.models.queue_entry_model import QueueEntryModel
    result = await session.execute(
        sa.select(sa.func.coalesce(sa.func.max(QueueEntryModel.token_number), 0)).where(
            sa.and_(
                QueueEntryModel.service_code == service_code.upper(),
                QueueEntryModel.visit_id.like(f"VIS-{date_prefix}-%"),
            )
        )
    )
    return (result.scalar() or 0) + 1


# ── AI Dietician ─────────────────────────────────────────────────────────────

from src.ai_engine.prompts import diet_plan_prompt


@router.get("/dietician", include_in_schema=False)
async def dietician_page(request: Request):
    sess = get_session(request)
    if not sess:
        return RedirectResponse("/staff/login")
    queue_entries = await _get_queue(request, department="Dietitian")
    return HTMLResponse(content=_render("dashboard/dietician.html",
        request=request, active_page="dietician", session_user=sess,
        queue_entries=queue_entries,
    ))


@router.post("/api/diet-plan", include_in_schema=False)
async def api_diet_plan(request: Request):
    sess = get_session(request)
    if not sess:
        return {"ok": False, "error": "Not logged in"}

    try:
        body = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON"}

    name = body.get("name", "").strip()
    if not name:
        return {"ok": False, "error": "Patient name required"}

    # Calculate BMI
    weight_str = body.get("weight", "0")
    height_str = body.get("height", "0")
    bmi = ""
    try:
        w = float(weight_str)
        h = float(height_str)
        if w > 0 and h > 0:
            bmi_val = w / ((h / 100) ** 2)
            bmi = f"{bmi_val:.1f} ({_bmi_category(bmi_val)})"
    except Exception:
        pass

    prompt = diet_plan_prompt(
        patient_name=name,
        age=body.get("age", ""),
        gender=body.get("gender", "Male"),
        weight=weight_str,
        height=height_str,
        bmi=bmi,
        conditions=body.get("conditions", ""),
        allergies=body.get("allergies", ""),
        goal=body.get("goal", "General health"),
        diet_type=body.get("diet_type", "Regular"),
        meals_per_day=body.get("meals_per_day", "3 main + 2 snacks"),
        restrictions=body.get("restrictions", ""),
        target_calories=body.get("target_calories", ""),
        protein_ratio=body.get("protein_ratio", "1.0"),
    )

    from src.ai_engine.provider_router import route_chat, sanitize_output
    from src.ai_engine.usage import log_ai_usage

    settings = {}
    try:
        from src.presentation.opd.routes.opd_routes import _ai_settings_for
        settings = await _ai_settings_for("clinic_default")
    except Exception:
        pass

    puter_text = str(body.get("puter_result") or "").strip()
    if puter_text:
        result, provider, model_used, usage = sanitize_output(puter_text), "puter", settings.get("ai_model") or "puter", {}
    else:
        routed = route_chat(settings, [prompt], feature="diet-plan", temp=0.3, max_tokens=4000)
        if routed.get("puter_needed"):
            return {"ok": False, "code": routed["code"], "prompt": routed["prompt"], "model": routed["model"]}
        result, provider, model_used, usage = routed.get("text") or "", routed.get("provider") or "", routed.get("model") or "", routed.get("usage") or {}
        if not result:
            await log_ai_usage(clinic_id=settings.get("clinic_id"), doctor_id="clinic_default",
                               feature="diet-plan", provider=provider or "none", model=model_used,
                               success=False, error=routed.get("error") or "")
            return {"ok": False, "error": routed.get("error") or "AI generation failed. Clinic owner: OPD → Settings → AI Provider."}

    await log_ai_usage(clinic_id=settings.get("clinic_id"), doctor_id="clinic_default",
                       feature="diet-plan", provider=provider, model=model_used, success=True,
                       prompt_tokens=int(usage.get("prompt_tokens") or 0),
                       completion_tokens=int(usage.get("completion_tokens") or 0))

    # Auto-update queue entry for Dietitian to REPORT_READY for inter-department sync
    visit_id = body.get("visit_id")
    if visit_id:
        try:
            async with async_session_factory() as session:
                from src.infrastructure.queue.models.queue_entry_model import QueueEntryModel
                stmt = (
                    sa.update(QueueEntryModel)
                    .where(QueueEntryModel.id == visit_id)
                    .values(status="REPORT_READY", updated_at=datetime.now(timezone.utc))
                )
                await session.execute(stmt)
                await session.commit()
        except Exception:
            pass

    return {"ok": True, "diet_plan": result}


@router.post("/api/diet-pdf", include_in_schema=False)
async def api_diet_pdf(request: Request):
    """Generate diet plan PDF."""
    sess = get_session(request)
    if not sess:
        return {"ok": False, "error": "Not logged in"}

    try:
        body = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON"}

    from src.utils.pdf_generator import make_diet_pdf

    pdf_bytes = make_diet_pdf(
        patient_name=body.get("patient_name", "Patient"),
        age=body.get("age", ""),
        gender=body.get("gender", ""),
        weight=body.get("weight", ""),
        height=body.get("height", ""),
        bmi=body.get("bmi", ""),
        conditions=body.get("conditions", ""),
        goal=body.get("goal", ""),
        diet_type=body.get("diet_type", ""),
        target_calories=body.get("target_calories", ""),
        diet_plan=body.get("diet_plan", ""),
        clinic_name=body.get("clinic_name", ""),
        doc_name=body.get("doc_name", "Dietitian"),
        phone=body.get("phone", ""),
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="DietPlan_{body.get("patient_name", "Patient")}.pdf"',
        },
    )


def _bmi_category(bmi: float) -> str:
    if bmi < 18.5: return "Underweight"
    if bmi < 25: return "Normal"
    if bmi < 30: return "Overweight"
    return "Obese"


@router.post("/api/ai-usage", include_in_schema=False)
async def api_staff_ai_usage(request: Request):
    """Browser gateway logs Puter-side AI calls here (staff pages) for metering."""
    sess = get_session(request)
    if not sess:
        return {"ok": False, "error": "Not logged in"}
    try:
        body = await request.json()
    except Exception:
        body = {}
    try:
        from src.ai_engine.usage import log_ai_usage
        await log_ai_usage(
            clinic_id=None,
            doctor_id="clinic_default",
            feature=str(body.get("feature") or "browser-ai")[:50],
            provider=str(body.get("provider") or "puter")[:40],
            model=str(body.get("model") or "")[:100],
            success=bool(body.get("success", True)),
            error=str(body.get("error") or "")[:500],
        )
    except Exception as e:
        logger.warning("staff ai-usage log failed: %s", e)
    return {"ok": True}


@router.get("/api/dietitian-queue", include_in_schema=False)
async def api_dietitian_queue(request: Request):
    """Return waiting Dietitian queue patients for frontend auto-load."""
    sess = get_session(request)
    if not sess:
        return {"ok": False, "error": "Not logged in"}
    entries = await _get_queue(request, department="Dietitian")
    # Enrich with patient details (age, gender, phone) from PatientModel
    enriched = []
    phone_map = {}
    try:
        from src.infrastructure.patient.models.patient_model import PatientModel
        async with async_session_factory() as session:
            for e in entries:
                pid = e.get("patient_id", "")
                if pid:
                    row = await session.execute(
                        sa.select(PatientModel).where(PatientModel.patient_id == pid)
                    )
                    p = row.scalar_one_or_none()
                    if p:
                        phone_map[pid] = {"phone": p.phone or "", "age": p.age or "",
                                          "gender": p.gender or ""}
            for e in entries:
                pid = e.get("patient_id", "")
                info = phone_map.get(pid, {})
                e["phone"] = info.get("phone", "")
                if not e.get("age"):
                    e["age"] = info.get("age", "")
                if not e.get("gender"):
                    e["gender"] = info.get("gender", "")
                enriched.append(e)
    except Exception:
        enriched = entries
    return {"ok": True, "entries": enriched}


@router.get("/api/dietitian-settings", include_in_schema=False)
async def api_dietitian_settings(request: Request):
    """Return WhatsApp settings for Dietitian page (reads from OPD settings)."""
    sess = get_session(request)
    if not sess:
        return {"ok": False, "error": "Not logged in"}
    try:
        from src.infrastructure.opd.models.opd_models import SettingsModel
        async with async_session_factory() as session:
            # Get the first available settings (or by doctor_id if set)
            row = await session.execute(
                sa.select(SettingsModel).where(SettingsModel.doctor_id == "chief")
            )
            s = row.scalar_one_or_none()
            if not s:
                # Try any settings record
                row = await session.execute(sa.select(SettingsModel).limit(1))
                s = row.scalar_one_or_none()
            if s:
                return {
                    "wa_reception": s.wa_reception or "",
                    "wa_manager": s.wa_manager or "",
                    "wa_doctor": s.wa_doctor or "",
                    "wa_dietitian": s.wa_dietitian or "",
                }
    except Exception:
        pass
    return {"wa_reception": "", "wa_manager": "", "wa_doctor": "", "wa_dietitian": ""}


# ── Public Patient Tracking (NO LOGIN REQUIRED) ───────────────────────────────
# This is the safe URL to send patients via WhatsApp: /track/{token}
# Shows only: Name, Token, Service, Status. No staff UI.

@public_router.get("/track/{public_token}", include_in_schema=False)
async def public_patient_track(request: Request, public_token: str):
    """Public patient status tracking — no login required.

    Decodes signed token → patient_id → fetches today's queue entries.
    Renders a clean minimal page with NO staff sidebar or navigation.
    """
    patient_id = decode_tracking_token(public_token)
    if not patient_id:
        return HTMLResponse(content=_render_track_error("Invalid or expired tracking link."), status_code=400)

    # Fetch all queue entries for this patient today
    try:
        all_entries = await _get_queue(request)
        patient_entries = [
            e for e in all_entries
            if e.get("patient_id") == patient_id
        ]
    except Exception:
        patient_entries = []

    patient_name = patient_entries[0].get("patient_name", patient_id) if patient_entries else patient_id

    return HTMLResponse(content=_render("patient_track.html",
        request=request,
        patient_name=patient_name,
        patient_id=patient_id,
        patient_entries=patient_entries,
        tracking_token=public_token,
    ))


@public_router.get("/track/{public_token}/status", include_in_schema=False)
async def public_patient_track_status(request: Request, public_token: str):
    """Live JSON status for the patient tracking page (polled every 8s).

    Lets the patient's phone show live "Called / In Progress / Report Ready"
    without a full page reload — the missing link in the call flow.
    """
    patient_id = decode_tracking_token(public_token)
    if not patient_id:
        return {"ok": False, "error": "Invalid tracking link"}

    try:
        all_entries = await _get_queue(request)
        patient_entries = [
            e for e in all_entries
            if e.get("patient_id") == patient_id
        ]
    except Exception as exc:
        logger.exception("track status failed: %s", exc)
        patient_entries = []

    return {
        "ok": True,
        "patient_name": patient_entries[0].get("patient_name", patient_id) if patient_entries else patient_id,
        "entries": [
            {
                "service_code": e.get("service_code", ""),
                "token_number": e.get("token_number", ""),
                "status": e.get("status", "WAITING"),
                "department": e.get("department", ""),
                "room": e.get("room", ""),
            }
            for e in patient_entries
        ],
    }


def _render_track_error(msg: str) -> str:
    """Render a minimal error page for invalid tracking links."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Invalid Link — GIL Clinic</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           background: #f7fafc; display: flex; align-items: center;
           justify-content: center; min-height: 100vh; margin: 0; }}
    .box {{ background: white; border-radius: 16px; padding: 40px; text-align: center;
            box-shadow: 0 4px 24px rgba(0,0,0,0.08); max-width: 340px; width: 90%; }}
    .icon {{ font-size: 48px; margin-bottom: 16px; }}
    h2 {{ color: #c53030; margin: 0 0 8px; font-size: 20px; }}
    p {{ color: #718096; font-size: 14px; line-height: 1.6; }}
    a {{ color: #667eea; text-decoration: none; font-weight: 600; }}
  </style>
</head>
<body>
  <div class="box">
    <div class="icon">🔗</div>
    <h2>Invalid Link</h2>
    <p>{msg}</p>
    <p style="margin-top:16px;">Please contact GIL Clinic reception for a new tracking link.</p>
  </div>
</body>
</html>"""


# ── Seed Data (one-time test data for Railway) ─────────────────────────────────


@router.get("/seed", include_in_schema=False)
async def seed_test_data(request: Request):
    """Seed sample data. ADMIN ONLY."""
    sess = get_session(request)
    if not sess or sess.get("role") not in ("admin", "Admin", "manager", "Manager"):
        return RedirectResponse("/staff/login", status_code=302)
    try:
        from src.infrastructure.patient.models.patient_model import PatientModel
        from src.infrastructure.queue.models.queue_entry_model import QueueEntryModel
        from src.shared.domain.base_entity import uuid7

        now = datetime.now(timezone.utc)
        date_prefix = now.strftime("%Y%m%d")

        sample_patients = [
            {"name": "Amar Singh",     "age": 45, "gender": "Male",   "phone": "9876543210", "service": "ECG",  "status": "WAITING"},
            {"name": "Baldev Kaur",    "age": 52, "gender": "Female", "phone": "9876543211", "service": "Echo", "status": "COMPLETED"},
            {"name": "Charanjit Singh","age": 38, "gender": "Male",   "phone": "9876543212", "service": "TMT",  "status": "IN_PROGRESS"},
            {"name": "Davinder Kaur",  "age": 60, "gender": "Female", "phone": "9876543213", "service": "OPD",  "status": "WAITING"},
            {"name": "Ekamjot Singh",  "age": 28, "gender": "Male",   "phone": "9876543214", "service": "ECG",  "status": "CALLED"},
            {"name": "Gurpreet Kaur",  "age": 35, "gender": "Female", "phone": "9876543215", "service": "Echo", "status": "WAITING"},
        ]

        async with async_session_factory() as session:
            created_patients = 0
            created_entries = 0

            for i, p in enumerate(sample_patients):
                # Generate patient_id: CQ-YYYYMMDD-NNN
                patient_id = f"CQ-{date_prefix}-{i+1:03d}"
                phone_hash = hashlib.sha256(p["phone"].encode()).hexdigest()

                # Check if patient already exists
                existing = await session.execute(
                    sa.select(PatientModel).where(
                        PatientModel.patient_id == patient_id
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                # Create patient
                patient = PatientModel(
                    id=uuid7(),
                    patient_id=patient_id,
                    name=p["name"],
                    age=p["age"],
                    gender=p["gender"],
                    date_of_birth=f"{now.year - p['age']}-01-01",
                    phone=p["phone"],
                    phone_hash=phone_hash,
                    address=f"#{i+1}, Sample Street, Amritsar",
                    status="active",
                    total_visits=0,
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
                session.add(patient)

                # Create visit_id: VIS-YYYYMMDD-ffffff
                visit_id = f"VIS-{date_prefix}-{i+1:06d}"

                # Create queue entry
                token = i + 1
                status = p["status"]
                q = QueueEntryModel(
                    id=uuid7(),
                    visit_id=visit_id,
                    patient_id=patient_id,
                    patient_uuid=str(patient.id),
                    patient_name=p["name"],
                    service_code=p["service"],
                    token_number=token,
                    department=department_for_service(p["service"]),
                    room="",
                    status=status,
                    priority=0,
                    display_order=0 if status in ("WAITING", "CALLED", "IN_PROGRESS") else 99,
                    created_by="seed",
                    updated_by="seed",
                    version=1,
                    created_at=now,
                    updated_at=now,
                )

                # Set timestamps based on status
                if status == "IN_PROGRESS":
                    q.called_at = now
                    q.started_at = now
                elif status == "CALLED":
                    q.called_at = now
                elif status == "COMPLETED":
                    q.called_at = now
                    q.started_at = now
                    q.completed_at = now

                session.add(q)
                created_entries += 1
                created_patients += 1

            await session.commit()

        return HTMLResponse(content=f"""<html><body style="font-family:sans-serif;padding:40px">
<h2>✅ Seed Data Created</h2>
<p>Patients: {created_patients}</p>
<p>Queue Entries: {created_entries}</p>
<p><a href="/staff/home">Go to Dashboard →</a></p>
</body></html>""")
    except Exception as exc:
        return HTMLResponse(content=f"""<html><body style="font-family:sans-serif;padding:40px">
<h2>❌ Seed Failed</h2>
<pre>{exc}</pre>
</body></html>""", status_code=500)
