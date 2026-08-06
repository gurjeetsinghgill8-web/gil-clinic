"""Admin Authentication Routes — Super Admin & CEO login.

Uses itsdangerous signed cookies (same pattern as staff_routes.py)
with bcrypt password verification and rate limiting.

Session cookie: admin_session (httponly, 8hr max age)
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bcrypt
import sqlalchemy as sa
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from src.infrastructure.identity.models.admin_user_model import AdminUserModel
from src.shared.infrastructure.database import async_session_factory

logger = logging.getLogger(__name__)

# ── Session ───────────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "gil-clinic-secret-2024-change-in-prod")
_signer = URLSafeTimedSerializer(SECRET_KEY)
SESSION_COOKIE = "admin_session"
SESSION_MAX_AGE = 60 * 60 * 8  # 8 hours

# ── Rate limiting ─────────────────────────────────────────────────────────────
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 15

# ── Jinja2 ────────────────────────────────────────────────────────────────────
import jinja2

_TEMPLATES_DIR = Path(__file__).parents[4] / "templates"
_jinja_loader = jinja2.FileSystemLoader(str(_TEMPLATES_DIR))
_jinja_env = jinja2.Environment(loader=_jinja_loader, auto_reload=True)
_jinja_env.cache = {}


def _render(name: str, **context) -> str:
    template = _jinja_env.get_template(name)
    return template.render(**context)


# ── Router ────────────────────────────────────────────────────────────────────
router = APIRouter(prefix="/admin", tags=["Admin Auth"])


# ═══════════════════════════════════════════════════════════════════════════════
# Session Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _create_admin_session(admin_id: str, username: str, role: str, display_name: str = "") -> str:
    """Create a signed admin session token."""
    payload = {
        "admin_id": admin_id,
        "username": username,
        "role": role,
        "display_name": display_name,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    return _signer.dumps(payload)


def _read_admin_session(token: str) -> dict | None:
    """Read and validate an admin session token."""
    try:
        return _signer.loads(token, max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


def get_admin_session(request: Request) -> dict | None:
    """Extract admin session from request cookies."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    return _read_admin_session(token)


def require_admin_session(request: Request) -> dict:
    """Get admin session or raise redirect to login."""
    sess = get_admin_session(request)
    if not sess:
        raise HTTPException(status_code=302, headers={"Location": "/admin/login"})
    return sess


# ═══════════════════════════════════════════════════════════════════════════════
# Routes
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/", include_in_schema=False)
async def admin_root(request: Request):
    """Redirect to dashboard if logged in, else login."""
    sess = get_admin_session(request)
    if sess:
        return RedirectResponse("/admin/dashboard")
    return RedirectResponse("/admin/login")


@router.get("/login", include_in_schema=False)
async def admin_login_page(request: Request, error: str = ""):
    """Admin login page."""
    sess = get_admin_session(request)
    if sess:
        return RedirectResponse("/admin/dashboard")
    return HTMLResponse(content=_render("admin/login.html", error=error))


@router.post("/login", include_in_schema=False)
async def admin_login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    """Authenticate admin user with username + password."""
    username = username.strip()
    password = password.strip()

    if not username or not password:
        return HTMLResponse(
            content=_render("admin/login.html", error="❌ Username and password required."),
            status_code=401,
        )

    try:
        async with async_session_factory() as session:
            # Look up admin user
            row = await session.execute(
                sa.select(AdminUserModel).where(
                    AdminUserModel.username == username,
                    AdminUserModel.is_active == True,
                )
            )
            admin = row.scalar_one_or_none()

            if not admin:
                logger.warning("Admin login failed: unknown username '%s'", username)
                return HTMLResponse(
                    content=_render("admin/login.html", error="❌ Invalid username or password."),
                    status_code=401,
                )

            # Check lockout
            if admin.locked_until and admin.locked_until > datetime.now(timezone.utc):
                remaining = int((admin.locked_until - datetime.now(timezone.utc)).total_seconds() // 60)
                return HTMLResponse(
                    content=_render(
                        "admin/login.html",
                        error=f"🔒 Account locked. Try again in {remaining} minutes.",
                    ),
                    status_code=401,
                )

            # Verify password
            if not bcrypt.checkpw(password.encode("utf-8"), admin.password_hash.encode("utf-8")):
                admin.login_attempts += 1
                if admin.login_attempts >= MAX_LOGIN_ATTEMPTS:
                    admin.locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)
                    admin.login_attempts = 0
                    logger.warning("Admin account '%s' locked after %d failed attempts", username, MAX_LOGIN_ATTEMPTS)
                await session.commit()
                return HTMLResponse(
                    content=_render("admin/login.html", error="❌ Invalid username or password."),
                    status_code=401,
                )

            # Success — reset attempts, update last login
            admin.login_attempts = 0
            admin.locked_until = None
            admin.last_login = datetime.now(timezone.utc)
            await session.commit()

            # Create session
            token = _create_admin_session(
                admin_id=str(admin.id),
                username=admin.username,
                role=admin.role,
                display_name=admin.display_name,
            )

            resp = RedirectResponse("/admin/dashboard", status_code=303)
            resp.set_cookie(
                SESSION_COOKIE,
                token,
                max_age=SESSION_MAX_AGE,
                httponly=True,
                samesite="lax",
                secure=False,  # Set True in production with HTTPS
            )
            logger.info("Admin '%s' (%s) logged in successfully", username, admin.role)
            return resp

    except Exception as e:
        logger.error("Admin login error: %s", e)
        return HTMLResponse(
            content=_render("admin/login.html", error="⚠️ System error. Please try again."),
            status_code=500,
        )


