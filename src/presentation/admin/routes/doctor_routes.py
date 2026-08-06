"""Doctor Onboarding API — admin adds new doctors/clinics.

POST /admin/api/onboard — Creates clinic + auto-generates credentials
GET /admin/onboard — Onboarding form page
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path

import bcrypt
import sqlalchemy as sa
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from src.infrastructure.clinic.models.clinic_model import ClinicModel
from src.infrastructure.clinic.services.credential_generator import generate_all_credentials
from src.infrastructure.persistence.clinic_repository import ClinicRepository
from src.shared.infrastructure.database import async_session_factory

logger = logging.getLogger(__name__)

# ── Session ───────────────────────────────────────────────────────────────────
from src.presentation.admin.routes.auth_routes import require_admin_session

# ── Jinja2 ────────────────────────────────────────────────────────────────────
import jinja2

_TEMPLATES_DIR = Path(__file__).parents[4] / "templates"
_jinja_loader = jinja2.FileSystemLoader(str(_TEMPLATES_DIR))
_jinja_env = jinja2.Environment(loader=_jinja_loader, auto_reload=True)
_jinja_env.cache = {}


def _render(name: str, **context) -> str:
    template = _jinja_env.get_template(name)
    return template.render(**context)


router = APIRouter(prefix="/admin", tags=["Doctor Onboarding"])


# ═══════════════════════════════════════════════════════════════════════════════
# Onboarding Form Page
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/onboard", include_in_schema=False)
async def onboard_page(request: Request):
    """Doctor onboarding form page."""
    sess = require_admin_session(request)
    return HTMLResponse(content=_render("admin/onboard_doctor.html", session=sess, result=None, error=None))


# ═══════════════════════════════════════════════════════════════════════════════
# Onboarding API
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/api/onboard", include_in_schema=False)
async def api_onboard_doctor(
    request: Request,
    doctor_name: str = Form(...),
    doctor_phone: str = Form(""),
    doctor_email: str = Form(""),
    clinic_name: str = Form(...),
    address: str = Form(""),
    city: str = Form(""),
    state: str = Form(""),
    doctor_degree: str = Form(""),
    doctor_reg_no: str = Form(""),
    specialty: str = Form("General Physician"),
    license_duration: int = Form(2),  # 2, 3, or 4 months
):
    """Create a new clinic + doctor with auto-generated credentials."""
    sess = require_admin_session(request)

    if not doctor_name.strip() or not clinic_name.strip():
        return HTMLResponse(
            content=_render("admin/onboard_doctor.html", session=sess, error="Doctor name and clinic name are required."),
            status_code=400,
        )

    try:
        async with async_session_factory() as session:
            repo = ClinicRepository(session)

            # Get current clinic count for sequential code
            clinic_count_row = await session.execute(
                sa.select(sa.func.count()).select_from(ClinicModel)
            )
            clinic_count = clinic_count_row.scalar() or 0

            # Generate credentials
            creds = generate_all_credentials(doctor_name.strip(), clinic_count)

            # Hash password
            password_hash = bcrypt.hashpw(
                creds["clinic_password"].encode("utf-8"),
                bcrypt.gensalt(rounds=12),
            ).decode("utf-8")

            # Calculate license dates
            today = date.today()
            expiry = today + timedelta(days=license_duration * 30)

            # Create clinic
            clinic = ClinicModel(
                clinic_name=clinic_name.strip(),
                clinic_code=creds["clinic_code"],
                doctor_name=doctor_name.strip(),
                doctor_phone=doctor_phone.strip(),
                doctor_email=doctor_email.strip(),
                doctor_degree=doctor_degree.strip(),
                doctor_reg_no=doctor_reg_no.strip(),
                specialty=specialty.strip(),
                address=address.strip(),
                city=city.strip(),
                state=state.strip(),
                clinic_username=creds["clinic_username"],
                clinic_password_hash=password_hash,
                doctor_opd_pin=creds["doctor_opd_pin"],
                dietician_pin=creds["dietician_pin"],
                staff_default_pin="1234",
                license_start_date=today.isoformat(),
                license_expiry_date=expiry.isoformat(),
                license_duration_months=license_duration,
                is_license_active=True,
                created_by=sess.get("username", "unknown"),
            )

            await repo.create(clinic)
            await session.commit()

            logger.info(
                "Doctor onboarded: %s | Clinic: %s | Username: %s",
                doctor_name, creds["clinic_code"], creds["clinic_username"],
            )

            return HTMLResponse(content=_render(
                "admin/onboard_doctor.html",
                session=sess,
                result={
                    "doctor_name": doctor_name.strip(),
                    "clinic_name": clinic_name.strip(),
                    "clinic_code": creds["clinic_code"],
                    "username": creds["clinic_username"],
                    "password": creds["clinic_password"],
                    "opd_pin": creds["doctor_opd_pin"],
                    "dietician_pin": creds["dietician_pin"],
                    "staff_pin": "1234",
                    "expiry_date": expiry.isoformat(),
                    "duration_months": license_duration,
                },
                error=None,
            ))

    except Exception as e:
        logger.error("Onboarding error: %s", e)
        return HTMLResponse(
            content=_render("admin/onboard_doctor.html", session=sess, error=f"System error: {str(e)}"),
            status_code=500,
        )
