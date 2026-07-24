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
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import sqlalchemy as sa
from fastapi import APIRouter, Cookie, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

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
    "Dietitian":  os.getenv("PIN_DIETITIAN",  "1234"),
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
    return HTMLResponse(content=_render("dashboard/login.html", request=request))


@router.post("/login", include_in_schema=False)
async def login_submit(
    request: Request,
    role: str = Form(...),
    name: str = Form(""),
    pin: str = Form(...),
):
    expected_pin = STAFF_PINS.get(role)
    if not expected_pin or pin.strip() != expected_pin:
        return HTMLResponse(content=_render("dashboard/login.html", request=request, error="❌ Wrong PIN. Please try again."))

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
    """Create default staff users for testing."""
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
async def ecg(request: Request):  return await _dept_page(request, "ECG",  "ecg")

@router.get("/echo", include_in_schema=False)
async def echo(request: Request): return await _dept_page(request, "Echo", "echo")

@router.get("/tmt",  include_in_schema=False)
async def tmt(request: Request):  return await _dept_page(request, "TMT",  "tmt")

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
    return HTMLResponse(content=_render("dashboard/base.html",
        request=request, active_page="billing", session_user=sess,
    ))


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
                        department="Cardiology",
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
                return {"ok": True, "patient_id": patient_id, "visit_id": visit_id, "entries": entries_created,
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
                    department="Cardiology",
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
            return {"ok": True, "patient_id": patient_id, "visit_id": visit_id, "entries": entries_created,
                    "message": f"{name} registered! Patient ID: {patient_id}"}

    except Exception as exc:
        return {"ok": False, "error": str(exc)}


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

from src.ai_engine.groq_client import call_groq
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
    )

    groq_key = os.getenv("GROQ_API_KEY", "")
    if not groq_key:
        return {"ok": False, "error": "GROQ_API_KEY not set in environment"}

    os.environ["GROQ_API_KEY"] = groq_key
    result = call_groq([prompt], temp=0.3)

    if not result:
        return {"ok": False, "error": "AI generation failed. Check API key."}

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
        clinic_name=body.get("clinic_name", "GIL CLINIC"),
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


# ── Seed Data (one-time test data for Railway) ─────────────────────────────────


@router.get("/seed", include_in_schema=False)
async def seed_test_data(request: Request):
    """Seed sample patients + queue entries for demo/testing."""
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
                    department="Cardiology",
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
