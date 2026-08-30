"""
provider_router — Multi-provider AI router for GIL CLINIC (GHOS v2).

Replaces the old single-wallet model (Groq → DeepSeek on OUR keys) with:

  Mode "auto"   (default) : Direct BYOK — clinic's own keys (OpenAI / Anthropic /
                            Groq / DeepSeek / Gemini) called directly. Clinic pays
                            its own provider bill. ₹0 middleman. ₹0 for GIL CLINIC.
  Mode "puter"             : Browser-side Puter AI (user-pays). Server returns a
                            `puter_needed` marker with the prompt; the browser
                            gateway calls puter.ai.* and re-posts the result.
  Mode "off"               : AI disabled for this clinic.
  System fallback          : Legacy GIL CLINIC keys (env/secret.txt/.env) — used
                            only when a clinic has no key AND
                            SYSTEM_AI_FALLBACK_ENABLED != "false" (capped emergency).

All provider keys are stored encrypted (Fernet) in opd_settings with the
"enc:v1:" prefix; legacy plaintext values are still readable for migration.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# PROVIDER REGISTRY — OpenAI-compatible endpoints for 5 providers
# ═══════════════════════════════════════════════════════════════════════════════

PROVIDERS: Dict[str, Dict[str, Any]] = {
    "groq": {
        "label": "Groq (Llama)",
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile",
        "vision_model": "meta-llama/llama-4-scout-17b-16e-instruct",
        "audio_model": "whisper-large-v3",
        "supports_vision": True,
        "supports_audio": True,
        "key_field": "groq_api_key",
        "system_env": "GROQ_API_KEY",
    },
    "deepseek": {
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "vision_model": None,
        "audio_model": None,
        "supports_vision": False,
        "supports_audio": False,
        "key_field": "deepseek_api_key",
        "system_env": "DEEPSEEK_KEY",
    },
    "gemini": {
        "label": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model": "gemini-2.0-flash",
        "vision_model": "gemini-2.0-flash",
        "audio_model": "gemini-2.0-flash",
        "supports_vision": True,
        "supports_audio": True,
        "key_field": "gemini_api_key",
        "system_env": "GEMINI_API_KEY",
    },
    "openai": {
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "vision_model": "gpt-4o-mini",
        "audio_model": "whisper-1",
        "supports_vision": True,
        "supports_audio": True,
        "key_field": "openai_api_key",
        "system_env": "OPENAI_API_KEY",
    },
    "anthropic": {
        "label": "Anthropic (Claude)",
        "base_url": "https://api.anthropic.com/v1",
        "model": "claude-3-5-haiku-latest",
        "vision_model": "claude-3-5-haiku-latest",
        "audio_model": None,
        "supports_vision": True,
        "supports_audio": False,
        "key_field": "anthropic_api_key",
        "system_env": "ANTHROPIC_API_KEY",
    },
}

# Cheap/quality-balanced order; clinics pay their own provider anyway.
CHAT_ORDER = ["groq", "deepseek", "gemini", "openai", "anthropic"]
VISION_ORDER = ["gemini", "openai", "groq", "anthropic"]
AUDIO_ORDER = ["groq", "openai", "gemini"]

# ═══════════════════════════════════════════════════════════════════════════════
# ENCRYPTION — Fernet, key derived from GHOS_AI_KEYS_SECRET (or SECRET_KEY)
# ═══════════════════════════════════════════════════════════════════════════════

_ENC_PREFIX = "enc:v1:"
_fernet_instance = None


def _fernet():
    global _fernet_instance
    if _fernet_instance is None:
        from cryptography.fernet import Fernet

        secret = (
            os.getenv("GHOS_AI_KEYS_SECRET")
            or os.getenv("SECRET_KEY")
            or "gil-clinic-ai-keys-dev-only-change-me"
        )
        digest = hashlib.sha256(secret.encode("utf-8")).digest()
        _fernet_instance = Fernet(base64.urlsafe_b64encode(digest))
    return _fernet_instance


def encrypt_key(plaintext: str) -> str:
    """Encrypt an API key for storage. Empty string stays empty."""
    if not plaintext or not plaintext.strip():
        return ""
    return _ENC_PREFIX + _fernet().encrypt(plaintext.strip().encode("utf-8")).decode("utf-8")


_MASK_VALUES = {"", "••••••••", "********", "****", "(in secret.txt)"}


def decrypt_key(value: str) -> str:
    """Decrypt a stored key. Handles legacy plaintext values transparently."""
    if not value or value in _MASK_VALUES:
        return ""
    if value.startswith(_ENC_PREFIX):
        try:
            return _fernet().decrypt(value[len(_ENC_PREFIX):].encode("utf-8")).decode("utf-8")
        except Exception:
            logger.warning("Could not decrypt API key (secret changed?) — treated as unset")
            return ""
    return value  # legacy plaintext


def is_key_set(value: str) -> bool:
    return bool(decrypt_key(value))


def mask_value(value: str) -> str:
    """UI-safe masked display of a stored key."""
    return "••••••••" if is_key_set(value) else ""


def system_fallback_enabled() -> bool:
    return os.getenv("SYSTEM_AI_FALLBACK_ENABLED", "true").strip().lower() != "false"


# ═══════════════════════════════════════════════════════════════════════════════
# GIL AI WALLET MODE ("gilwallet") — owner-owned prepaid credits (Phase 1)
# Puter primary rehta hai; ye mode sasta backup hai. System keys (Groq/DeepSeek/
# Gemini env se) use hoti hain aur har call par wallet balance se cost katta hai.
# ═══════════════════════════════════════════════════════════════════════════════

_WALLET_FEATURE_COST_PAISE = {
    "generate-rx": 200,
    "generate-diagnosis": 100,
    "generate-followup-rx": 200,
    "optimize-rx": 150,
    "clinical-support": 150,
    "drug-review": 100,
    "handwriting-ocr": 100,
    "handwriting-ocr-struct": 0,  # struct is part of handwriting-ocr call
    "scan-ai": 100,
    "lab-report-analyze": 200,
    "transcribe": 100,
    "specialty-upgrade": 300,
    "cme": 300,
    "research": 300,
}


def _wallet_margin() -> float:
    try:
        return max(1.0, float(os.getenv("AI_WALLET_MARGIN", "2.0")))
    except Exception:
        return 2.0


def wallet_cost_paise(feature: str) -> int:
    base = _WALLET_FEATURE_COST_PAISE.get(feature, 100)
    return int(round(base * _wallet_margin()))


def _secret_file_keys() -> Dict[str, str]:
    """secret.txt (project root) se keys — groq_client jaisa hi behavior."""
    out: Dict[str, str] = {}
    try:
        p = Path(__file__).resolve().parents[2] / "secret.txt"
        if p.exists():
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                out[k.strip().upper()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return out


def _system_wallet_providers() -> List[Dict[str, Any]]:
    """Owner ke system keys (env → secret.txt) — wallet mode ke liye."""
    secrets = _secret_file_keys()
    out: List[Dict[str, Any]] = []
    for pid, env in (("groq", "GROQ_API_KEY"), ("deepseek", "DEEPSEEK_API_KEY"), ("gemini", "GEMINI_API_KEY")):
        key = os.getenv(env, "") or secrets.get(env, "") or secrets.get(f"{pid.upper()}_KEY", "")
        if not key:
            continue
        p = PROVIDERS[pid]
        out.append({
            "id": pid,
            "label": p["label"],
            "key": key,
            "base_url": p["base_url"],
            "model": p["model"],
            "vision_model": p["vision_model"],
            "audio_model": p["audio_model"],
            "supports_vision": p["supports_vision"],
            "supports_audio": p["supports_audio"],
        })
    return out


def _wallet_precheck(settings: Optional[Dict[str, Any]], feature: str):
    """Wallet mode: call se pehle balance check (SYNC — router functions sync hain).
    Returns (ok, balance_paise)."""
    try:
        from main_v2 import SessionLocal  # deferred import (runtime loaded)
        from src.infrastructure.opd.models.ai_wallet_model import AIWalletModel

        clinic_id = (settings or {}).get("doctor_id") or "clinic_default"
        with SessionLocal() as session:
            w = session.get(AIWalletModel, clinic_id)
            balance = int(w.balance_paise) if w else 0
        cost = wallet_cost_paise(feature)
        if balance < cost:
            return False, balance
        return True, balance
    except Exception as exc:
        logger.warning("wallet precheck failed: %s", exc)
        return True, 0


def _wallet_deduct(settings: Optional[Dict[str, Any]], feature: str) -> None:
    try:
        from main_v2 import SessionLocal  # deferred import (runtime loaded)
        from src.infrastructure.opd.models.ai_wallet_model import AIWalletModel, AIWalletTxnModel

        clinic_id = (settings or {}).get("doctor_id") or "clinic_default"
        cost = wallet_cost_paise(feature)
        with SessionLocal() as session:
            w = session.get(AIWalletModel, clinic_id)
            if not w:
                w = AIWalletModel(clinic_id=clinic_id, balance_paise=0,
                                  total_recharged_paise=0, total_spent_paise=0)
                session.add(w)
                session.flush()
            w.balance_paise = int(w.balance_paise or 0) - cost
            w.total_spent_paise = int(w.total_spent_paise or 0) + cost
            session.add(AIWalletTxnModel(clinic_id=clinic_id, delta_paise=-cost, reason=feature))
            session.commit()
            logger.info("wallet: -%d paise (%s) balance=%d", cost, feature, int(w.balance_paise))
    except Exception as exc:
        logger.warning("wallet deduct failed: %s", exc)


def puter_model_id(settings: Optional[Dict[str, Any]] = None) -> str:
    """Model id to send to Puter AI (from clinic's ai_model override or a safe default)."""
    override = ((settings or {}).get("ai_model") or "").strip()
    return override or "gpt-4o-mini"


def _mode_of(settings: Optional[Dict[str, Any]]) -> str:
    return ((settings or {}).get("ai_mode") or "auto").strip().lower()


# ═══════════════════════════════════════════════════════════════════════════════
# KEY RESOLUTION
# ═══════════════════════════════════════════════════════════════════════════════

def resolve_provider_keys(settings: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ordered list of providers that have a usable (decrypted) clinic key."""
    out: List[Dict[str, Any]] = []
    for pid in CHAT_ORDER:
        p = PROVIDERS[pid]
        key = decrypt_key((settings or {}).get(p["key_field"], "") or "")
        if key:
            out.append({
                "id": pid,
                "label": p["label"],
                "key": key,
                "base_url": p["base_url"],
                "model": p["model"],
                "vision_model": p["vision_model"],
                "audio_model": p["audio_model"],
                "supports_vision": p["supports_vision"],
                "supports_audio": p["supports_audio"],
            })
    return out


def ai_config_summary(settings: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Public (no secrets) summary for the browser /api/ai-config endpoint."""
    keys = {}
    for pid in CHAT_ORDER:
        p = PROVIDERS[pid]
        keys[pid] = is_key_set((settings or {}).get(p["key_field"], "") or "")
    return {
        "mode": _mode_of(settings),
        "model": puter_model_id(settings),
        "keys": keys,
        "system_fallback": system_fallback_enabled(),
        "puter_enabled": True,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# MESSAGE BUILDING
# ═══════════════════════════════════════════════════════════════════════════════

def _pil_to_data_uri(image) -> str:
    buf = io.BytesIO()
    img = image
    if hasattr(img, "mode") and img.mode in ("RGBA", "LA", "P"):
        from PIL import Image as _PILImage

        background = _PILImage.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        background.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
        img = background
    elif hasattr(img, "mode") and img.mode != "RGB":
        img = img.convert("RGB")
    img.save(buf, format="JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")


def _build_openai_messages(messages: List[Any]) -> List[Dict[str, Any]]:
    """Convert mixed text+image lists into OpenAI-compatible messages."""
    openai_messages: List[Dict[str, Any]] = []
    text_items = [m for m in messages if isinstance(m, str)]
    if len(text_items) == 1:
        openai_messages.append({"role": "user", "content": text_items[0]})
    else:
        for i, item in enumerate(messages):
            if isinstance(item, str):
                role = "system" if i == 0 else "user"
                openai_messages.append({"role": role, "content": item})

    for item in messages:
        if hasattr(item, "save"):  # PIL image
            openai_messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": "Analyze this medical document image carefully."},
                    {"type": "image_url", "image_url": {"url": _pil_to_data_uri(item)}},
                ],
            })
    return openai_messages


