"""Tests for the multi-provider AI router (BYOK) + key encryption.

Runs under pytest OR standalone:  python tests/test_ai_router.py
"""

import os
import sys
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ai_engine.provider_router import (
    PROVIDERS,
    ai_config_summary,
    decrypt_key,
    encrypt_key,
    is_key_set,
    mask_value,
    puter_model_id,
    resolve_provider_keys,
    route_chat,
    sanitize_output,
    system_fallback_enabled,
)


# ── Encryption ────────────────────────────────────────────────────────────────

def test_encrypt_decrypt_roundtrip():
    key = "sk-test-1234567890"
    enc = encrypt_key(key)
    assert enc.startswith("enc:v1:")
    assert enc != key
    assert decrypt_key(enc) == key


def test_encrypt_empty_stays_empty():
    assert encrypt_key("") == ""
    assert encrypt_key("   ") == ""


def test_decrypt_legacy_plaintext_passthrough():
    assert decrypt_key("gsk_legacy_plain") == "gsk_legacy_plain"


def test_decrypt_garbage_returns_empty():
    assert decrypt_key("enc:v1:not-a-valid-token") == ""


def test_decrypt_rejects_mask_placeholders():
    for mask in ("••••••••", "********", "****", "(in secret.txt)"):
        assert decrypt_key(mask) == ""


def test_mask_and_is_key_set():
    assert is_key_set("") is False
    assert is_key_set(encrypt_key("abc123")) is True
    assert mask_value("") == ""
    assert mask_value(encrypt_key("abc123")) == "••••••••"


# ── Provider resolution ───────────────────────────────────────────────────────

def test_resolve_provider_keys_only_configured():
    settings = {"groq_api_key": encrypt_key("gsk_test"), "gemini_api_key": encrypt_key("AIza_test")}
    resolved = resolve_provider_keys(settings)
    ids = [p["id"] for p in resolved]
    assert ids == ["groq", "gemini"]  # CHAT_ORDER order
    assert all(p["key"] == "gsk_test" or p["key"] == "AIza_test" for p in resolved)


def test_resolve_ignores_mask_and_empty():
    settings = {"groq_api_key": "••••••••", "openai_api_key": ""}
    assert resolve_provider_keys(settings) == []


def test_ai_config_summary_no_secrets():
    settings = {"groq_api_key": encrypt_key("gsk_secret"), "ai_mode": "auto", "ai_model": ""}
    summary = ai_config_summary(settings)
    assert summary["keys"]["groq"] is True
    assert summary["keys"]["openai"] is False
    assert "gsk_secret" not in str(summary)
    assert summary["mode"] == "auto"
    assert summary["puter_enabled"] is True


def test_puter_model_id_override_and_default():
    assert puter_model_id({}) == "gpt-4o-mini"
    assert puter_model_id({"ai_model": "gemini-2.0-flash"}) == "gemini-2.0-flash"


# ── Routing behaviour ─────────────────────────────────────────────────────────

def test_route_chat_off_mode():
    res = route_chat({"ai_mode": "off"}, ["hello"], feature="test")
    assert res["text"] == ""
    assert "turned off" in res["error"]


def test_route_chat_puter_mode_returns_handoff():
    res = route_chat({"ai_mode": "puter", "ai_model": ""}, ["system prompt", "user question"], feature="test")
    assert res.get("puter_needed") is True
    assert res["code"] == "PUTER_CHAT"
    assert "system prompt" in res["prompt"]
    assert res["model"] == "gpt-4o-mini"


def test_route_chat_no_keys_system_fallback_disabled():
    with mock.patch.dict(os.environ, {"SYSTEM_AI_FALLBACK_ENABLED": "false"}):
        assert system_fallback_enabled() is False
        res = route_chat({}, ["hello"], feature="test")
    assert res["text"] == ""
    assert res["provider"] == ""
    assert "No AI provider configured" in res["error"]


def test_route_chat_uses_clinic_key_first():
    """The clinic's own Groq key must be used — not any system key."""
    captured = {}

    def fake_compat(p, model, messages, temp, max_tokens):
        captured["key"] = p["key"]
        captured["provider"] = p["id"]
        return "AI RESPONSE", {"prompt_tokens": 10, "completion_tokens": 20}, ""

    import src.ai_engine.provider_router as pr

    with mock.patch.object(pr, "_call_openai_compat", fake_compat), \
         mock.patch.dict(os.environ, {"SYSTEM_AI_FALLBACK_ENABLED": "false"}):
        clinic_key = encrypt_key("gsk_clinic_own_key")
        res = route_chat({"groq_api_key": clinic_key}, ["hello"], feature="test")

    assert res["text"] == "AI RESPONSE"
    assert res["provider"] == "groq"
    assert captured["key"] == "gsk_clinic_own_key"
    assert res["usage"]["prompt_tokens"] == 10


def test_route_chat_provider_failover():
    """If Groq fails with 401, the router must try the next clinic provider."""
    calls = []

    def fake_compat(p, model, messages, temp, max_tokens):
        calls.append(p["id"])
        if p["id"] == "groq":
            return "", {}, "Invalid API key for Groq (Llama)."
        return "DEEPSEEK RESPONSE", {}, ""

    import src.ai_engine.provider_router as pr

    settings = {
        "groq_api_key": encrypt_key("gsk_bad"),
        "deepseek_api_key": encrypt_key("sk_good"),
    }
    with mock.patch.object(pr, "_call_openai_compat", fake_compat), \
         mock.patch.dict(os.environ, {"SYSTEM_AI_FALLBACK_ENABLED": "false"}):
        res = route_chat(settings, ["hello"], feature="test")

    assert res["provider"] == "deepseek"
    assert res["text"] == "DEEPSEEK RESPONSE"
    assert calls == ["groq", "deepseek"]


def test_sanitize_output():
    assert sanitize_output("```json\n{\"a\":1}\n```") == "{\"a\":1}"


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
