"""Admin Dashboard Routes — stats, overview, and quick actions."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import sqlalchemy as sa
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src.infrastructure.identity.models.admin_user_model import AdminUserModel
from src.shared.infrastructure.database import async_session_factory

logger = logging.getLogger(__name__)

# ── Jinja2 ────────────────────────────────────────────────────────────────────
import jinja2

_TEMPLATES_DIR = Path(__file__).parents[4] / "templates"
_jinja_loader = jinja2.FileSystemLoader(str(_TEMPLATES_DIR))
_jinja_env = jinja2.Environment(loader=_jinja_loader, auto_reload=True)
_jinja_env.cache = {}


def _render(name: str, **context) -> str:
    template = _jinja_env.get_template(name)
    return template.render(**context)


# ── Session helper (imported from auth_routes) ────────────────────────────────
from src.presentation.admin.routes.auth_routes import require_admin_session, get_admin_session

router = APIRouter(prefix="/admin", tags=["Admin Dashboard"])


# ═══════════════════════════════════════════════════════════════════════════════
# Dashboard Page
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/dashboard", include_in_schema=False)
async def admin_dashboard(request: Request):
    """Admin dashboard — overview of all clinics and licenses."""
    sess = require_admin_session(request)

    stats = {
        "total_clinics": 0,
        "active_licenses": 0,
        "expiring_soon": 0,  # within 30 days
        "expired": 0,
        "total_doctors": 0,
    }

    try:
        async with async_session_factory() as session:
            # Count clinics
            from src.infrastructure.clinic.models.clinic_model import ClinicModel
            row = await session.execute(sa.select(sa.func.count()).select_from(ClinicModel))
            stats["total_clinics"] = row.scalar() or 0

            # Active licenses
            row = await session.execute(
                sa.select(sa.func.count()).select_from(ClinicModel).where(
                    ClinicModel.is_license_active == True
                )
            )
            stats["active_licenses"] = row.scalar() or 0

            # Expiring within 30 days
            today = datetime.now(timezone.utc).date()
            thirty_days = today + timedelta(days=30)
            row = await session.execute(
                sa.select(sa.func.count()).select_from(ClinicModel).where(
                    ClinicModel.is_license_active == True,
                    ClinicModel.license_expiry_date <= thirty_days.isoformat(),
                    ClinicModel.license_expiry_date >= today.isoformat(),
                )
            )
            stats["expiring_soon"] = row.scalar() or 0

            # Expired
            row = await session.execute(
                sa.select(sa.func.count()).select_from(ClinicModel).where(
                    ClinicModel.is_license_active == False
                )
            )
            stats["expired"] = row.scalar() or 0

            stats["total_doctors"] = stats["total_clinics"]

    except Exception as e:
        logger.warning("Dashboard stats load error (may be first run): %s", e)
        # Stats remain 0 — ClinicModel table may not exist yet (first run before Block 6)

    return HTMLResponse(content=_render(
        "admin/dashboard.html",
        session=sess,
        stats=stats,
    ))