def _messages_to_puter_prompt(messages: List[Any]) -> str:
    parts = [m for m in messages if isinstance(m, str)]
    return "\n\n".join(parts).strip()


def _image_to_puter_prompt(context: str = "") -> str:
    base = (
        "You are a world-class AI Clinical Specialist reading handwritten doctor "
        "prescriptions AND pathology lab reports.\n"
        "Extract ALL clinical information from this document image.\n\n"
        "Return ONLY valid JSON (no markdown, no code fences):\n"
        '{"patient_name":"name or empty","phone":"10 digits or empty","age":"years or empty",'
        '"gender":"Male/Female/empty","vitals":"BP/HR/Sugar/Weight or empty",'
        '"complaints":"chief complaints","diagnosis":"diagnoses or impressions",'
        '"medicines":"all medicines with doses, frequency, and duration",'
        '"investigations":"lab test results with values and abnormal flags",'
        '"advice":"lifestyle/diet advice","follow_up":"follow up date or instructions"}'
    )
    if context:
        base += f"\n\nContext: {context}"
    return base


# ═══════════════════════════════════════════════════════════════════════════════
# LOW-LEVEL CALLS
# ═══════════════════════════════════════════════════════════════════════════════

_last_call: Dict[str, float] = {}


def _min_gap(pid: str):
    """Light per-provider pacing (avoid accidental provider rate-limits)."""
    now = time.time()
    prev = _last_call.get(pid, 0.0)
    if now - prev < 0.6:
        time.sleep(0.6 - (now - prev))
    _last_call[pid] = time.time()


