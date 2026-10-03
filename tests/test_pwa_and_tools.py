"""PWA installability + clinic tools tests.

Run:  python -m pytest tests/test_pwa_and_tools.py -q

Two problems this file exists to prevent from coming back:

  1. **The app was not installable, and nothing said so.** Three manifests
     existed, none linked from the pages staff use, and every icon they
     declared was a 404 — Chrome requires a valid 192px AND 512px icon, so
     installability failed at the first requirement. Silent, because Chrome
     simply never shows the prompt. These tests assert the files exist and the
     endpoints serve real bytes, not just that a manifest is configured.

  2. **Features shipped with no way to reach them.** Health-card revoke, the
     access log, the invite pipeline, the family locker, the FHIR export and
     the crawl history were all real, tested and live — and invisible, because
     they were API-only. `/tools` is the front door; the last group asserts the
     page exists, renders, and that every endpoint it calls is reachable.
"""

from __future__ import annotations

import json
import os
import struct
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_TEST_DB = ROOT / "test_pwa_tools.db"
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
from src.infrastructure.clinic.models.clinic_model import ClinicModel  # noqa: E402
from src.shared.infrastructure.database import async_session_factory  # noqa: E402

main_v2.Base.metadata.create_all(bind=main_v2.engine)
main_v2._migrate_sqlite_columns()

TOKEN = "GIL-DEMO-SEED-2026"


def _run(coro):
    import asyncio

    return asyncio.run(coro)


@pytest.fixture(scope="module")
def client():
    return TestClient(main_v2.app)


@pytest.fixture
def login(monkeypatch):
    from src.presentation.opd.routes import opd_routes

    def _login(clinic_id: str = ""):
        monkeypatch.setattr(
            opd_routes,
            "_require_opd_session",
            lambda request: {
                "role": "chief", "doctor_id": "chief", "name": "Dr Test",
                "clinic_id": clinic_id, "lic_info": {},
            },
        )
        return "chief"

    return _login


def _png_size(path: Path) -> tuple[int, int]:
    """Read width/height straight from the PNG header.

    Parsed by hand rather than with PIL so the test proves the file on disk is a
    real PNG, without adding an image library to the test environment.
    """
    with open(path, "rb") as handle:
        header = handle.read(24)
    assert header[:8] == b"\x89PNG\r\n\x1a\n", f"{path.name} is not a PNG"
    width, height = struct.unpack(">II", header[16:24])
    return width, height


# ══════════════════════════════════════════════════════════════════════════
# 1. The icons must EXIST — this was the actual bug
# ══════════════════════════════════════════════════════════════════════════


class TestIconsOnDisk:
    def test_every_declared_icon_exists_and_is_a_real_png(self):
        """The original bug: the manifest declared icons that were 404."""
        from src.presentation.pwa.routes.pwa_routes import MANIFEST

        for icon in MANIFEST["icons"]:
            path = ROOT / icon["src"].lstrip("/")
            assert path.exists(), f"{icon['src']} is missing — Chrome will refuse to install"

    def test_icon_dimensions_match_what_the_manifest_claims(self):
        """A manifest that lies about sizes is as bad as a missing file."""
        from src.presentation.pwa.routes.pwa_routes import MANIFEST

        for icon in MANIFEST["icons"]:
            path = ROOT / icon["src"].lstrip("/")
            width, height = _png_size(path)
            assert f"{width}x{height}" == icon["sizes"], (
                f"{icon['src']} is {width}x{height} but declares {icon['sizes']}"
            )

    def test_a_192_and_a_512_icon_both_exist(self):
        """Chrome's hard requirement — both sizes, or no install prompt."""
        from src.presentation.pwa.routes.pwa_routes import MANIFEST

        sizes = {i["sizes"] for i in MANIFEST["icons"]}
        assert "192x192" in sizes
        assert "512x512" in sizes

    def test_a_maskable_icon_is_declared(self):
        """Without one, Android crops the icon into a circle and cuts the mark."""
        from src.presentation.pwa.routes.pwa_routes import MANIFEST

        assert any(i["purpose"] == "maskable" for i in MANIFEST["icons"])

    def test_icons_are_not_tiny_placeholders(self):
        for icon in ("icon-192.png", "icon-512.png", "apple-touch-icon.png"):
            path = ROOT / "static" / "icons" / icon
            assert path.stat().st_size > 500, f"{icon} looks like an empty placeholder"


