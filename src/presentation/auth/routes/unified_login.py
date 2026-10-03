"""Unified PIN login — one door for OPD + staff roles (Brick 2a).

Additive by design: the existing ``/opd/login``, ``/staff/login``,
``/clinic-portal`` and ``/admin/login`` all keep working exactly as before. This
adds ONE new door (``/signin``) that a person can use instead:

    PIN "5554"  → exactly one match (Chief Doctor) → straight to /opd/dashboard
    PIN "1234"  → many matches (junior + reception + ecg + …) → "choose your role"
    PIN "???"   → licensed doctor PIN → /opd/dashboard

Routing reuses each system's own session creator, so the dashboard the person
lands on accepts the cookie with no changes to that dashboard.

Super-admin and clinic (username + password) remain on their own logins for now
— those use a different credential shape and are the next sub-brick.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import jinja2
import sqlalchemy as sa
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src.domain.auth.identity import (
    SYSTEM_OPD,
    SYSTEM_STAFF,
    RoleMatch,
    resolve_pin,
    route_for,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Auth"])

_TEMPLATES_DIR = Path(__file__).parents[4] / "templates"

#: Where a staff role lands. Dietician gets its own screen; everyone else goes
#: home first (the sidebar then takes them anywhere their role allows).
STAFF_HOME = "/staff/home"


def _render(name: str, **context: Any) -> str:
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)), auto_reload=True
    )
    return env.get_template(name).render(**context)


@router.get("/signin", include_in_schema=False)
async def signin_page(request: Request):
    """The one login page. No state — always shows the PIN form."""
    return HTMLResponse(_render("unified_login.html"))


def _opd_response(match: RoleMatch) -> RedirectResponse:
    """Build the OPD cookie + redirect for a doctor-side role."""
    from src.presentation.opd.routes import opd_routes

    doctor_id = "admin" if match.key == "opd_admin" else "clinic_default"
    token = opd_routes._create_opd_session(
        role=match.key, doctor_id=doctor_id, name=match.name
    )
    resp = RedirectResponse(match.dashboard, status_code=303)
    resp.set_cookie(
        opd_routes.SESSION_COOKIE,
        token,
        max_age=opd_routes.SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return resp


def _staff_response(match: RoleMatch) -> RedirectResponse:
    """Build the staff cookie + redirect for a department role."""
    from src.presentation.staff.routes import staff_routes

    token = staff_routes.create_session(role=match.name, name=match.name)
    resp = RedirectResponse(match.dashboard, status_code=303)
    resp.set_cookie(
        staff_routes.SESSION_COOKIE,
        token,
        max_age=staff_routes.SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=True,
    )
    return resp


async def _resolve_with_licensed(pin: str) -> list[RoleMatch]:
    """Built-in + staff roles, then the licensed-doctor table as a fallback.

    The licensed lookup mirrors ``opd_login_submit`` so a clinic that issued its
    own doctor PINs can also use the single door.
    """
    matches = resolve_pin(pin)
    if matches:
        return matches

    try:
        from src.infrastructure.opd.models.opd_models import LicenseModel
        from src.shared.infrastructure.database import async_session_factory

        async with async_session_factory() as session:
            row = await session.execute(
                sa.select(LicenseModel).where(
                    LicenseModel.pin == pin, LicenseModel.is_active == 1
                )
            )
            lic = row.scalar_one_or_none()
        if lic is not None:
            return [
                RoleMatch(
                    key="licensed",
                    system=SYSTEM_OPD,
                    name=lic.doctor_name or "Licensed Doctor",
                    dashboard="/opd/dashboard",
                )
            ]
    except Exception as exc:  # pragma: no cover - best-effort
        logger.warning("licensed PIN lookup failed: %s", exc)

    return []


@router.post("/signin", include_in_schema=False)
async def signin_submit(
    request: Request,
    pin: str = Form(""),
    role: str = Form(""),
):
    """Handle one PIN.

    * no match         → error back to the form
    * exactly one match → set that system's cookie and redirect
    * several matches   → render the role picker (the PIN alone cannot decide)
    """
    pin = (pin or "").strip()
    chosen_role = (role or "").strip()

    matches = await _resolve_with_licensed(pin)

    if not matches:
        return HTMLResponse(
            _render("unified_login.html", error="❌ PIN match nahi hua. Dobara try karein."),
            status_code=401,
        )

    # Second hop: the person picked a role from the ambiguity list.
    if chosen_role:
        match = next((m for m in matches if m.key == chosen_role), None)
        if match is None:
            return HTMLResponse(
                _render("unified_login.html", error="❌ Wo role is PIN se match nahi karta."),
                status_code=400,
            )
        return _route(match)

    if len(matches) == 1:
        return _route(matches[0])

    # Ambiguous: let the person choose. Show the SAME pin hidden so they do not
    # have to retype it.
    return HTMLResponse(
        _render(
            "unified_login.html",
            pin=pin,
            choices=[
                {"key": m.key, "name": m.name, "dashboard": m.dashboard}
                for m in matches
            ],
        ),
        status_code=200,
    )


def _route(match: RoleMatch) -> RedirectResponse:
    if match.system == SYSTEM_OPD:
        return _opd_response(match)
    return _staff_response(match)


@router.get("/signin/check", include_in_schema=False)
async def signin_check(pin: str = ""):
    """Which roles does this PIN open? (read-only, for the tools page + tests).

    Does NOT log anyone in and does NOT reveal dashboard internals — it answers
    the question a confused user has: "is my PIN a doctor, reception, or lab?"
    """
    matches = await _resolve_with_licensed(pin)
    return {
        "ok": True,
        "pin": pin or "",
        "count": len(matches),
        "roles": [
            {"key": m.key, "name": m.name, "dashboard": m.dashboard} for m in matches
        ],
        "ambiguous": len(matches) > 1,
    }
