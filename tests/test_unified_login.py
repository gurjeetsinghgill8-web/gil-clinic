"""Brick 2a — unified PIN login + identity resolver.

Run:  python -m pytest tests/test_unified_login.py -q

The dangerous part of a single login is NOT the page — it is the resolver. If a
PIN routes to the wrong dashboard, a receptionist lands on a doctor's cockpit and
the whole "one door" promise becomes a privacy incident. So the resolver is
pinned hard:

  * a PIN with exactly one meaning routes directly,
  * a PIN with several meanings must NEVER pick one silently — it lists them,
  * the resolver stays in sync with the PINs the old logins actually check,
  * the login sets the correct session cookie per system (opd vs staff).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_TEST_DB = ROOT / "test_unified_login.db"
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
from src.domain.auth import identity  # noqa: E402

main_v2.Base.metadata.create_all(bind=main_v2.engine)
main_v2._migrate_sqlite_columns()


# ══════════════════════════════════════════════════════════════════════════
# 1. The resolver — pure logic
# ══════════════════════════════════════════════════════════════════════════


class TestResolvePin:
    def test_chief_pin_resolves_to_exactly_one_role(self):
        matches = identity.resolve_pin(identity.OPD_CHIEF_PIN)
        assert len(matches) == 1, matches
        assert matches[0].key == "chief"
        assert matches[0].system == identity.SYSTEM_OPD
        assert matches[0].dashboard == "/opd/dashboard"

    def test_ambiguous_pin_returns_every_role_it_could_be(self):
        """1234 = junior doctor AND several staff roles. Never guess."""
        matches = identity.resolve_pin("1234")
        keys = {m.key for m in matches}
        assert "junior" in keys
        assert "reception" in keys
        assert "ecg" in keys
        # It must list them, not silently pick one.
        assert len(matches) > 1

    def test_a_unique_staff_pin_resolves_to_one_department(self):
        matches = identity.resolve_pin("5678")  # Doctor
        assert len(matches) == 1
        assert matches[0].key == "doctor"
        assert matches[0].system == identity.SYSTEM_STAFF
        assert matches[0].dashboard == "/staff/doctor"

    def test_manager_pin_lands_on_manager(self):
        matches = identity.resolve_pin("9999")
        assert len(matches) == 1
        assert matches[0].key == "manager"

    def test_empty_pin_matches_nothing(self):
        assert identity.resolve_pin("") == []
        assert identity.resolve_pin(None) == []

    def test_unknown_pin_matches_nothing(self):
        assert identity.resolve_pin("999999") == []

    def test_no_duplicate_roles(self):
        """Dietician must not appear twice even if STAFF_PINS lists it twice."""
        keys = [m.key for m in identity.resolve_pin("1234")]
        assert len(keys) == len(set(keys))

    def test_unique_dashboard_only_when_unambiguous(self):
        one = identity.resolve_pin("5554")
        assert identity.unique_dashboard(one) == "/opd/dashboard"
        many = identity.resolve_pin("1234")
        assert identity.unique_dashboard(many) is None


class TestResolverStaysInSyncWithOldLogins:
    """The unified door must never accept a PIN the old logins would reject,
    or route a PIN the old logins never meant."""

    def test_opd_pins_match_opd_routes(self):
        from src.presentation.opd.routes import opd_routes

        assert identity.OPD_CHIEF_PIN == opd_routes.CHIEF_PIN
        assert identity.OPD_JUNIOR_PIN == opd_routes.JUNIOR_PIN
        assert identity.OPD_ADMIN_PIN == opd_routes.ADMIN_PIN

    def test_staff_pins_match_staff_routes(self):
        from src.presentation.staff.routes import staff_routes

        assert identity.STAFF_PINS == staff_routes.STAFF_PINS, (
            "STAFF_PINS drifted between identity.py and staff_routes.py"
        )

    def test_default_pin_departments_match_the_staff_login_fallback(self):
        """Xray and Lab have no explicit STAFF_PINS entry; the old login grants
        them '1234' via ``STAFF_PINS.get(role) or '1234'``. The unified door must
        match that, not drop them."""
        assert identity.DEFAULT_PIN_DEPARTMENTS == {"Xray": "1234", "Lab": "1234"}
        # And both actually resolve from the default pin.
        keys = {m.key for m in identity.resolve_pin("1234")}
        assert "xray" in keys and "lab" in keys


# ══════════════════════════════════════════════════════════════════════════
# 2. The login route — routing + cookies
# ══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def client():
    # Function-scoped on purpose: the login tests SET cookies, and a shared
    # client would leak an opd_session/gc_session into the next test (which is
    # exactly how the "old logins still work" check produced a surprise 307).
    return TestClient(main_v2.app, follow_redirects=False)


class TestSigninRoute:
    def test_the_page_renders(self, client):
        response = client.get("/signin")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "PIN" in response.text

    def test_a_unique_pin_routes_directly_and_sets_the_opd_cookie(self, client):
        response = client.post("/signin", data={"pin": "5554"})
        assert response.status_code == 303
        assert response.headers["location"] == "/opd/dashboard"
        # It must set the OPD session cookie, not the staff one.
        assert "opd_session" in response.headers.get("set-cookie", "")

    def test_a_unique_staff_pin_sets_the_staff_cookie(self, client):
        response = client.post("/signin", data={"pin": "5678"})
        assert response.status_code == 303
        assert response.headers["location"] == "/staff/doctor"
        assert "gc_session" in response.headers.get("set-cookie", "")

    def test_an_ambiguous_pin_renders_the_role_picker_instead_of_guessing(self, client):
        response = client.post("/signin", data={"pin": "1234"})
        assert response.status_code == 200
        # The picker must be shown, not a silent redirect.
        assert "role chunein" in response.text or "role" in response.text
        # And it must list more than one option.
        assert response.text.count("choice-btn") > 1

    def test_picking_a_role_from_the_ambiguity_routes_correctly(self, client):
        response = client.post("/signin", data={"pin": "1234", "role": "reception"})
        assert response.status_code == 303
        assert response.headers["location"] == "/staff/reception"
        assert "gc_session" in response.headers.get("set-cookie", "")

    def test_picking_the_junior_doctor_role_routes_to_opd(self, client):
        response = client.post("/signin", data={"pin": "1234", "role": "junior"})
        assert response.status_code == 303
        assert response.headers["location"] == "/opd/dashboard"
        assert "opd_session" in response.headers.get("set-cookie", "")

    def test_a_wrong_role_for_the_pin_is_rejected(self, client):
        # "manager" is NOT a role that PIN 5554 opens.
        response = client.post("/signin", data={"pin": "5554", "role": "manager"})
        assert response.status_code == 400

    def test_an_unknown_pin_is_rejected(self, client):
        response = client.post("/signin", data={"pin": "000000"})
        assert response.status_code == 401
        assert "match nahi" in response.text

    def test_a_blank_pin_is_rejected(self, client):
        response = client.post("/signin", data={"pin": ""})
        assert response.status_code == 401

    def test_the_old_logins_still_work(self, client):
        """The unified door is additive — nothing else may break."""
        assert client.get("/opd/login").status_code == 200
        assert client.get("/staff/login").status_code == 200
        assert client.get("/clinic-portal", follow_redirects=False).status_code == 200
        assert client.get("/admin/login", follow_redirects=False).status_code == 200


class TestSigninCheck:
    def test_check_reports_ambiguity_without_logging_in(self, client):
        body = client.get("/signin/check", params={"pin": "1234"}).json()
        assert body["ok"] is True
        assert body["ambiguous"] is True
        assert body["count"] > 1
        roles = {r["key"] for r in body["roles"]}
        assert "junior" in roles and "reception" in roles

    def test_check_reports_a_single_role(self, client):
        body = client.get("/signin/check", params={"pin": "5554"}).json()
        assert body["ambiguous"] is False
        assert body["count"] == 1
        assert body["roles"][0]["key"] == "chief"


class TestLandingLinksTheUnifiedDoor:
    def test_the_landing_page_offers_the_single_login(self):
        html = (ROOT / "templates" / "landing.html").read_text(encoding="utf-8")
        assert 'href="/signin"' in html
        assert "Ek Login" in html
