"""Brick 2b — username/password on the unified door (admin + clinic).

Run:  python -m pytest tests/test_unified_password.py -q

These pin the two things that can go wrong with a shared credential check:

  1. The unified door must set the SAME cookie the old logins set, so the
     dashboard it lands on accepts it unchanged.
  2. A lockout or an expired licence must be refused here exactly as it is at
     the old login — the single door must never become the back way past them.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_TEST_DB = ROOT / "test_unified_password.db"
if _TEST_DB.exists():
    try:
        _TEST_DB.unlink()
    except Exception:
        pass

os.environ["GHOS_DB_URL"] = f"sqlite:///{_TEST_DB}"
os.environ["SYSTEM_AI_FALLBACK_ENABLED"] = "false"

import bcrypt  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import main_v2  # noqa: E402
from src.infrastructure.clinic.models.clinic_model import ClinicModel  # noqa: E402
from src.infrastructure.identity.models.admin_user_model import AdminUserModel  # noqa: E402
from src.shared.infrastructure.database import async_session_factory  # noqa: E402

main_v2.Base.metadata.create_all(bind=main_v2.engine)
main_v2._migrate_sqlite_columns()

PASSWORD = "secret123"


def _hash(value: str) -> str:
    return bcrypt.hashpw(value.encode("utf-8"), bcrypt.gensalt(rounds=4)).decode("utf-8")


def _run(coro):
    import asyncio

    return asyncio.run(coro)


def _make_admin(username: str, role: str = "super_admin", password: str = PASSWORD) -> None:
    async def _insert():
        async with async_session_factory() as session:
            session.add(
                AdminUserModel(
                    username=username,
                    password_hash=_hash(password),
                    role=role,
                    display_name=username.title(),
                    is_active=True,
                    login_attempts=0,
                )
            )
            await session.commit()

    _run(_insert())


def _make_clinic(username: str, *, license_active: bool = True, password: str = PASSWORD) -> str:
    from src.shared.domain.base_entity import uuid7

    clinic_id = uuid7()

    async def _insert():
        async with async_session_factory() as session:
            session.add(
                ClinicModel(
                    id=clinic_id,
                    clinic_name=f"{username} Clinic",
                    clinic_code=f"CL-{username[:8].upper()}",
                    doctor_name=f"Dr {username}",
                    specialty="Cardiology",
                    city="Jodhpur",
                    state="Rajasthan",
                    clinic_username=username,
                    clinic_password_hash=_hash(password),
                    is_license_active=license_active,
                    is_active=True,
                    license_expiry_date="2030-01-01",
                )
            )
            await session.commit()
        return str(clinic_id)

    return _run(_insert())


@pytest.fixture
def client():
    return TestClient(main_v2.app, follow_redirects=False)


# ══════════════════════════════════════════════════════════════════════════
# 1. The shared verifiers
# ══════════════════════════════════════════════════════════════════════════


class TestVerifyAdmin:
    def test_correct_credentials_succeed(self):
        from src.application.auth.credentials import verify_admin

        _make_admin("ceo-ok")
        async def _check():
            async with async_session_factory() as session:
                admin, err = await verify_admin(session, "ceo-ok", PASSWORD)
                return admin is not None, err
        ok, err = _run(_check())
        assert ok, err

    def test_wrong_password_fails(self):
        from src.application.auth.credentials import verify_admin

        _make_admin("ceo-bad")
        async def _check():
            async with async_session_factory() as session:
                admin, err = await verify_admin(session, "ceo-bad", "wrong")
                return admin, err
        admin, err = _run(_check())
        assert admin is None
        assert "galat" in err

    def test_lockout_after_five_failures(self):
        from src.application.auth.credentials import verify_admin

        _make_admin("ceo-lock")
        async def _check():
            async with async_session_factory() as session:
                err = ""
                for _ in range(5):
                    _, err = await verify_admin(session, "ceo-lock", "wrong")
                # Sixth attempt, even with the RIGHT password, is refused.
                admin, lock_err = await verify_admin(session, "ceo-lock", PASSWORD)
                return admin, lock_err
        admin, err = _run(_check())
        assert admin is None
        assert "lock" in err


class TestVerifyClinic:
    def test_correct_credentials_succeed(self):
        from src.application.auth.credentials import verify_clinic

        _make_clinic("clinic-ok")
        async def _check():
            async with async_session_factory() as session:
                clinic, err = await verify_clinic(session, "clinic-ok", PASSWORD)
                return clinic is not None, err
        ok, err = _run(_check())
        assert ok, err

    def test_expired_license_is_refused(self):
        from src.application.auth.credentials import verify_clinic

        _make_clinic("clinic-expired", license_active=False)
        async def _check():
            async with async_session_factory() as session:
                clinic, err = await verify_clinic(session, "clinic-expired", PASSWORD)
                return clinic, err
        clinic, err = _run(_check())
        assert clinic is None
        assert "License" in err


# ══════════════════════════════════════════════════════════════════════════
# 2. The unified door
# ══════════════════════════════════════════════════════════════════════════


class TestPasswordDoor:
    def test_admin_lands_on_admin_dashboard_with_admin_cookie(self, client):
        _make_admin("door-admin")
        response = client.post(
            "/signin/password", data={"username": "door-admin", "password": PASSWORD}
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/admin/dashboard"
        assert "admin_session" in response.headers.get("set-cookie", "")

    def test_clinic_lands_on_staff_home_with_gc_session(self, client):
        _make_clinic("door-clinic")
        response = client.post(
            "/signin/password", data={"username": "door-clinic", "password": PASSWORD}
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/staff/home"
        assert "gc_session" in response.headers.get("set-cookie", "")

    def test_the_clinic_cookie_carries_the_clinic_id(self, client):
        """Staff routes scope data by clinic_id — the unified door must set it
        just like the old clinic login does."""
        from src.presentation.staff.routes import staff_routes

        _make_clinic("door-scope")
        response = client.post(
            "/signin/password", data={"username": "door-scope", "password": PASSWORD}
        )
        cookie = response.headers.get("set-cookie", "")
        token = cookie.split("gc_session=", 1)[1].split(";", 1)[0]
        payload = staff_routes.read_session(token)
        assert payload is not None
        assert payload.get("clinic_id")

    def test_wrong_password_is_rejected(self, client):
        _make_admin("door-wrong")
        response = client.post(
            "/signin/password", data={"username": "door-wrong", "password": "nope"}
        )
        assert response.status_code == 401

    def test_unknown_username_is_rejected(self, client):
        response = client.post(
            "/signin/password", data={"username": "nobody", "password": "x"}
        )
        assert response.status_code == 401

    def test_blank_credentials_are_rejected(self, client):
        response = client.post("/signin/password", data={"username": "", "password": ""})
        assert response.status_code == 401

    def test_the_page_shows_the_username_tab(self, client):
        html = client.get("/signin").text
        assert "Username + Password" in html
        assert "signin/password" in html


# ══════════════════════════════════════════════════════════════════════════
# 3. Staff phone + password (the third credential shape on the same door)
# ══════════════════════════════════════════════════════════════════════════


def _make_staff(phone: str, name: str = "Reception One", role: str = "receptionist",
                password: str = "staffpass") -> None:
    import hashlib

    from src.infrastructure.staff.models.staff_user_model import StaffUserModel

    async def _insert():
        async with async_session_factory() as session:
            session.add(
                StaffUserModel(
                    name=name,
                    phone=phone,
                    password_hash=hashlib.sha256(password.encode("utf-8")).hexdigest(),
                    role=role,
                    assigned_opds="[]",
                    is_active=True,
                )
            )
            await session.commit()

    _run(_insert())


class TestStaffPhoneDoor:
    def test_a_staff_phone_logs_in_on_the_unified_door(self, client):
        _make_staff("9000000001")
        response = client.post(
            "/signin/password", data={"username": "9000000001", "password": "staffpass"}
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/staff/home"
        assert "gc_session" in response.headers.get("set-cookie", "")

    def test_a_wrong_staff_password_is_rejected(self, client):
        _make_staff("9000000002")
        response = client.post(
            "/signin/password", data={"username": "9000000002", "password": "wrong"}
        )
        assert response.status_code == 401

    def test_a_phone_that_is_not_registered_is_rejected(self, client):
        response = client.post(
            "/signin/password", data={"username": "9999999999", "password": "x"}
        )
        assert response.status_code == 401

    def test_username_and_phone_do_not_collide(self, client):
        """An admin username and a staff phone live in different namespaces — the
        door tries admin, then clinic, then staff phone, in that order."""
        _make_admin("root")
        _make_staff("root")  # same string, but as a staff PHONE
        response = client.post(
            "/signin/password", data={"username": "root", "password": PASSWORD}
        )
        # "root" as an admin username wins (higher privilege is checked first).
        assert response.status_code == 303
        assert response.headers["location"] == "/admin/dashboard"
        assert "admin_session" in response.headers.get("set-cookie", "")
