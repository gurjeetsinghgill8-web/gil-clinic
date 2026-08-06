"""Clinic Authentication Routes — Multi-tenant clinic login.

POST /clinic/login — Validates clinic_username + password, sets session with clinic_id.
GET  /clinic/logout — Clears session.

Session stores clinic_id which is used by all routes to scope data.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import bcrypt
import sqlalchemy as sa
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from src.infrastructure.clinic.models.clinic_model import ClinicModel
from src.shared.infrastructure.database import async_session_factory

logger = logging.getLogger(__name__)

# ── Session ───────────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "gil-clinic-secret-2024-change-in-prod")
_signer = URLSafeTimedSerializer(SECRET_KEY)
SESSION_COOKIE = "gc_session"  # Same cookie as staff login for compatibility
SESSION_MAX_AGE = 60 * 60 * 12  # 12 hours

# ── Jinja2 ────────────────────────────────────────────────────────────────────
import jinja2

_TEMPLATES_DIR = Path(__file__).parents[4] / "templates"
_jinja_loader = jinja2.FileSystemLoader(str(_TEMPLATES_DIR))
_jinja_env = jinja2.Environment(loader=_jinja_loader, auto_reload=True)
_jinja_env.cache = {}


def _render(name: str, **context) -> str:
    template = _jinja_env.get_template(name)
    return template.render(**context)


router = APIRouter(prefix="/clinic", tags=["Clinic Auth"])


# ═══════════════════════════════════════════════════════════════════════════════
# Clinic Login
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/login", include_in_schema=False)
async def clinic_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    """Authenticate a clinic by username + password.

    Looks up ClinicModel by clinic_username, verifies bcrypt password,
    checks license expiry, and sets a signed session cookie with clinic_id.
    """
    username = username.strip()
    password = password.strip()

    if not username or not password:
        return HTMLResponse(
            content=_render("dashboard/login.html", error="❌ Username and password required."),
            status_code=401,
        )

    try:
        async with async_session_factory() as session:
            row = await session.execute(
                sa.select(ClinicModel).where(
                    ClinicModel.clinic_username == username,
                    ClinicModel.is_active == True,
                )
            )
            clinic = row.scalar_one_or_none()

            if not clinic:
                logger.warning("Clinic login failed: unknown username '%s'", username)
                return HTMLResponse(
                    content=_render("dashboard/login.html", error="❌ Invalid username or password."),
                    status_code=401,
                )

            # Check license expiry
            from datetime import date

            try:
                expiry = date.fromisoformat(str(clinic.license_expiry_date)[:10])
                today = date.today()

                if clinic.is_license_active and expiry < today:
                    # License expired — mark inactive
                    clinic.is_license_active = False
                    await session.commit()
                    logger.info("License expired for %s", clinic.clinic_code)

                if not clinic.is_license_active:
                    return HTMLResponse(
                        content=_render(
                            "dashboard/login.html",
                            error=f"🚫 License expired ({clinic.license_expiry_date}). Contact admin for renewal.",
                        ),
                        status_code=401,
                    )

                # Warning: expiring within 3 days
                days_left = (expiry - today).days
                if 0 <= days_left <= 3 and clinic.is_license_active:
                    logger.info(
                        "License expiring soon: %s | %d days left",
                        clinic.clinic_code, days_left,
                    )
                    # Show warning but allow login
            except (ValueError, TypeError):
                pass  # Skip expiry check if date is malformed

            # Verify password
            if clinic.clinic_password_hash:
                if not bcrypt.checkpw(
                    password.encode("utf-8"),
                    clinic.clinic_password_hash.encode("utf-8"),
                ):
                    return HTMLResponse(
                        content=_render("dashboard/login.html", error="❌ Invalid username or password."),
                        status_code=401,
                    )
            else:
                # No password set — fallback to default "1234"
                if password != "1234":
                    return HTMLResponse(
                        content=_render("dashboard/login.html", error="❌ Invalid username or password."),
                        status_code=401,
                    )

            # Success — create session
            payload = {
                "role": "Doctor",
                "user_id": str(clinic.id),
                "name": clinic.doctor_name,
                "clinic_id": str(clinic.id),
                "clinic_code": clinic.clinic_code,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
            token = _signer.dumps(payload)

            resp = RedirectResponse("/staff/home", status_code=303)
            resp.set_cookie(
                SESSION_COOKIE,
                token,
                max_age=SESSION_MAX_AGE,
                httponly=True,
                samesite="lax",
            )
            logger.info(
                "Clinic logged in: %s | %s", clinic.clinic_code, clinic.doctor_name
            )
            return resp

    except Exception as e:
        logger.error("Clinic login error: %s", e)
        return HTMLResponse(
            content=_render("dashboard/login.html", error="⚠️ System error. Please try again."),
            status_code=500,
        )


@router.get("/logout", include_in_schema=False)
async def clinic_logout():
    """Clear clinic session."""
    resp = RedirectResponse("/staff/login")
    resp.delete_cookie(SESSION_COOKIE)
    return resp
