"""End-to-end tests for the interconnection pipeline (Lego Block 3-4):

1. Reception registers a patient → queue entries get the REAL department (TMT etc.)
2. Patient tracking link returns live status JSON
3. Technician "call" action → patient WhatsApp link auto-generated

Run:  python tests/test_interconnection.py
"""

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_TEST_DB = str(ROOT / "test_interconn.db")

# ── Fresh DB per run (previous runs left locked/stale files) ──
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


def _phone() -> str:
    return f"9{_RUN:05d}0000"


def test_register_creates_real_department_entries():
    with TestClient(main_v2.app) as client:
        token = create_session(role="Reception", name="Test Reception", user_id="tester")
        client.cookies.set("gc_session", token)

        r = client.post("/staff/api/register", json={
            "name": "Ramesh Kumar",
            "phone": _phone(),
            "age": 45,
            "gender": "Male",
            "services": ["TMT", "ECG"],
            "complaints": "chest pain on walking",
        })
        data = r.json()
        assert data.get("ok") is True, data
        assert len(data["entries"]) == 2
        assert data["tracking_url"].startswith("http")

        # Verify the DB rows carry the REAL department (not "Cardiology")
        with main_v2.engine.connect() as conn:
            from sqlalchemy import text
            rows = conn.execute(text(
                "SELECT service_code, department FROM queue_entries WHERE patient_name='Ramesh Kumar'"
            )).fetchall()
        dept_map = {r[0]: r[1] for r in rows}
        assert dept_map.get("TMT") == "TMT", dept_map
        assert dept_map.get("ECG") == "ECG", dept_map


def test_tracking_status_endpoint_live():
    with TestClient(main_v2.app) as client:
        token = create_session(role="Reception", name="Test Reception", user_id="tester")
        client.cookies.set("gc_session", token)
        reg = client.post("/staff/api/register", json={
            "name": "Sita Devi",
            "phone": str(int(_phone()) + 1),
            "age": 50,
            "gender": "Female",
            "services": ["Echo"],
            "complaints": "breathlessness",
        }).json()
        assert reg.get("ok") is True, reg

        token_part = reg["tracking_url"].rsplit("/", 1)[-1]
        r = client.get(f"/track/{token_part}/status")
        data = r.json()
        assert data.get("ok") is True
        assert data["patient_name"] == "Sita Devi"
        assert any(e["service_code"].upper() == "ECHO" for e in data["entries"])


def test_call_action_generates_whatsapp_url():
    with TestClient(main_v2.app) as client:
        token = create_session(role="Reception", name="Test Reception", user_id="tester")
        client.cookies.set("gc_session", token)
        reg = client.post("/staff/api/register", json={
            "name": "Mohan Lal",
            "phone": str(int(_phone()) + 2),
            "age": 60,
            "gender": "Male",
            "services": ["TMT"],
            "complaints": "",
        }).json()
        assert reg.get("ok") is True, reg
        patient_id = reg["patient_id"]

        with main_v2.engine.connect() as conn:
            from sqlalchemy import text
            entry_id = conn.execute(text(
                "SELECT id FROM queue_entries WHERE patient_id = :pid AND service_code='TMT'"
            ), {"pid": patient_id}).scalar()
        assert entry_id

        r = client.post("/api/v1/queue/action", json={
            "entry_id": str(entry_id),
            "action": "call",
            "updated_by": "Test Tech",
        })
        data = r.json()
        assert data.get("action") == "call", data
        # wa.me link must be present so the technician's browser notifies the patient
        assert data.get("whatsapp_url", "").startswith("https://wa.me/"), data


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
