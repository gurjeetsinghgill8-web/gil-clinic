"""Credential verification for admin + clinic (Brick 2b).

Why this is a shared module
---------------------------
The old ``/admin/login`` and ``/clinic/login`` verify credentials inline. The
unified ``/signin`` door needs the SAME checks, and duplicating them would let
the two drift — the classic failure is a lockout that one login path honours and
the other silently bypasses. These functions are the single verification any
login surface should call.

They take an open SQLAlchemy session and return ``(model, "")`` on success or
``(None, error_message)`` on failure. The caller owns the commit, so the old
logins and the new door stay in control of their own transaction.

Note: the admin lockout constants are duplicated here from
``auth_routes.py`` (MAX_LOGIN_ATTEMPTS=5, LOCKOUT_MINUTES=15) on purpose — this
module is the source of truth going forward, and ``auth_routes.py`` will be
pointed at it in a later brick.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, timezone
from typing import Any

import bcrypt
import sqlalchemy as sa

from src.infrastructure.clinic.models.clinic_model import ClinicModel
from src.infrastructure.identity.models.admin_user_model import AdminUserModel
from src.infrastructure.staff.models.staff_user_model import StaffUserModel

#: After this many wrong passwords an admin account locks for a cool-down.
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 15

_INVALID = "Username ya password galat hai."


async def verify_admin(
    session: Any, username: str, password: str
) -> tuple[AdminUserModel | None, str]:
    """Verify a super-admin / ceo. Applies the same lockout the old login does.

    A locked account is refused here exactly as it is at ``/admin/login``, so a
    unified door cannot become the back way past a lockout.
    """
    username = (username or "").strip()
    password = (password or "").strip()
    if not username or not password:
        return None, "Username aur password chahiye."

    row = await session.execute(
        sa.select(AdminUserModel).where(
            AdminUserModel.username == username,
            AdminUserModel.is_active == True,  # noqa: E712
        )
    )
    admin = row.scalar_one_or_none()
    if admin is None:
        return None, _INVALID

    now = datetime.now(timezone.utc)
    locked_until = admin.locked_until
    if locked_until is not None and getattr(locked_until, "tzinfo", None) is None:
        # SQLite returns naive datetimes even for DateTime(timezone=True);
        # comparing naive to aware raises TypeError on a hot login path.
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    if locked_until and locked_until > now:
        remaining = int((locked_until - now).total_seconds() // 60)
        return None, f"Account {remaining} min ke liye lock hai — thodi der baad koshish karein."

    if not bcrypt.checkpw(password.encode("utf-8"), admin.password_hash.encode("utf-8")):
        admin.login_attempts = int(admin.login_attempts or 0) + 1
        if admin.login_attempts >= MAX_LOGIN_ATTEMPTS:
            admin.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
            admin.login_attempts = 0
            return None, f"Bahut galat koshish — account {LOCKOUT_MINUTES} min ke liye lock ho gaya."
        return None, _INVALID

    admin.login_attempts = 0
    admin.locked_until = None
    admin.last_login = now
    return admin, ""


async def verify_clinic(
    session: Any, username: str, password: str
) -> tuple[ClinicModel | None, str]:
    """Verify a clinic by its ``clinic_username`` + password.

    Mirrors the essential checks of ``clinic_login``: row exists, license is
    still active, and the bcrypt password matches (with the "1234" fallback for
    clinics that never set a password).
    """
    username = (username or "").strip()
    password = (password or "").strip()
    if not username or not password:
        return None, "Username aur password chahiye."

    row = await session.execute(
        sa.select(ClinicModel).where(
            ClinicModel.clinic_username == username,
            ClinicModel.is_active == True,  # noqa: E712
        )
    )
    clinic = row.scalar_one_or_none()
    if clinic is None:
        return None, _INVALID

    # License must be active — and an expiry date in the past flips it inactive,
    # exactly as the old login does, so an expired clinic cannot use this door.
    if clinic.is_license_active:
        try:
            expiry = date.fromisoformat(str(clinic.license_expiry_date)[:10])
            if expiry < date.today():
                clinic.is_license_active = False
        except (ValueError, TypeError):
            pass  # malformed date → do not hard-block, let is_license_active decide
    if not clinic.is_license_active:
        return None, "License expire ho gaya — admin se renewal karayein."

    if clinic.clinic_password_hash:
        if not bcrypt.checkpw(password.encode("utf-8"), clinic.clinic_password_hash.encode("utf-8")):
            return None, _INVALID
    elif password != "1234":
        return None, _INVALID

    return clinic, ""


async def verify_staff_phone(
    session: Any, phone: str, password: str
) -> tuple[StaffUserModel | None, str]:
    """Verify a staff user by phone + password (receptionists, some doctors).

    The old staff ``phone-login`` hashes the password with SHA-256 (not bcrypt,
    unlike admin/clinic). This mirrors that exact check so a staff member can use
    the unified door with the same credential they already have.
    """
    phone = (phone or "").strip()
    password = (password or "").strip()
    if not phone or not password:
        return None, "Phone aur password chahiye."

    row = await session.execute(
        sa.select(StaffUserModel).where(
            StaffUserModel.phone == phone,
            StaffUserModel.is_active == True,  # noqa: E712
        )
    )
    user = row.scalar_one_or_none()
    if user is None or not user.password_hash:
        return None, _INVALID

    if hashlib.sha256(password.encode("utf-8")).hexdigest() != user.password_hash:
        return None, _INVALID

    return user, ""
