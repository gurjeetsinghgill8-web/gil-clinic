"""Staff Settings Routes — PIN change, preferences.

GET  /staff/settings   → Settings page
POST /staff/api/change-pin → Change staff PIN
"""

from __future__ import annotations

import logging
from pathlib import Path

import sqlalchemy as sa
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from src.infrastructure.clinic.models.staff_pin_model import StaffPinModel
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


# ── Session ───────────────────────────────────────────────────────────────────
from src.presentation.staff.routes.staff_routes import get_session

router = APIRouter(prefix="/staff", tags=["Staff Settings"])


@router.get("/settings", include_in_schema=False)
async def settings_page(request: Request):
    """Staff settings page."""
    sess = get_session(request)
    if not sess:
        from fastapi.responses import RedirectResponse
        return RedirectResponse("/staff/login")
    return HTMLResponse(content=_render("dashboard/settings.html"))


@router.post("/api/change-pin", include_in_schema=False)
async def api_change_pin(request: Request):
    """Change staff PIN for current user's role and clinic."""
    sess = get_session(request)
    if not sess:
        return {"ok": False, "error": "Not logged in"}

    try:
        body = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON"}

    current_pin = (body.get("current_pin") or "").strip()
    new_pin = (body.get("new_pin") or "").strip()

    if not current_pin or not new_pin:
        return {"ok": False, "error": "Current and new PIN required"}
    if len(new_pin) != 4 or not new_pin.isdigit():
        return {"ok": False, "error": "PIN must be exactly 4 digits"}

    role = sess.get("role", "")
    clinic_id = sess.get("clinic_id", "")
    if not role:
        return {"ok": False, "error": "Role not found in session"}

    try:
        async with async_session_factory() as session:
            # Look up existing PIN
            row = await session.execute(
                sa.select(StaffPinModel).where(
                    StaffPinModel.clinic_id == clinic_id,
                    StaffPinModel.role == role,
                )
            )
            pin_entry = row.scalar_one_or_none()

            if pin_entry:
                # Verify current PIN
                if pin_entry.pin != current_pin:
                    return {"ok": False, "error": "Current PIN is incorrect"}
                pin_entry.pin = new_pin
            else:
                # Default PIN check (first time)
                default_pins = {
                    "Reception": "1234", "ECG": "1234", "Echo": "1234",
                    "TMT": "1234", "Doctor": "5678", "Manager": "9999",
                    "Dietitian": "1234", "Dietician": "1234",
                }
                default = default_pins.get(role, "1234")
                if current_pin != default:
                    return {"ok": False, "error": "Current PIN is incorrect"}
                # Create new entry
                pin_entry = StaffPinModel(
                    clinic_id=clinic_id,
                    role=role,
                    pin=new_pin,
                )
                session.add(pin_entry)

            await session.commit()
            logger.info("PIN changed for clinic=%s role=%s", clinic_id, role)
            return {"ok": True, "message": "PIN changed successfully!"}

    except Exception as e:
        logger.error("PIN change error: %s", e)
        return {"ok": False, "error": str(e)}