def _call_openai_compat(p: Dict[str, Any], model: str, messages: List[Dict[str, Any]],
                        temp: float, max_tokens: int) -> Tuple[str, Dict[str, int], str]:
    url = p["base_url"].rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {p['key']}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": messages, "temperature": temp, "max_tokens": max_tokens}
    _min_gap(p["id"])
    for attempt in range(3):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=90)
            if resp.status_code == 401:
                return "", {}, f"Invalid API key for {p['label']}."
            if resp.status_code == 403:
                return "", {}, f"{p['label']} access denied — check billing/credits on the clinic's own account."
            if resp.status_code == 429:
                wait = (2 ** (attempt + 1)) + 0.5
                logger.warning("%s rate limited (attempt %d/3, wait %.1fs)", p["id"], attempt + 1, wait)
                time.sleep(wait)
                continue
            if not resp.ok:
                logger.error("%s HTTP %d: %s", p["id"], resp.status_code, resp.text[:200])
                time.sleep(1)
                continue
            data = resp.json()
            usage = data.get("usage") or {}
            usage = {
                "prompt_tokens": int(usage.get("prompt_tokens", 0) or 0),
                "completion_tokens": int(usage.get("completion_tokens", 0) or 0),
            }
            text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
            if text:
                return text, usage, ""
            return "", usage, f"{p['label']} returned empty content."
        except requests.exceptions.Timeout:
            logger.warning("%s timeout (attempt %d)", p["id"], attempt + 1)
            time.sleep(2)
        except requests.exceptions.RequestException as e:
            logger.error("%s error (attempt %d): %s", p["id"], attempt + 1, e)
            time.sleep(2 ** (attempt + 1))
    return "", {}, f"{p['label']} failed after 3 attempts."


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC ROUTERS
# ═══════════════════════════════════════════════════════════════════════════════