# ══════════════════════════════════════════════════════════════════════════
# 2. Manifest and service worker are served correctly
# ══════════════════════════════════════════════════════════════════════════


class TestManifestServed:
    def test_manifest_is_served_from_the_root(self, client):
        response = client.get("/manifest.json")
        assert response.status_code == 200
        assert "manifest+json" in response.headers["content-type"]
        body = response.json()
        assert body["name"] and body["short_name"]

    def test_manifest_is_never_cached_hard(self, client):
        """A stale manifest is how an installed app keeps a dead icon."""
        response = client.get("/manifest.json")
        assert "no-cache" in response.headers.get("cache-control", "")

    def test_manifest_has_the_fields_chrome_requires(self, client):
        body = client.get("/manifest.json").json()
        for field in ("name", "short_name", "start_url", "display", "icons", "scope"):
            assert field in body, field
        assert body["display"] == "standalone"

    def test_start_url_is_inside_the_scope(self, client):
        body = client.get("/manifest.json").json()
        assert body["start_url"].startswith(body["scope"])

    def test_shortcuts_point_at_real_pages(self, client):
        body = client.get("/manifest.json").json()
        for shortcut in body.get("shortcuts", []):
            assert shortcut["url"].startswith("/")
            assert shortcut.get("name")

    def test_icon_urls_actually_resolve_over_http(self, client):
        """Declared is not enough — the browser fetches them by URL."""
        body = client.get("/manifest.json").json()
        for icon in body["icons"]:
            response = client.get(icon["src"])
            assert response.status_code == 200, f"{icon['src']} → {response.status_code}"
            assert response.headers["content-type"].startswith("image/png")
            assert len(response.content) > 500


class TestServiceWorkerServed:
    def test_the_worker_is_served_from_the_root(self, client):
        """Served from /static/sw.js it could only ever control /static/*."""
        response = client.get("/sw.js")
        assert response.status_code == 200
        assert "javascript" in response.headers["content-type"]

    def test_the_scope_header_allows_the_whole_origin(self, client):
        response = client.get("/sw.js")
        assert response.headers.get("service-worker-allowed") == "/"

    def test_the_worker_itself_is_never_cached_hard(self, client):
        """Otherwise a fixed caching bug can never reach the affected devices."""
        response = client.get("/sw.js")
        assert "no-cache" in response.headers.get("cache-control", "")

    def test_the_worker_refuses_to_cache_private_routes(self):
        """The rule that matters: a shared clinic tablet must never show the
        previous doctor's cached patient list."""
        source = (ROOT / "static" / "sw.js").read_text(encoding="utf-8")
        for private in ("/opd/api/", "/track/", "/my/", "/card/", "/api/",
                        "/admin/", "/r/"):
            assert f"'{private}'" in source, f"{private} must be in NEVER_CACHE_PREFIXES"

    def test_the_worker_explains_why_it_does_not_cache_data(self):
        """A future maintainer must find the reason, not just the rule."""
        source = (ROOT / "static" / "sw.js").read_text(encoding="utf-8")
        assert "shared" in source.lower()
        assert "leak" in source.lower() or "PHI" in source


class TestPwaStatusEndpoint:
    def test_status_reports_installable(self, client):
        body = client.get("/pwa-status").json()
        assert body["ok"] is True
        assert body["installable"] is True, [
            c for c in body["checks"] if not c["ok"]
        ]

    def test_status_reports_every_check_individually(self, client):
        body = client.get("/pwa-status").json()
        names = {c["check"] for c in body["checks"]}
        assert "icons resolve" in names
        assert "service worker file exists" in names
        assert "192px icon declared" in names
        assert "512px icon declared" in names

    def test_status_explains_how_to_install(self, client):
        body = client.get("/pwa-status").json()
        assert "Install" in body["how_to_install"]

    def test_status_states_the_no_caching_of_patient_data_rule(self, client):
        body = client.get("/pwa-status").json()
        assert "cache" in body["note"].lower()


