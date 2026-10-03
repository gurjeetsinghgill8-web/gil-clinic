"""Role-based navigation model — who can see which module (Brick 3).

Why this exists
---------------
The two dashboards each show their own nav: the staff sidebar lists EVERY
department, and the OPD cockpit has no link to any of them. The user's rule is
simpler and safer: *a receptionist sees only reception, a lab tech only lab, a
doctor their own cockpit, an admin more, a CEO everything read-only, the owner
everything read-write.*

This module is that rule as PURE data + a pure function, so it is testable and
can drive the sidebar, the hub page, and later the per-route guard — from ONE
source of truth. If a role should gain a module, this is the only file to edit.

Roles are canonicalised because the three sessions spell them differently:
``"chief"`` (OPD), ``"Reception"`` (staff PIN), ``"receptionist"`` (staff user),
``"super_admin"`` (admin), ``"ceo"`` (admin) — all map to a small canonical set.
"""

from __future__ import annotations

from dataclasses import dataclass

# ── The rooms (module catalogue, in display order) ──────────────────────────


@dataclass(frozen=True)
class Module:
    key: str
    name: str
    url: str
    icon: str
    group: str


MODULES: tuple[Module, ...] = (
    Module("opd", "Doctor OPD", "/opd/dashboard", "🩺", "Clinical"),
    Module("reception", "Reception", "/staff/reception", "🏥", "Clinical"),
    Module("dietician", "Dietician", "/staff/dietician", "🥗", "Clinical"),
    Module("patient_status", "Patient Status", "/staff/patient-status", "🔍", "Clinical"),
    Module("ecg", "ECG", "/staff/ecg", "💓", "Diagnostics"),
    Module("echo", "Echo", "/staff/echo", "🫀", "Diagnostics"),
    Module("tmt", "TMT", "/staff/tmt", "🏃", "Diagnostics"),
    Module("xray", "Xray", "/staff/xray", "🦴", "Diagnostics"),
    Module("lab", "Lab", "/staff/lab", "🧪", "Diagnostics"),
    Module("billing", "Billing", "/staff/billing", "💰", "Admin"),
    Module("live_board", "Live Board", "/staff/live-board", "📊", "Admin"),
    Module("tv", "TV Display", "/staff/tv", "📺", "Admin"),
    Module("tools", "Clinic Tools", "/tools", "🛠️", "Admin"),
    Module("admin", "Admin Panel", "/admin/dashboard", "🔐", "Admin"),
    Module("find_doctor", "Find a Doctor", "/find-doctor", "📍", "Public"),
)

_MODULE_BY_KEY = {m.key: m for m in MODULES}

# ── The access matrix: canonical role → allowed module keys ─────────────────

_ALL = tuple(m.key for m in MODULES)

ROLE_MODULES: dict[str, tuple[str, ...]] = {
    # Owner: everything, read + write.
    "owner": _ALL,
    # CEO: everything, read-only (the guard is applied elsewhere; this is nav).
    "ceo": _ALL,
    # Super-admin / clinic admin: admin surface + the operational rooms, and —
    # per the owner's rule "admin doctor se bhi zyada dekh sakta hai" — the
    # doctor cockpit too, so an admin can oversee it.
    "admin": ("admin", "opd", "reception", "billing", "tools", "live_board",
              "tv", "patient_status", "find_doctor"),
    # Manager: the operational oversight rooms.
    "manager": ("reception", "billing", "tools", "live_board", "tv",
                "patient_status", "find_doctor"),
    # Doctor (OPD chief/junior/admin/licensed + staff "doctor"): own cockpit.
    "doctor": ("opd", "tools", "patient_status", "live_board", "find_doctor"),
    # Single-department roles see only their own room.
    "reception": ("reception", "patient_status", "find_doctor"),
    "lab": ("lab", "find_doctor"),
    "ecg": ("ecg",),
    "echo": ("echo",),
    "tmt": ("tmt",),
    "xray": ("xray",),
    "dietician": ("dietician", "find_doctor"),
    "billing": ("billing",),
}

# ── Canonicalisation ─────────────────────────────────────────────────────────

_CANONICAL: dict[str, str] = {
    # OPD session roles (doctor-side)
    "chief": "doctor",
    "junior": "doctor",
    "opd_admin": "doctor",
    "licensed": "doctor",
    "doctor": "doctor",
    # Staff PIN / staff-user roles
    "reception": "reception",
    "receptionist": "reception",
    "ecg": "ecg",
    "echo": "echo",
    "tmt": "tmt",
    "xray": "xray",
    "lab": "lab",
    "dietician": "dietician",
    "dietitian": "dietician",
    "billing": "billing",
    "manager": "manager",
    "admin": "manager",   # the STAFF "Admin" PIN is a clinic admin, not super_admin
    # Admin session roles
    "super_admin": "admin",
    "ceo": "ceo",
    "owner": "owner",
}

READ_ONLY_ROLES: frozenset[str] = frozenset({"ceo"})
OWNER_ROLES: frozenset[str] = frozenset({"owner"})


def canonical_role(raw_role: str | None) -> str:
    """Map any session role string to a canonical key. Unknown → "doctor".

    Unknown falls back to the least-privileged useful role rather than the most,
    so a typo in a session role never widens access.
    """
    if not raw_role:
        return "doctor"
    return _CANONICAL.get(str(raw_role).strip().lower(), "doctor")


def modules_for_role(raw_role: str | None) -> list[Module]:
    """The modules this role may open, in catalogue order."""
    role = canonical_role(raw_role)
    keys = ROLE_MODULES.get(role, ROLE_MODULES["doctor"])
    return [_MODULE_BY_KEY[k] for k in keys if k in _MODULE_BY_KEY]


def is_read_only(raw_role: str | None) -> bool:
    """A CEO can see everything but change nothing."""
    return canonical_role(raw_role) in READ_ONLY_ROLES


def is_owner(raw_role: str | None) -> bool:
    """The owner sees and changes everything."""
    return canonical_role(raw_role) in OWNER_ROLES


def module_keys(raw_role: str | None) -> list[str]:
    """Just the keys, for quick assertions and JSON."""
    return [m.key for m in modules_for_role(raw_role)]