def route_chat(settings: Optional[Dict[str, Any]], messages: List[Any], feature: str = "",
               model: Optional[str] = None, temp: float = 0.3, max_tokens: int = 4000) -> Dict[str, Any]:
    """Route a text AI call.

    Returns dict with: text, error, provider, model, usage {prompt_tokens, completion_tokens}
    OR (puter mode): puter_needed=True, prompt, model  → browser must call Puter AI.
    """
    mode = _mode_of(settings)
    if mode == "off":
        return {"text": "", "error": "AI is turned off in clinic Settings → AI Provider.", "provider": "", "model": "", "usage": {}}
    if mode == "puter":
        return {
            "text": "", "error": "", "provider": "puter", "model": puter_model_id(settings),
            "usage": {}, "puter_needed": True, "code": "PUTER_CHAT",
            "prompt": _messages_to_puter_prompt(messages),
        }

    providers = resolve_provider_keys(settings)
    override = ((settings or {}).get("ai_model") or "").strip()
    errors: List[str] = []

    # ── GIL AI Wallet mode: owner's system keys + prepaid balance ──
    is_wallet = mode == "gilwallet"
    if is_wallet:
        providers = _system_wallet_providers()
        if not providers:
            return {"text": "", "error": "GIL Wallet mode on hai par system AI keys set nahi hain (owner: .env mein GROQ_API_KEY/DEEPSEEK_API_KEY/GEMINI_API_KEY).", "provider": "", "model": "", "usage": {}}
        ok, bal = _wallet_precheck(settings, feature)
        if not ok:
            return {"text": "", "error": f"Wallet balance kam hai (₹{bal/100:.2f}) — UPI se Recharge karo (Settings → GIL Wallet).", "provider": "", "model": "", "usage": {}, "wallet_low": True}

    for p in providers:
        pmodel = override or model or p["model"]
        text, usage, err = _call_openai_compat(p, pmodel, _build_openai_messages(messages), temp, max_tokens)
        if text:
            if is_wallet:
                _wallet_deduct(settings, feature)
            return {"text": text, "error": "", "provider": p["id"], "model": pmodel, "usage": usage}
        if err:
            errors.append(f"{p['label']}: {err}")

    # ── System emergency fallback (GIL CLINIC legacy keys) ──
    # Wallet mode mein fallback nahi — wallet ke andar hi balance kata hai
    if not is_wallet and system_fallback_enabled():
        try:
            from src.ai_engine.groq_client import call_groq_with_error

            text, err = call_groq_with_error(list(messages), model=None, temp=temp, max_tokens=max_tokens)
            if text:
                logger.warning("[AI] system fallback used for feature=%s", feature)
                return {"text": text, "error": "", "provider": "system_groq", "model": "auto", "usage": {}}
            if err:
                errors.append(f"system fallback: {err}")
        except Exception as e:
            errors.append(f"system fallback error: {e}")

    return {
        "text": "", "provider": "", "model": "",
        "error": "; ".join(errors) or "No AI provider configured. Clinic owner: Settings → AI Provider → add a key.",
        "usage": {},
    }


