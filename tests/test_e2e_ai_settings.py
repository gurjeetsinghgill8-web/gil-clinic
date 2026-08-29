"""End-to-end functional test: app boot + SQLite migration + settings encryption
+ Puter handoff + usage metering. No real AI/network calls needed.

Run:  python tests/test_e2e_ai_settings.py
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Must be set BEFORE importing main_v2 (module-level engine binding)
_TEST_DB = str(ROOT / "test_ai_e2e.db")
os.environ["GHOS_DB_URL"] = f"sqlite:///{_TEST_DB}"
os.environ["SYSTEM_AI_FALLBACK_ENABLED"] = "false"

from fastapi.testclient import TestClient  # noqa: E402

import main_v2  # noqa: E402
from src.presentation.opd.routes.opd_routes import _create_opd_session  # noqa: E402


def _client() -> TestClient:
    client = TestClient(main_v2.app)
    token = _create_opd_session("chief", "clinic_default", "Chief Doctor")
    client.cookies.set("opd_session", token)
    return client


def test_health():
    with TestClient(main_v2.app) as client:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


def test_settings_encrypt_roundtrip_and_mask():
    with TestClient(main_v2.app) as client:
        token = _create_opd_session("chief", "clinic_default", "Chief Doctor")
        client.cookies.set("opd_session", token)

        # Save a key + puter mode OFF first (auto)
        r = client.post("/opd/api/settings", json={
            "clinic_name": "Test Clinic",
            "doc_name": "Dr Test",
            "ai_mode": "auto",
            "openai_api_key": "sk-e2e-test-key-123",
            "groq_api_key": "",
        })
        assert r.json().get("ok") is True

        # GET must NEVER leak the raw key
        r = client.get("/opd/api/settings")
        data = r.json()
        assert data["has_openai"] is True
        assert data["openai_api_key"] == "••••••••"
        assert "sk-e2e-test-key-123" not in str(data)

        # Raw DB value must be Fernet-encrypted
        with main_v2.engine.connect() as conn:
            from sqlalchemy import text
            raw = conn.execute(text(
                "SELECT openai_api_key FROM opd_settings WHERE doctor_id='clinic_default'"
            )).scalar()
        assert raw.startswith("enc:v1:")
        assert "sk-e2e-test-key-123" not in raw

        # Clearing a key works
        r = client.post("/opd/api/settings", json={"clear_openai": True, "ai_mode": "auto"})
        assert r.json().get("ok") is True
        r = client.get("/opd/api/settings")
        assert r.json()["has_openai"] is False


def test_ai_config_summary():
    with TestClient(main_v2.app) as client:
        token = _create_opd_session("chief", "clinic_default", "Chief Doctor")
        client.cookies.set("opd_session", token)
        r = client.get("/opd/api/ai-config")
        data = r.json()
        assert data["mode"] in ("auto", "puter", "off")
        assert data["puter_enabled"] is True
        assert "keys" in data


def test_generate_rx_puter_handoff_and_result():
    with TestClient(main_v2.app) as client:
        token = _create_opd_session("chief", "clinic_default", "Chief Doctor")
        client.cookies.set("opd_session", token)

        # Switch to puter mode
        assert client.post("/opd/api/settings", json={"ai_mode": "puter"}).json()["ok"]

        body = {
            "patient_name": "Test Patient",
            "vitals": "BP 120/80",
            "complaints": "cough fever",
            "allow_suggest_drugs": False,
        }
        # 1) No puter_result → server must hand off to browser Puter
        r = client.post("/opd/api/generate-rx", json=body)
        data = r.json()
        assert data.get("ok") is False
        assert data.get("code") == "PUTER_CHAT"
        assert "cough" in data["prompt"]

        # 2) Browser resolves via Puter → re-posts result
        body["puter_result"] = (
            "Diagnosis: 1. Acute Upper Respiratory Infection\n"
            "Treatment: 1. Tab. Paracetamol 500mg BD x 3 days\n"
            "Advice: Rest and fluids\n"
            "Follow-up: 3 days"
        )
        r = client.post("/opd/api/generate-rx", json=body)
        data = r.json()
        assert data.get("ok") is True
        assert "Paracetamol" in data["prescription"]
        assert data["provider"] == "puter"

        # Switch back to auto
        assert client.post("/opd/api/settings", json={"ai_mode": "auto"}).json()["ok"]


def test_usage_metering():
    with TestClient(main_v2.app) as client:
        token = _create_opd_session("chief", "clinic_default", "Chief Doctor")
        client.cookies.set("opd_session", token)

        r = client.post("/opd/api/ai-usage", json={"feature": "generate-rx", "provider": "puter", "success": True})
        assert r.json().get("ok") is True

        r = client.get("/opd/api/ai-usage")
        data = r.json()
        assert data["usage_today"] >= 1
        assert data["usage_this_month"] >= 1


def test_handwriting_ocr_puter_hops():
    with TestClient(main_v2.app) as client:
        token = _create_opd_session("chief", "clinic_default", "Chief Doctor")
        client.cookies.set("opd_session", token)
        client.post("/opd/api/settings", json={"ai_mode": "puter"})

        # Hop 1: server asks browser for OCR
        tiny_png = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
            "+A8AAQUBAScY42YAAAAASUVORK5CYII="
        )
        r = client.post("/opd/api/handwriting-ocr", json={"image": "data:image/png;base64," + tiny_png})
        data = r.json()
        assert data.get("code") == "PUTER_OCR"

        # Hop 2: browser sends structured JSON from puter chat structuring
        r = client.post("/opd/api/handwriting-ocr", json={
            "image": "data:image/png;base64," + tiny_png,
            "puter_result": '{"vitals":"BP 130/85","complaints":"headache","diagnosis":"Tension headache","medicines":"1. Tab. PCM 500mg SOS","investigations":"","advice":"rest","follow_up":"1 week"}',
        })
        data = r.json()
        assert data.get("ok") is True
        assert data.get("ocr_method") == "puter"
        assert data["parsed"].get("diagnosis") == "Tension headache"

        client.post("/opd/api/settings", json={"ai_mode": "auto"})


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