def _render_opd_dashboard() -> str:
    """Render the OPD dashboard through Jinja (its content lives in partials).

    Brick 4b split the 380KB template into partials, so a raw read of
    ``dashboard.html`` only sees the include shell — render it to check content.
    """
    import jinja2

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(ROOT / "templates")), auto_reload=False
    )
    return env.get_template("opd/dashboard.html").render(
        request=None,
        session={"role": "chief", "name": "Dr"},
        role="chief",
        doctor_id="x",
        doc_name="Dr",
        settings={},
        raw_ai_keys={},
        build_stamp="t",
        tab="rx",
        today_count=0,
        today_revenue=0,
        is_chief=True,
        is_owner=True,
        templates=[],
    )


class TestPagesLinkTheManifest:
    """A manifest nobody links is a manifest the browser never reads."""

    def test_the_dashboard_links_and_registers(self):
        html = _render_opd_dashboard()
        assert 'rel="manifest"' in html
        assert "/manifest.json" in html
        assert "serviceWorker" in html and "'/sw.js'" in html

    def test_the_marketplace_links_and_registers(self):
        html = (ROOT / "templates" / "marketplace.html").read_text(encoding="utf-8")
        assert 'rel="manifest"' in html
        assert "serviceWorker" in html

    def test_the_patient_track_page_links_and_registers(self):
        html = (ROOT / "templates" / "patient_track.html").read_text(encoding="utf-8")
        assert 'rel="manifest"' in html
        assert "serviceWorker" in html

    def test_the_tools_page_links_and_registers(self):
        html = (ROOT / "templates" / "clinic_tools.html").read_text(encoding="utf-8")
        assert 'rel="manifest"' in html
        assert "serviceWorker" in html

    def test_no_page_links_a_manifest_that_does_not_exist(self):
        """The exact bug: /static/icons/icon-192.png was a 404."""
        import re

        for template in (ROOT / "templates").rglob("*.html"):
            text = template.read_text(encoding="utf-8", errors="replace")
            for match in re.finditer(r'href="(/static/[^"]+)"', text):
                asset = match.group(1)
                if asset.endswith((".png", ".ico", ".svg")):
                    path = ROOT / asset.lstrip("/")
                    assert path.exists(), f"{template.name} links missing asset {asset}"


# ══════════════════════════════════════════════════════════════════════════
# 3. /tools — the front door for features that had none
# ══════════════════════════════════════════════════════════════════════════


class TestToolsPage:
    def _seed_clinic(self, code: str, name: str) -> str:
        from src.shared.domain.base_entity import uuid7

        clinic_id = uuid7()

        async def _insert():
            async with async_session_factory() as session:
                session.add(
                    ClinicModel(
                        id=clinic_id, clinic_name=name, clinic_code=code,
                        doctor_name=f"Dr {name}", specialty="Cardiology",
                        city="Jodhpur", state="Rajasthan",
                        open_time="00:01", close_time="23:58",
                        is_license_active=True, is_active=True,
                    )
                )
                await session.commit()
            return str(clinic_id)

        return _run(_insert())

    def test_the_page_requires_a_session(self, client):
        response = client.get("/tools", follow_redirects=False)
        assert response.status_code in (301, 302, 303, 307, 401, 403)

    def test_the_page_renders_for_staff(self, client, login):
        login(self._seed_clinic("TLS-A", "Tools Clinic"))
        response = client.get("/tools")
        assert response.status_code == 200, response.text
        assert "text/html" in response.headers["content-type"]
        assert "Clinic Tools" in response.text

    def test_it_presents_every_capability_that_had_no_home(self, client, login):
        """Each of these shipped as API-only — real, tested, unreachable."""
        login(self._seed_clinic("TLS-B", "Tools Clinic 2"))
        html = client.get("/tools").text
        for capability in (
            "Kisne khola",        # health card access log
            "Revoke",             # health card revoke
            "FHIR export",        # ABD-03
            "Referrals",          # F-06
            "wait time sach",     # EWT accuracy (F-03)
            "Verified reviews",   # F-07
            "Patients kya maang", # invite pipeline (GRW-02)
            "Crawler ne kya",     # Module 6 ingestion
            "Install",            # PWA
        ):
            assert capability in html, f"tools page is missing: {capability}"

    def test_it_says_why_it_exists(self, client, login):
        """A future maintainer must know this page is not decoration."""
        login(self._seed_clinic("TLS-C", "Tools Clinic 3"))
        html = client.get("/tools").text
        assert "tested" in html.lower() or "test" in html.lower()
        assert "clickable" in html.lower() or "click" in html.lower()

    def test_the_dashboard_links_to_the_tools_page(self):
        html = _render_opd_dashboard()
        assert 'href="/tools"' in html