def route_vision(settings: Optional[Dict[str, Any]], image, feature: str = "",
                 context: str = "", temp: float = 0.1, max_tokens: int = 2500,
                 prompt_text: Optional[str] = None) -> Dict[str, Any]:
    """Route a vision/OCR call (handwritten Rx, scans, lab reports).

    prompt_text overrides the default clinical-document prompt (e.g. lab reports
    need a list-shaped JSON extraction prompt).
    """
    mode = _mode_of(settings)
    if mode == "off":
        return {"text": "", "error": "AI is turned off in clinic Settings → AI Provider.", "provider": "", "usage": {}}
    if mode == "puter":
        return {
            "text": "", "error": "", "provider": "puter", "model": puter_model_id(settings),
            "usage": {}, "puter_needed": True, "code": "PUTER_OCR",
            "prompt": prompt_text or _image_to_puter_prompt(context),
        }

    providers = [p for p in resolve_provider_keys(settings) if p["supports_vision"]]
    override = ((settings or {}).get("ai_model") or "").strip()
    errors: List[str] = []

    is_wallet = mode == "gilwallet"
    if is_wallet:
        providers = [p for p in _system_wallet_providers() if p["supports_vision"]]
        if not providers:
            return {"text": "", "error": "GIL Wallet mode: system vision key set nahi hai (owner: .env mein GROQ_API_KEY ya GEMINI_API_KEY).", "provider": "", "usage": {}}
        ok, bal = _wallet_precheck(settings, feature)
        if not ok:
            return {"text": "", "error": f"Wallet balance kam hai (₹{bal/100:.2f}) — UPI se Recharge karo.", "provider": "", "usage": {}, "wallet_low": True}

    prompt_text = prompt_text or _image_to_puter_prompt(context)
    vision_messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": prompt_text},
            {"type": "image_url", "image_url": {"url": _pil_to_data_uri(image)}},
        ],
    }]

    for p in providers:
        pmodel = override or p["vision_model"]
        text, usage, err = _call_openai_compat(p, pmodel, vision_messages, temp, max_tokens)
        if text:
            if is_wallet:
                _wallet_deduct(settings, feature)
            return {"text": text, "error": "", "provider": p["id"], "model": pmodel, "usage": usage}
        if err:
            errors.append(f"{p['label']}: {err}")

    if not is_wallet and system_fallback_enabled():
        try:
            from src.ai_engine.groq_client import call_vision_with_fallback

            text, err, provider = call_vision_with_fallback(image, context=context)
            if text and len(text.strip()) > 3:
                logger.warning("[AI] system vision fallback used for feature=%s", feature)
                return {"text": text, "error": "", "provider": f"system_{provider}", "model": "auto", "usage": {}}
            if err:
                errors.append(f"system fallback: {err}")
        except Exception as e:
            errors.append(f"system fallback error: {e}")

    return {
        "text": "", "provider": "",
        "error": "; ".join(errors) or "No vision provider configured. Clinic owner: Settings → AI Provider → add a key.",
        "usage": {},
    }


