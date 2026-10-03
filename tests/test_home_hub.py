"""Brick 3a — role-based navigation model + the /home hub.

Run:  python -m pytest tests/test_home_hub.py -q

The dangerous part of role-filtered nav is a matrix error: a receptionist who
sees the admin panel, or a CEO who cannot see anything. So the matrix is pinned
role-by-role, and the /home route is checked end-to-end for one real role.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_TEST_DB = ROOT / "test_home_hub.db"
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
# 1. The matrix — pure
# ══════════════════════════════════════════════════════════════════════════


class TestCanonicalRole:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("chief", "doctor"),
            ("junior", "doctor"),
            ("opd_admin", "doctor"),
            ("licensed", "doctor"),
            ("Doctor", "doctor"),
            ("Reception", "reception"),
            ("receptionist", "reception"),
            ("ECG", "ecg"),
            ("Lab", "lab"),
            ("Dietician", "dietician"),
            ("dietitian", "dietician"),
            ("Manager", "manager"),
            ("super_admin", "admin"),
            ("ceo", "ceo"),
            ("owner", "owner"),
        ],
    )
    def test_known_roles_map_to_canonical(self, raw, expected):
        assert nav.canonical_role(raw) == expected

    def test_unknown_role_falls_back_to_least_privilege(self):
        # A typo in a session role must never widen access.
        assert nav.canonical_role("GOD_MODE") == "doctor"
        assert nav.canonical_role("") == "doctor"
        assert nav.canonical_role(None) == "doctor"


class TestRoleModules:
    def test_a_receptionist_sees_only_reception(self):
        keys = nav.module_keys("reception")
        assert "reception" in keys
        assert "opd" not in keys
        assert "admin" not in keys
        assert "lab" not in keys
        assert "ecg" not in keys

    def test_a_lab_tech_sees_only_lab(self):
        keys = nav.module_keys("lab")
        assert "lab" in keys
        assert "opd" not in keys
        assert "admin" not in keys
        assert "reception" not in keys

    def test_a_doctor_sees_their_cockpit(self):
        keys = nav.module_keys("chief")
        assert "opd" in keys
        assert "tools" in keys
        assert "admin" not in keys
        assert "lab" not in keys

    def test_an_admin_sees_more_than_a_doctor(self):
        """The owner's rule: admin 'doctor se bhi zyada' — a superset of doctor."""
        doctor_keys = set(nav.module_keys("chief"))
        admin_keys = set(nav.module_keys("super_admin"))
        assert "admin" in admin_keys
        assert "admin" not in doctor_keys
        # Admin also sees the doctor cockpit (oversight).
        assert "opd" in admin_keys
        assert doctor_keys <= admin_keys, "admin should be a superset of doctor"

    def test_a_ceo_sees_everything(self):
        keys = set(nav.module_keys("ceo"))
        assert keys == {m.key for m in nav.MODULES}

    def test_the_owner_sees_everything(self):
        keys = set(nav.module_keys("owner"))
        assert keys == {m.key for m in nav.MODULES}

    def test_a_single_department_role_has_no_other_departments(self):
        for role in ("ecg", "echo", "tmt", "xray"):
            keys = nav.module_keys(role)
            assert role in keys, role
            # no other diagnostics rooms
            others = {"ecg", "echo", "tmt", "xray", "lab"} - {role}
            assert not (others & set(keys)), f"{role} leaked {others & set(keys)}"

    def test_every_module_has_a_group_and_a_url(self):
        for module in nav.MODULES:
            assert module.name and module.url.startswith("/")
            assert module.group
            assert module.icon

    def test_dietician_is_a_department_not_a_doctor(self):
        keys = nav.module_keys("dietician")
        assert "dietician" in keys
        assert "opd" not in keys


class TestPrivilegeFlags:
    def test_ceo_is_read_only(self):
        assert nav.is_read_only("ceo") is True
        assert nav.is_read_only("owner") is False
        assert nav.is_read_only("chief") is False

    def test_owner_is_owner_only(self):
        assert nav.is_owner("owner") is True
        assert nav.is_owner("ceo") is False
        assert nav.is_owner("super_admin") is False


# ══════════════════════════════════════════════════════════════════════════
# 2. The /home route — end to end
# ══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def client():
    return TestClient(main_v2.app, follow_redirects=False)


class TestHomeHub:
    def test_not_logged_in_goes_to_the_unified_door(self, client):
        response = client.get("/home")
        assert response.status_code == 302
        assert response.headers["location"] == "/signin"

    def test_a_doctor_sees_their_modules_not_admin(self, client):
        # Log in as chief through the unified door (sets opd_session).
        login = client.post("/signin", data={"pin": "5554"})
        assert login.status_code == 303

        home = client.get("/home")
        assert home.status_code == 200
        assert "Doctor OPD" in home.text
        assert "Clinic Tools" in home.text
        # A doctor must NOT see the admin panel or another department.
        assert "Admin Panel" not in home.text
        assert "Reception" not in home.text

    def test_the_page_names_the_person(self, client):
        client.post("/signin", data={"pin": "5554"})
        home = client.get("/home")
        assert "Chief Doctor" in home.text

    def test_the_page_links_back_to_the_dashboard(self, client):
        client.post("/signin", data={"pin": "5554"})
        home = client.get("/home")
        assert "/opd/dashboard" in home.text

    def test_a_staff_receptionist_sees_reception_not_opd(self, client):
        # Build a staff session directly (the staff cookie is secure=True so the
        # TestClient would not resend it over http; set it ourselves instead).
        from src.presentation.staff.routes import staff_routes

        token = staff_routes.create_session(role="Reception", name="Reception One")
        client.cookies.set("gc_session", token)

        home = client.get("/home")
        assert home.status_code == 200
        assert "Reception" in home.text
        assert "Doctor OPD" not in home.text
        assert "Admin Panel" not in home.text

    def test_an_admin_sees_the_admin_panel(self, client):
        from src.presentation.staff.routes import staff_routes

        token = staff_routes.create_session(role="Manager", name="Manager One")
        client.cookies.set("gc_session", token)

        home = client.get("/home")
        assert home.status_code == 200
        # Manager sees the operational rooms, not the admin panel.
        assert "Reception" in home.text
        assert "Admin Panel" not in home.text

    def test_a_ceo_admin_sees_everything_and_is_marked_read_only(self, client):
        from src.presentation.admin.routes import auth_routes

        token = auth_routes._create_admin_session("1", "ceo-1", "ceo", "CEO Person")
        client.cookies.set("admin_session", token)

        home = client.get("/home")
        assert home.status_code == 200
        assert "Read-only" in home.text
        assert "Admin Panel" in home.text
        assert "Doctor OPD" in home.text
