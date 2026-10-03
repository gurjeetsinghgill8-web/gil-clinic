"""Brick 4 — role-based route enforcement (the matrix as security).

Run:  python -m pytest tests/test_role_guard.py -q

Hiding a link is not protection. A receptionist can type /staff/lab in the
address bar. These tests pin that the route actually refuses, and that the
oversight roles (admin/ceo/owner) are never locked out.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_TEST_DB = ROOT / "test_role_guard.db"
if _TEST_DB.exists():
    try:
        _TEST_DB.unlink()
    except Exception:
        pass

os.environ["GHOS_DB_URL"] = f"sqlite:///{_TEST_DB}"
os.environ["SYSTEM_AI_FALLBACK_ENABLED"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import main_v2  # noqa: E402
from src.domain.auth import nav  # noqa: E402

main_v2.Base.metadata.create_all(bind=main_v2.engine)
main_v2._migrate_sqlite_columns()


# ══════════════════════════════════════════════════════════════════════════
# 1. The pure guard
# ══════════════════════════════════════════════════════════════════════════


class TestCanAccess:
    def test_a_receptionist_cannot_open_other_departments(self):
        assert nav.can_access_staff_route("Reception", "reception") is True
        assert nav.can_access_staff_route("Reception", "lab") is False
        assert nav.can_access_staff_route("Reception", "ecg") is False
        assert nav.can_access_staff_route("Reception", "opd") is False

    def test_a_lab_tech_can_only_open_lab(self):
        assert nav.can_access_staff_route("Lab", "lab") is True
        assert nav.can_access_staff_route("Lab", "reception") is False
        assert nav.can_access_staff_route("Lab", "xray") is False

    def test_a_doctor_can_see_shared_rooms_but_not_departments(self):
        assert nav.can_access_staff_route("Doctor", "patient_status") is True
        assert nav.can_access_staff_route("Doctor", "live_board") is True
        assert nav.can_access_staff_route("Doctor", "lab") is False
        assert nav.can_access_staff_route("Doctor", "reception") is False

    def test_oversight_roles_bypass_everything(self):
        for role in ("super_admin", "ceo", "owner"):
            for key in ("lab", "ecg", "reception", "billing", "settings", "anything"):
                assert nav.can_access_staff_route(role, key) is True, (role, key)

    def test_a_manager_can_oversee_but_not_enter_a_department(self):
        assert nav.can_access_staff_route("Manager", "reception") is True
        assert nav.can_access_staff_route("Manager", "live_board") is True
        assert nav.can_access_staff_route("Manager", "lab") is False

    def test_an_unknown_role_is_least_privilege(self):
        assert nav.can_access_staff_route("GOD", "reception") is False


class TestNoDeadModules:
    """/staff/billing and /staff/tv are disabled stubs (redirect home), so the
    nav must not advertise them."""

    def test_billing_and_tv_are_not_in_the_catalog(self):
        keys = {m.key for m in nav.MODULES}
        assert "billing" not in keys
        assert "tv" not in keys

    def test_no_role_is_offered_a_dead_module(self):
        for role in nav.ROLE_MODULES:
            modules = set(nav.module_keys(role))
            assert "billing" not in modules, role
            assert "tv" not in modules, role


# ══════════════════════════════════════════════════════════════════════════
# 2. The route actually refuses (not just hides the link)
# ══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def client():
    return TestClient(main_v2.app, follow_redirects=False)


def _staff_session(role: str) -> None:
    from src.presentation.staff.routes import staff_routes

    token = staff_routes.create_session(role=role, name=role)
    return token


class TestRouteRefusal:
    def test_a_receptionist_is_bounced_off_lab(self, client):
        token = _staff_session("Reception")
        client.cookies.set("gc_session", token)
        response = client.get("/staff/lab")
        assert response.status_code == 302
        assert response.headers["location"] == "/home"

    def test_a_receptionist_is_bounced_off_ecg(self, client):
        client.cookies.set("gc_session", _staff_session("Reception"))
        response = client.get("/staff/ecg")
        assert response.status_code == 302
        assert response.headers["location"] == "/home"

    def test_a_receptionist_is_bounced_off_the_doctor_cockpit_route(self, client):
        client.cookies.set("gc_session", _staff_session("Reception"))
        response = client.get("/staff/opd")
        assert response.status_code == 302
        assert response.headers["location"] == "/home"

    def test_a_lab_tech_is_bounced_off_reception(self, client):
        client.cookies.set("gc_session", _staff_session("Lab"))
        response = client.get("/staff/reception")
        assert response.status_code == 302
        assert response.headers["location"] == "/home"

    def test_a_manager_is_allowed_into_reception(self, client):
        client.cookies.set("gc_session", _staff_session("Manager"))
        response = client.get("/staff/reception")
        # Not the guard's bounce: either a real page (200) or another redirect,
        # but never the /home denial.
        assert not (response.status_code == 302 and response.headers.get("location") == "/home")

    def test_home_is_open_to_every_role(self, client):
        for role in ("Reception", "Lab", "Manager", "Doctor"):
            client.cookies.set("gc_session", _staff_session(role))
            response = client.get("/staff/home")
            assert response.status_code == 200, role


class TestOpdIsolationFromStaff:
    """A staff session must NEVER grant OPD (prescription) access.

    Regression for the security blunder where the OPD session reader borrowed a
    staff session and mapped ANY staff role to a doctor — a receptionist could
    open the prescription pad. OPD access comes only from an ``opd_session``.
    """

    def test_a_receptionist_cannot_open_the_opd_cockpit(self, client):
        client.cookies.set("gc_session", _staff_session("Reception"))
        response = client.get("/opd/dashboard")
        assert response.status_code == 302
        assert "opd/login" in response.headers.get("location", "")

    def test_a_receptionist_cannot_read_opd_apis(self, client):
        client.cookies.set("gc_session", _staff_session("Reception"))
        for path in ("/opd/api/settings", "/opd/api/queue-ewt", "/opd/api/referrals", "/opd/api/leads"):
            response = client.get(path)
            assert response.status_code == 302, path
            assert "opd/login" in response.headers.get("location", ""), path

    def test_a_lab_tech_cannot_open_the_opd_cockpit(self, client):
        client.cookies.set("gc_session", _staff_session("Lab"))
        response = client.get("/opd/dashboard")
        assert response.status_code == 302

    def test_the_doctor_view_route_is_guarded(self, client):
        client.cookies.set("gc_session", _staff_session("Reception"))
        response = client.get("/staff/doctor")
        assert response.status_code == 302
        assert response.headers.get("location") == "/home"


class TestLoginClearsOtherSessions:
    """Logging in as one role must clear the OTHER session cookies, so a person
    cannot stack a low-privilege session on a still-valid high-privilege one."""

    def test_staff_login_clears_an_existing_opd_session(self, client):
        from src.presentation.opd.routes import opd_routes

        doctor_token = opd_routes._create_opd_session(
            role="junior", doctor_id="clinic_default", name="Dr"
        )
        client.cookies.set("opd_session", doctor_token)

        response = client.post(
            "/signin", data={"pin": "1234", "role": "reception"}, follow_redirects=False
        )

        set_cookies = response.headers.get_list("set-cookie")
        joined = "; ".join(set_cookies)
        # The old doctor cookie is cleared AND the reception staff cookie is set.
        assert "opd_session" in joined
        assert "gc_session" in joined
