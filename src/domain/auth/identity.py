"""Unified identity resolution — one PIN → every role it could be (Brick 2).

Why this file exists
--------------------
The app has four logins because each system keeps its own credential namespace:

    /opd/login   → built-in + licensed doctor PINs  → `opd_session`
    /staff/login → role PINs (STAFF_PINS)           → `gc_session`
    /clinic-portal → clinic username + password     → `gc_session`
    /admin/login → super-admin username + password  → `admin_session`

A single PIN can match MANY roles: `1234` is the junior doctor PIN *and* the
Reception/ECG/Echo/TMT/Dietician staff PIN. A unified login therefore cannot
guess which of those a person means — it must resolve the PIN to ALL matches and
then either route directly (exactly one match) or ask the person which role they
are signing in as.

This module is that resolution, kept PURE (no DB, no FastAPI) so it is the
testable "brain" the login page builds on.

Sync contract
-------------
It mirrors the PIN constants defined in ``opd_routes.py`` and ``staff_routes.py``
and reads the SAME env vars. ``tests/test_phase0.py`` (or a sibling test) asserts
the two stay in sync, so a PIN changed in one place cannot silently drift.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# ── Credentials (mirrored from the presentation modules; read the same env) ──

OPD_CHIEF_PIN = os.getenv("OPD_CHIEF_PIN", "5554")
OPD_JUNIOR_PIN = os.getenv("OPD_JUNIOR_PIN", "1234")
OPD_ADMIN_PIN = os.getenv("OPD_ADMIN_PIN", "1010")

#: role → PIN. An EXACT mirror of ``staff_routes.STAFF_PINS`` — same keys, same
#: env vars, same defaults — so the unified door never accepts a PIN the old
#: staff login would reject, nor misses one it would accept. A test pins this.
STAFF_PINS: dict[str, str] = {
    "Reception": os.getenv("PIN_RECEPTION") or "1234",
    "ECG": os.getenv("PIN_ECG") or "1234",
    "Echo": os.getenv("PIN_ECHO") or "1234",
    "TMT": os.getenv("PIN_TMT") or "1234",
    "Doctor": os.getenv("PIN_DOCTOR") or "5678",
    "Manager": os.getenv("PIN_MANAGER") or "9999",
    "Admin": os.getenv("PIN_ADMIN") or "0000",
    "Dietitian": os.getenv("PIN_DIETITIAN") or "1234",
    "Dietician": os.getenv("PIN_DIETITIAN") or "1234",
}

#: Department roles with no explicit entry in ``staff_routes.STAFF_PINS`` but
#: which the old login grants the DEFAULT pin anyway, via its fallback
#: ``STAFF_PINS.get(role) or "1234"``. Listed here so the unified door matches
#: that real behaviour instead of silently dropping Xray and Lab.
DEFAULT_PIN_DEPARTMENTS: dict[str, str] = {
    "Xray": "1234",
    "Lab": "1234",
}

# ── Canonical role → (system, dashboard, human label) ────────────────────────

#: The system that owns the session cookie for a given role.
SYSTEM_OPD = "opd"
SYSTEM_STAFF = "staff"

ROLE_TARGETS: dict[str, tuple[str, str, str]] = {
    # OPD doctor-side roles (built-in PINs) — all land on the Smart OPD cockpit.
    "chief": (SYSTEM_OPD, "/opd/dashboard", "Chief Doctor"),
    "junior": (SYSTEM_OPD, "/opd/dashboard", "Junior Doctor"),
    "opd_admin": (SYSTEM_OPD, "/opd/dashboard", "OPD Admin"),
    # Staff department roles — each lands on its own department screen.
    "reception": (SYSTEM_STAFF, "/staff/reception", "Reception"),
    "ecg": (SYSTEM_STAFF, "/staff/ecg", "ECG"),
    "echo": (SYSTEM_STAFF, "/staff/echo", "Echo"),
    "tmt": (SYSTEM_STAFF, "/staff/tmt", "TMT"),
    "xray": (SYSTEM_STAFF, "/staff/xray", "Xray"),
    "lab": (SYSTEM_STAFF, "/staff/lab", "Lab"),
    "doctor": (SYSTEM_STAFF, "/staff/doctor", "Doctor"),
    "dietician": (SYSTEM_STAFF, "/staff/dietician", "Dietician"),
    "manager": (SYSTEM_STAFF, "/staff/manager", "Manager"),
}


@dataclass(frozen=True)
class RoleMatch:
    """One role a PIN could belong to — everything the login needs to route."""

    key: str           # canonical key in ROLE_TARGETS ("chief", "reception", …)
    system: str        # SYSTEM_OPD | SYSTEM_STAFF
    name: str          # human label ("Chief Doctor", "Reception", …)
    dashboard: str     # where this role lands after login


def resolve_pin(pin: str) -> list[RoleMatch]:
    """Every role a PIN could belong to, deterministic order (OPD first).

    Order is deliberate: a doctor PIN is checked before the staff map, so the
    built-in `chief`/`junior`/`opd_admin` take precedence when the same digits
    collide — those are the higher-trust roles.
    """
    matches: list[RoleMatch] = []
    value = (pin or "").strip()
    if not value:
        return matches

    # ── OPD built-in PINs ──
    if value == OPD_CHIEF_PIN:
        matches.append(_match("chief"))
    if value == OPD_JUNIOR_PIN:
        matches.append(_match("junior"))
    if value == OPD_ADMIN_PIN:
        matches.append(_match("opd_admin"))

    # ── Staff role PINs (explicit map + default-pin departments) ──
    for role, role_pin in STAFF_PINS.items():
        if value == role_pin:
            matches.append(_match(_staff_key(role)))
    for role, role_pin in DEFAULT_PIN_DEPARTMENTS.items():
        if value == role_pin:
            matches.append(_match(_staff_key(role)))

    # Dedupe: a role may appear once only (e.g. Dietician and Dietitian).
    seen: set[str] = set()
    unique: list[RoleMatch] = []
    for match in matches:
        if match.key in seen:
            continue
        seen.add(match.key)
        unique.append(match)
    return unique


def _match(key: str) -> RoleMatch:
    system, dashboard, name = ROLE_TARGETS[key]
    return RoleMatch(key=key, system=system, name=name, dashboard=dashboard)


def _staff_key(role: str) -> str:
    """STAFF_PINS role label → canonical ROLE_TARGETS key."""
    lowered = role.strip().lower()
    if lowered in ("dietitian", "dietician"):
        return "dietician"
    return lowered


def unique_dashboard(matches: list[RoleMatch]) -> str | None:
    """The dashboard to route to, but only when there is exactly ONE match."""
    if len(matches) != 1:
        return None
    return matches[0].dashboard


def route_for(key: str) -> str | None:
    """Dashboard for a canonical role key, or None if unknown."""
    target = ROLE_TARGETS.get(key)
    return target[1] if target else None