def route_transcribe(settings: Optional[Dict[str, Any]], audio_bytes: bytes,
                     filename: str = "audio.webm", feature: str = "") -> Dict[str, Any]:
    """Route an audio transcription call (voice scribe)."""
    mode = _mode_of(settings)
    if mode == "off":
        return {"text": "", "error": "AI is turned off in clinic Settings → AI Provider.", "provider": "", "usage": {}}
    if mode == "puter":
        return {
            "text": "", "error": "", "provider": "puter", "model": puter_model_id(settings),
            "usage": {}, "puter_needed": True, "code": "PUTER_TRANSCRIBE",
        }

    providers = [p for p in resolve_provider_keys(settings) if p["supports_audio"]]
    errors: List[str] = []

    is_wallet = mode == "gilwallet"
    if is_wallet:
        providers = [p for p in _system_wallet_providers() if p["supports_audio"]]
        if not providers:
            return {"text": "", "error": "GIL Wallet mode: system audio key set nahi hai.", "provider": "", "usage": {}}
        ok, bal = _wallet_precheck(settings, feature)
        if not ok:
            return {"text": "", "error": f"Wallet balance kam hai (₹{bal/100:.2f}) — UPI se Recharge karo.", "provider": "", "usage": {}, "wallet_low": True}

    ext = filename.lower().split(".")[-1] if "." in filename else "webm"
    mime_map = {
        "webm": "audio/webm", "wav": "audio/wav", "mp3": "audio/mpeg",
        "m4a": "audio/mp4", "ogg": "audio/ogg", "mp4": "audio/mp4",
    }
    content_type = mime_map.get(ext, "audio/webm")

    for p in providers:
        url = p["base_url"].rstrip("/") + "/audio/transcriptions"
        _min_gap(p["id"])
        try:
            resp = requests.post(
                url,
                headers={"Authorization": f"Bearer {p['key']}"},
                files={"file": (filename, audio_bytes, content_type)},
                data={"model": p["audio_model"]},
                timeout=90,
            )
            if resp.status_code == 401:
                errors.append(f"{p['label']}: invalid key")
                continue
            if not resp.ok:
                errors.append(f"{p['label']}: HTTP {resp.status_code}")
                continue
            text = (resp.json().get("text") or "").strip()
            if text:
                if is_wallet:
                    _wallet_deduct(settings, feature)
                return {"text": text, "error": "", "provider": p["id"], "model": p["audio_model"], "usage": {}}
            errors.append(f"{p['label']}: empty transcription")
        except requests.exceptions.RequestException as e:
            errors.append(f"{p['label']}: {e}")

    if not is_wallet and system_fallback_enabled():
        try:
            from src.ai_engine.groq_client import call_whisper

            text = call_whisper(audio_bytes, filename)
            if text:
                logger.warning("[AI] system whisper fallback used for feature=%s", feature)
                return {"text": text, "error": "", "provider": "system_whisper", "model": "auto", "usage": {}}
        except Exception as e:
            errors.append(f"system fallback error: {e}")

    return {
        "text": "", "provider": "",
        "error": "; ".join(errors) or "No audio provider configured. Clinic owner: Settings → AI Provider → add a key.",
        "usage": {},
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SANITIZATION (same behaviour as legacy groq_client for UI compatibility)
# ═══════════════════════════════════════════════════════════════════════════════

def sanitize_output(text: str) -> str:
    try:
        import re as _re

        cleaned = _re.sub(r"```[\w]*\n?", "", text)
        cleaned = _re.sub(r"```", "", cleaned).strip()
        return cleaned.encode("utf-8", errors="replace").decode("utf-8")
    except Exception:
        return (text or "").strip()


def parse_ai_json(text: str) -> dict:
    """Parse AI response that should be JSON. Tolerates markdown fences."""
    if not text:
        return {}
    try:
        import re as _re

        cleaned = _re.sub(r"```json?\s*", "", text)
        cleaned = _re.sub(r"```", "", cleaned).strip()
        return json.loads(cleaned)
    except json.JSONDecodeError:
        try:
            import re as _re

            match = _re.search(r"\{[^{}]+\}", text, _re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception:
            pass
    return {}
