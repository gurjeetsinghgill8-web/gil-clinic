"""Regression tests for Brick 1 — Phase 0 correctness fixes.

Run:  python -m pytest tests/test_phase0.py -q

These pin the small fixes that a blind live-probe found, so they can never come
back silently:

  1. `GET /api/v1/queue/notes/{entry_id}` used to 500 on a malformed id — the
     repository's `get_by_id` called `uuid.UUID` uncaught. A bad id is "not
     found", never a crash.
  2. `/docs` and `/redoc` are OFF by default (the OpenAPI schema lists every
     internal/staff endpoint) and only turn on with `ENABLE_DOCS=1`.
  3. `/staff/seed` and `/staff/seed-staff` are env-gated behind `ALLOW_SEED=1`,
     so they cannot run in production by accident.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_TEST_DB = ROOT / "test_phase0.db"
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
from src.infrastructure.persistence.queue.repositories.queue_repository import (  # noqa: E402
    SqlAlchemyQueueRepository,
)
from src.shared.infrastructure.database import async_session_factory  # noqa: E402

main_v2.Base.metadata.create_all(bind=main_v2.engine)
main_v2._migrate_sqlite_columns()


def _run(coro):
    import asyncio

    return asyncio.run(coro)


@pytest.fixture(scope="module")
def client():
    return TestClient(main_v2.app)


class TestQueueNotesMalformedId:
    """The P0 crash: GET /api/v1/queue/notes/{entry_id} → 500 on a bad id."""

    def test_the_repository_returns_none_for_a_malformed_id(self):
        async def _check():
            async with async_session_factory() as session:
                repo = SqlAlchemyQueueRepository(session)
                return await repo.get_by_id("not-a-uuid")

        assert _run(_check()) is None, "a bad id must be 'not found', not a ValueError"

    def test_the_repository_returns_none_for_a_numeric_id(self):
        async def _check():
            async with async_session_factory() as session:
                repo = SqlAlchemyQueueRepository(session)
                return await repo.get_by_id("0")

        assert _run(_check()) is None

    def test_the_repository_returns_none_for_none(self):
        async def _check():
            async with async_session_factory() as session:
                repo = SqlAlchemyQueueRepository(session)
                return await repo.get_by_id("")

        assert _run(_check()) is None

    def test_a_real_but_absent_uuid_is_also_none(self):
        async def _check():
            async with async_session_factory() as session:
                repo = SqlAlchemyQueueRepository(session)
                return await repo.get_by_id("00000000-0000-0000-0000-000000000000")

        assert _run(_check()) is None


class TestDocsDisabledByDefault:
    def test_docs_are_off_without_the_env_flag(self, client):
        # `client` was built with ENABLE_DOCS unset (the default).
        assert client.get("/docs", follow_redirects=False).status_code == 404
        assert client.get("/redoc", follow_redirects=False).status_code == 404

    def test_the_flag_is_not_set_in_this_environment(self):
        assert os.getenv("ENABLE_DOCS") != "1", (
            "this test asserts the DEFAULT; if you set ENABLE_DOCS=1 the test is no longer "
            "proving the default"
        )


class TestSeedEnvGate:
    def test_seed_routes_refuse_without_the_flag(self, client):
        # Without ALLOW_SEED, the seed routes bounce to login before any write.
        for path in ("/staff/seed", "/staff/seed-staff"):
            response = client.get(path, follow_redirects=False)
            assert response.status_code == 302, path
            assert "/staff/login" in response.headers.get("location", ""), path

    def test_the_flag_is_not_set_in_this_environment(self):
        assert os.getenv("ALLOW_SEED") != "1", (
            "this test asserts the DEFAULT; with ALLOW_SEED=1 the gate is open and the "
            "assertion no longer proves the default"
        )


class TestBranding:
    def test_the_landing_page_no_longer_calls_itself_cardioqueue(self):
        html = (ROOT / "templates" / "landing.html").read_text(encoding="utf-8")
        # The subtitle used to contradict the h1 right above it ("GIL CLINIC").
        assert "CardioQueue — Multi-Specialty" not in html
        assert "GIL CLINIC — Multi-Specialty" in html
