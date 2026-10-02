"""Tests for Live Board (B5) + re-enabled department pages (B3).

Run:  python tests/test_live_board.py
"""

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_TEST_DB = str(ROOT / "test_liveboard.db")
for _p in (Path(_TEST_DB),):
    try:
        if _p.exists():
            _p.unlink()
    except Exception:
        pass

os.environ["GHOS_DB_URL"] = f"sqlite:///{_TEST_DB}"
os.environ["SYSTEM_AI_FALLBACK_ENABLED"] = "false"

from fastapi.testclient import TestClient  # noqa: E402

import main_v2  # noqa: E402
from src.presentation.staff.routes.staff_routes import create_session  # noqa: E402

_RUN = int(time.time()) % 100000


def _client(role: str = "Reception") -> TestClient:
    client = TestClient(main_v2.app)
    token = create_session(role=role, name="Test " + role, user_id="tester")
    client.cookies.set("gc_session", token)
    return client


def test_department_pages_are_enabled():
    """TMT/ECG/Echo pages must render (200), NOT redirect to /staff/home."""
    with _client() as client:
        for path in ("/staff/ecg", "/staff/echo", "/staff/tmt", "/staff/xray", "/staff/lab"):
            r = client.get(path, follow_redirects=False)
            assert r.status_code == 200, f"{path} -> {r.status_code} (expected 200)"
            assert "queue" in r.text.lower() or "patient" in r.text.lower()


def test_live_board_page_and_json():
    with _client() as client:
        # Register patients across departments
        client.post("/staff/api/register", json={
            "name": "LiveBoard One", "phone": f"9{_RUN:05d}0001",
            "age": 40, "gender": "Male", "services": ["TMT", "ECG"], "complaints": "",
        })
        client.post("/staff/api/register", json={
            "name": "LiveBoard Two", "phone": f"9{_RUN:05d}0002",
            "age": 35, "gender": "Female", "services": ["Echo"], "complaints": "",
        })

        # JSON API
        r = client.get("/staff/api/live-board")
        data = r.json()
        assert data.get("ok") is True, data
        assert data["total_waiting"] >= 3
        by_id = {d["id"]: d for d in data["departments"]}
        assert by_id["TMT"]["waiting"] >= 1
        assert by_id["ECG"]["waiting"] >= 1
        assert by_id["Echo"]["waiting"] >= 1

        # HTML page
        r = client.get("/staff/live-board")
        assert r.status_code == 200
        assert "data-waiting-total" in r.text
        assert "TMT" in r.text


def test_department_queue_filter_shows_only_its_service():
    with _client() as client:
        client.post("/staff/api/register", json={
            "name": "DeptFilter Test", "phone": f"9{_RUN:05d}0003",
            "age": 30, "gender": "Male", "services": ["TMT"], "complaints": "",
        })
        r = client.get("/staff/api/live-board")
        data = r.json()
        by_id = {d["id"]: d for d in data["departments"]}
        # TMT has the patient; Dietitian must NOT show him
        assert by_id["TMT"]["waiting"] >= 1
        assert "DeptFilter Test" in str(by_id["TMT"]["top"])
        assert "DeptFilter Test" not in str(by_id["Dietitian"]["top"])


if __name__ == "__main__":
    import traceback

    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except Exception as e:
            failed += 1
            print(f"FAIL  {t.__name__}: {e}")
            traceback.print_exc()
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