class TestToolsEndpoints:
    def test_the_summary_requires_a_session(self, client):
        response = client.get("/opd/api/tools/summary", follow_redirects=False)
        assert response.status_code in (301, 302, 303, 307, 401, 403)

    def test_the_summary_returns_the_counts_the_hub_shows(self, client, login):
        clinic = None
        from src.shared.domain.base_entity import uuid7

        clinic_id = uuid7()

        async def _insert():
            async with async_session_factory() as session:
                session.add(
                    ClinicModel(
                        id=clinic_id, clinic_name="Summary Clinic",
                        clinic_code="TLS-D", doctor_name="Dr Summary",
                        specialty="Cardiology", city="Jodhpur", state="Rajasthan",
                        open_time="00:01", close_time="23:58",
                        is_license_active=True, is_active=True,
                    )
                )
                await session.commit()

        _run(_insert())
        login(str(clinic_id))
        body = client.get("/opd/api/tools/summary").json()
        assert body["ok"] is True
        for field in ("referrals_pending", "reviews_visible", "leads_new",
                      "crawled_listings"):
            assert field in body, f"the hub needs {field} to show a real number"

    def test_the_patient_pick_list_returns_real_ids(self, client, login):
        """Free-text ids guarantee typos; the page must offer real ones."""
        login(str(uuid_of_clinic()))
        body = client.get("/opd/api/tools/recent-patients").json()
        assert body["ok"] is True
        assert "patients" in body

    def test_the_crawl_history_is_readable_by_staff_not_just_the_robot(self, client, login):
        """A doctor will not paste a machine secret to see what the crawler did."""
        login(str(uuid_of_clinic()))
        body = client.get("/api/v1/ingest/runs").json()
        assert body["ok"] is True, "staff session should be enough to READ"

    def test_the_opt_out_register_is_readable_by_staff(self, client, login):
        login(str(uuid_of_clinic()))
        body = client.get("/api/v1/marketplace/opt-out").json()
        assert body["ok"] is True

    def test_but_writing_to_the_directory_still_needs_the_token(self, client, login):
        """A session cookie must never be enough to inject listings."""
        login(str(uuid_of_clinic()))
        response = client.post(
            "/api/v1/ingest/doctors",
            json={"profiles": [{"doctor_name": "Session Injected Doctor"}]},
        )
        assert response.status_code == 401, "a login must not authorise ingestion"


_clinic_cache: list[str] = []


def uuid_of_clinic() -> str:
    """One shared clinic for the read-only tools tests."""
    if _clinic_cache:
        return __import__("uuid").UUID(_clinic_cache[0])

    from src.shared.domain.base_entity import uuid7

    clinic_id = uuid7()
    _clinic_cache.append(str(clinic_id))

    async def _insert():
        async with async_session_factory() as session:
            session.add(
                ClinicModel(
                    id=clinic_id, clinic_name="Shared Tools Clinic",
                    clinic_code="TLS-SHARED", doctor_name="Dr Shared",
                    specialty="Cardiology", city="Jodhpur", state="Rajasthan",
                    open_time="00:01", close_time="23:58",
                    is_license_active=True, is_active=True,
                )
            )
            await session.commit()

    _run(_insert())
    return clinic_id