@router.get("/logout", include_in_schema=False)
async def admin_logout():
    """Clear admin session and redirect to login."""
    resp = RedirectResponse("/admin/login")
    resp.delete_cookie(SESSION_COOKIE)
    return resp


# ═══════════════════════════════════════════════════════════════════════════════
# Seed Default Admin Accounts (call on first startup)
# ═══════════════════════════════════════════════════════════════════════════════


async def seed_default_admins():
    """Create default super_admin and ceo accounts if they don't exist.

    Called once at application startup. Passwords are loaded from env vars
    or generated with defaults.

    SUPER_ADMIN: 16-char auto-generated password (emailed to Gurjeet)
    CEO: 12-char fixed password (set by Gurjeet)
    """
    try:
        async with async_session_factory() as session:
            # Check if super_admin exists
            row = await session.execute(
                sa.select(AdminUserModel).where(AdminUserModel.role == "super_admin")
            )
            existing_sa = row.scalar_one_or_none()

            if not existing_sa:
                # Generate 16-char password for super_admin
                import secrets
                import string

                sa_password = os.getenv(
                    "SUPER_ADMIN_PASSWORD",
                    "".join(secrets.choice(string.ascii_letters + string.digits + "!@#$%^&*") for _ in range(16)),
                )
                sa_hash = bcrypt.hashpw(sa_password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")

                sa_admin = AdminUserModel(
                    username=os.getenv("SUPER_ADMIN_USERNAME", "superadmin"),
                    password_hash=sa_hash,
                    role="super_admin",
                    display_name="Technical Admin",
                    email=os.getenv("SUPER_ADMIN_EMAIL", ""),
                )
                session.add(sa_admin)
                await session.commit()
                logger.info("✅ Super Admin account seeded (username: %s)", sa_admin.username)
                # Print password so Gurjeet can save it (only on first run)
                print(f"\n{'='*60}")
                print(f"🔐 SUPER ADMIN CREDENTIALS (SAVE THESE!)")
                print(f"   Username: {sa_admin.username}")
                print(f"   Password: {sa_password}")
                print(f"{'='*60}\n")

            # Check if ceo exists
            row = await session.execute(
                sa.select(AdminUserModel).where(AdminUserModel.role == "ceo")
            )
            existing_ceo = row.scalar_one_or_none()

            if not existing_ceo:
                ceo_password = os.getenv("CEO_PASSWORD", "ceo123456789")  # 12-char default
                ceo_hash = bcrypt.hashpw(ceo_password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")

                ceo_admin = AdminUserModel(
                    username=os.getenv("CEO_USERNAME", "ceo"),
                    password_hash=ceo_hash,
                    role="ceo",
                    display_name="CEO",
                    email=os.getenv("CEO_EMAIL", ""),
                )
                session.add(ceo_admin)
                await session.commit()
                logger.info("✅ CEO account seeded (username: %s)", ceo_admin.username)
                print(f"\n{'='*60}")
                print(f"🔐 CEO CREDENTIALS (SAVE THESE!)")
                print(f"   Username: {ceo_admin.username}")
                print(f"   Password: {ceo_password}")
                print(f"{'='*60}\n")

    except Exception as e:
        logger.error("Failed to seed admin accounts: %s", e)
