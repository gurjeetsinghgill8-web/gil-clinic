"""Friendly URL tests — mistyped dashboard links must not look like a dead site.

Run:  python -m pytest tests/test_friendly_urls.py -q

Context: a doctor on a second laptop opened `/opd/Dashboard` (capital D) and the
app answered with the raw JSON ``{"detail":"Not Found"}``, which reads as "the
site is down". These tests pin the fix AND pin that nothing else changed:

  * aliases redirect to the right page
  * a human 404 shows a helpful HTML page (never raw JSON)
  * API 404s stay JSON (clients must not receive a web page)
  * the session guard's 302, /health and the real pages are untouched
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_TEST_DB = ROOT / "test_friendly_urls.db"
if _TEST_DB.exists():
    try:
        _TEST_DB.unlink()
    except Exception:
        pass

os.environ["GHOS_DB_URL"] = f"sqlite:///{_TEST_DB}"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import main_v2  # noqa: E402

main_v2.Base.metadata.create_all(bind=main_v2.engine)

client = TestClient(main_v2.app)


def _get(path: str):
    """GET without following redirects, so the redirect itself is assertable."""
    return client.get(path, follow_redirects=False)


# ══════════════════════════════════════════════════════════════════════════
# 1. Mistyped dashboard links land on the login page
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "path",
    [
        "/dashboard",
        "/Dashboard",
        "/opd/Dashboard",           # the exact URL from the support report
        "/opd/dashbord",            # typo
        "/opd/dashboad",            # typo
        "/opddashboard",            # missing slash
        "/opd/dashboard.html",
        "/doctor",
        "/doctor-dashboard",
        "/doctorlogin",
        "/opd/doctor",
    ],
)
def test_mistyped_dashboard_redirects_to_login(path):
    response = _get(path)
    assert response.status_code in (302, 307), f"{path} -> HTTP {response.status_code}"
    assert response.headers.get("location", "").endswith("/opd/login")


@pytest.mark.parametrize(
    "path", ["/finddoctor", "/find_doctor", "/find-a-doctor"]
)
def test_mistyped_find_a_doctor_redirects(path):
    response = _get(path)
    assert response.status_code in (302, 307)
    assert response.headers.get("location", "").endswith("/find-doctor")


# ══════════════════════════════════════════════════════════════════════════
# 2. An unknown page is helpful, never raw JSON
# ══════════════════════════════════════════════════════════════════════════


def test_unknown_page_shows_a_helpful_html_page():
    response = _get("/kuch-bhi-nahi-hai-yahan")
    assert response.status_code == 404
    body = response.text
    assert "text/html" in response.headers.get("content-type", "")
    assert "Ye page nahi mila" in body
    assert "/opd/login" in body          # a way forward, not a dead end
    assert "/find-doctor" in body
    assert "<!DOCTYPE html>" in body
    assert '{"detail"' not in body       # the old, confusing answer


def test_helpful_page_escapes_the_requested_path():
    response = _get("/%3Cscript%3Ealert(1)%3C/script%3E")
    assert response.status_code == 404
    assert "<script>alert(1)</script>" not in response.text
    assert "&lt;script&gt;" in response.text


# ══════════════════════════════════════════════════════════════════════════
# 3. APIs must keep receiving JSON
# ══════════════════════════════════════════════════════════════════════════


def test_api_404_still_returns_json():
    response = _get("/api/v1/aisa-kuch-nahi-hai")
    assert response.status_code == 404
    assert "application/json" in response.headers.get("content-type", "")
    assert response.json() == {"detail": "Not Found"}


def test_api_404_with_html_accept_header_still_returns_json():
    response = client.get(
        "/api/v1/marketplace/aisa-nahi-hai",
        follow_redirects=False,
        headers={"accept": "*/*"},
    )
    assert response.status_code == 404
    assert "application/json" in response.headers.get("content-type", "")


# ══════════════════════════════════════════════════════════════════════════
# 4. Nothing that already worked changed
# ══════════════════════════════════════════════════════════════════════════


def test_the_real_routes_still_work():
    assert _get("/health").status_code == 200
    assert _get("/").status_code == 200
    assert _get("/opd/login").status_code == 200
    assert _get("/find-doctor").status_code == 200


def test_the_correct_dashboard_url_still_bounces_to_login():
    """Correct URL + no session → the session guard's redirect, not a 404 page."""
    response = _get("/opd/dashboard")
    assert response.status_code == 302
    assert response.headers.get("location", "").endswith("/opd/login")


def test_session_guarded_api_keeps_its_302():
    """The queue-engine guard uses HTTPException(302) — it must survive the handler."""
    for path in ("/opd/api/chamber/status", "/opd/api/queue-ewt"):
        response = _get(path)
        assert response.status_code == 302, f"{path} -> {response.status_code}"
        assert response.headers.get("location", "").endswith("/opd/login")


def test_openapi_schema_still_builds():
    """A bad handler signature would blow up the schema — cheap smoke test."""
    schema = main_v2.app.openapi()
    assert "/api/v1/marketplace/doctors" in schema["paths"]
    # aliases are internal plumbing, they must not pollute the public schema
    assert "/dashboard" not in schema["paths"]
    assert "/opd/Dashboard" not in schema["paths"]


# ══════════════════════════════════════════════════════════════════════════
# 5. The alias table itself
# ══════════════════════════════════════════════════════════════════════════


def test_aliases_never_shadow_a_real_route():
    """Every alias must be a path that does not exist in the app already."""
    from src.presentation.common.routes.friendly_routes import ALIASES

    real = set()
    for route in main_v2.app.routes:
        path = getattr(route, "path", None)
        if path:
            real.add(path)
    clashes = sorted(set(ALIASES) & real)
    assert not clashes, f"aliases shadow real routes: {clashes}"
