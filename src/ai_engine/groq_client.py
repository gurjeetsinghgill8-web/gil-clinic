"""
groq_client — Dual AI Provider: Groq (primary) + DeepSeek (fallback).
All AI calls go through this module. No business logic here, just API wrappers.
"""

import base64
import io
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Union

import os
import requests

logger = logging.getLogger(__name__)

GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
_token_tracker: Dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0}

# Default models (overridable via env or per-call)
DEFAULT_TEXT_MODEL = os.getenv("GROQ_TEXT_MODEL", "llama-3.3-70b-versatile")
DEFAULT_VISION_MODEL = os.getenv("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
DEFAULT_WHISPER_MODEL = os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")


def _read_keys_from_file(filepath) -> dict:
    """Read GROQ_KEY=, DEEPSEEK_KEY=, GOOGLE_VISION_KEY= from a file."""
    keys = {"groq": "", "deepseek": "", "google_vision": ""}
    try:
        if filepath.exists():
            for line in filepath.read_text().splitlines():
                line = line.strip()
                if line.startswith("#") or not line:
                    continue
                if line.startswith("GROQ_KEY="):
                    keys["groq"] = line.split("=", 1)[1].strip().strip('"').strip("'")
                elif line.startswith("DEEPSEEK_KEY="):
                    keys["deepseek"] = line.split("=", 1)[1].strip().strip('"').strip("'")
                elif line.startswith("GOOGLE_VISION_KEY="):
                    keys["google_vision"] = line.split("=", 1)[1].strip().strip('"').strip("'")
                elif line.startswith("sk-") or line.startswith("gsk_"):
                    if line.startswith("gsk_"):
                        keys["groq"] = line
                    elif line.startswith("sk-"):
                        keys["deepseek"] = line
    except Exception:
        pass
    return keys


def _get_api_key() -> str:
    """Get Groq API key from env var, secret.txt, or .env."""
    key = os.getenv("GROQ_API_KEY", "")
    if key and len(key.strip()) > 10:
        return key.strip()

    from pathlib import Path
    root_dir = Path(__file__).parents[2]

    # Check secret.txt
    keys = _read_keys_from_file(root_dir / "secret.txt")
    if keys["groq"] and len(keys["groq"]) > 10:
        os.environ["GROQ_API_KEY"] = keys["groq"]
        return keys["groq"]

    # Check .env
    keys = _read_keys_from_file(root_dir / ".env")
    if keys["groq"] and len(keys["groq"]) > 10:
        os.environ["GROQ_API_KEY"] = keys["groq"]
        return keys["groq"]

    return ""


def _get_deepseek_key() -> str:
    """Get DeepSeek API key from env var, secret.txt, or .env."""
    key = os.getenv("DEEPSEEK_KEY", "")
    if key and len(key.strip()) > 10:
        return key.strip()

    from pathlib import Path
    root_dir = Path(__file__).parents[2]

    # Check secret.txt
    keys = _read_keys_from_file(root_dir / "secret.txt")
    if keys["deepseek"] and len(keys["deepseek"]) > 10:
        os.environ["DEEPSEEK_KEY"] = keys["deepseek"]
        return keys["deepseek"]

    # Check .env
    keys = _read_keys_from_file(root_dir / ".env")
    if keys["deepseek"] and len(keys["deepseek"]) > 10:
        os.environ["DEEPSEEK_KEY"] = keys["deepseek"]
        return keys["deepseek"]

    return ""


def _get_google_vision_key() -> str:
    """Get Google Cloud Vision API key from env var, secret.txt, or .env."""
    key = os.getenv("GOOGLE_VISION_KEY", "")
    if key and len(key.strip()) > 10:
        return key.strip()

    from pathlib import Path
    root_dir = Path(__file__).parents[2]

    keys = _read_keys_from_file(root_dir / "secret.txt")
    if keys.get("google_vision") and len(keys["google_vision"]) > 10:
        os.environ["GOOGLE_VISION_KEY"] = keys["google_vision"]
        return keys["google_vision"]

    keys = _read_keys_from_file(root_dir / ".env")
    if keys.get("google_vision") and len(keys["google_vision"]) > 10:
        os.environ["GOOGLE_VISION_KEY"] = keys["google_vision"]
        return keys["google_vision"]

    return ""


def _get_gemini_key() -> str:
    """Get Google Gemini API key from env var, secret.txt, or .env.
    GEMINI_API_KEY=AIza... (from Google AI Studio: aistudio.google.com)
    """
    key = os.getenv("GEMINI_API_KEY", "")
    if key and len(key.strip()) > 10:
        return key.strip()

    from pathlib import Path
    root_dir = Path(__file__).parents[2]

    for filename in ("secret.txt", ".env"):
        try:
            p = root_dir / filename
            if p.exists():
                for line in p.read_text().splitlines():
                    line = line.strip()
                    if line.startswith("GEMINI_API_KEY="):
                        k = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if k and len(k) > 10:
                            os.environ["GEMINI_API_KEY"] = k
                            return k
        except Exception:
            pass
    return ""


# ════════════════════════════════════════════════════════════════════════════
# RATE LIMIT GUARD — shared across both providers
# ════════════════════════════════════════════════════════════════════════════
import random as _random
_request_times: List[float] = []
_MAX_RPM = 15
_WINDOW_SEC = 60
_MIN_GAP_SEC = 2.0

def _rate_limit_guard():
    """Enforce rate limit: if too many requests in last 60s, sleep until safe."""
    now = time.time()
    while _request_times and _request_times[0] < now - _WINDOW_SEC:
        _request_times.pop(0)
    if len(_request_times) >= _MAX_RPM:
        wait = _request_times[0] - (now - _WINDOW_SEC) + 0.5
        if wait > 0:
            logger.info("Rate guard: %d requests in window, sleeping %.1fs", len(_request_times), wait)
            time.sleep(wait)
            return _rate_limit_guard()
    if _request_times and (now - _request_times[-1]) < _MIN_GAP_SEC:
        time.sleep(_MIN_GAP_SEC - (now - _request_times[-1]))
    _request_times.append(time.time())


# Eagerly load keys on module import
if not os.getenv("GROQ_API_KEY"):
    _get_api_key()
if not os.getenv("DEEPSEEK_KEY"):
    _get_deepseek_key()
if not os.getenv("GOOGLE_VISION_KEY"):
    _get_google_vision_key()
if not os.getenv("GEMINI_API_KEY"):
    _get_gemini_key()



def _update_token_usage(usage: dict) -> None:
    """Track token usage across all API calls."""
    try:
        _token_tracker["prompt_tokens"] += int(usage.get("prompt_tokens", 0))
        _token_tracker["completion_tokens"] += int(usage.get("completion_tokens", 0))
    except (TypeError, ValueError):
        pass


def sanitize_output(text: str) -> str:
    """Clean AI output: remove code fences, trim whitespace, ensure valid UTF-8."""
    try:
        cleaned = re.sub(r"```[\w]*\n?", "", text)
        cleaned = re.sub(r"```", "", cleaned).strip()
        return cleaned.encode("utf-8", errors="replace").decode("utf-8")
    except Exception:
        return text.strip()


def get_token_usage() -> dict:
    """Return cumulative token usage stats."""
    return dict(_token_tracker)


# ════════════════════════════════════════════════════════════════════════════
# DUAL-PROVIDER CORE — tries Groq first, falls back to DeepSeek
# ════════════════════════════════════════════════════════════════════════════

def _call_provider(url: str, api_key: str, model: str, groq_messages: list,
                   temp: float, max_tokens: int, provider_name: str) -> tuple[str, str]:
    """Call a single AI provider. Returns (response_text, error_message)."""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": groq_messages, "temperature": temp, "max_tokens": max_tokens}

    for attempt in range(3):
        try:
            resp = requests.post(f"{url}/chat/completions", headers=headers, json=payload, timeout=90)
            if resp.status_code == 429:
                wait = (2 ** (attempt + 1)) + _random.uniform(0, 1)
                logger.warning("%s rate limited (attempt %d/3, wait %.1fs)", provider_name, attempt + 1, wait)
                time.sleep(wait)
                continue
            if resp.status_code == 401:
                return "", f"❌ Invalid {provider_name} API key."
            if resp.status_code == 403:
                return "", f"❌ {provider_name} access denied. Check billing/credits."
            if not resp.ok:
                logger.error("%s HTTP %d: %s", provider_name, resp.status_code, resp.text[:200])
                time.sleep(1)
                continue
            data = resp.json()
            _update_token_usage(data.get("usage", {}))
            return sanitize_output(data["choices"][0]["message"]["content"]), ""
        except requests.exceptions.Timeout:
            logger.warning("%s timeout (attempt %d)", provider_name, attempt + 1)
            time.sleep(2)
        except requests.exceptions.RequestException as e:
            logger.error("%s error (attempt %d): %s", provider_name, attempt + 1, e)
            time.sleep(2 ** (attempt + 1))

    return "", f"{provider_name} failed after 3 attempts."


def _build_messages(messages: list) -> list:
    """Convert mixed text+image list into API-compatible message format."""
    groq_messages = []
    text_items = [item for item in messages if isinstance(item, str)]
    if len(text_items) == 1:
        groq_messages.append({"role": "user", "content": text_items[0]})
    else:
        for i, item in enumerate(messages):
            if isinstance(item, str):
                role = "system" if i == 0 else "user"
                groq_messages.append({"role": role, "content": item})

    for item in messages:
        if hasattr(item, 'save'):
            try:
                buf = io.BytesIO()
                item.save(buf, format='JPEG', quality=85)
                img_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
                groq_messages.append({"role": "user", "content": [
                    {"type": "text", "text": "Analyze this prescription image carefully."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                ]})
            except Exception as e:
                logger.error("Image conversion error: %s", e)
    return groq_messages


def call_groq_with_error(messages: list, model: str = None, temp: float = 0.3, max_tokens: int = 4000) -> tuple[str, str]:
    """
    Dual-provider AI call: tries Groq first, falls back to DeepSeek if rate-limited.
    Returns tuple of (response_text, error_message).
    """
    groq_messages = _build_messages(messages)
    _rate_limit_guard()

    # ── Try Groq ──
    groq_key = _get_api_key()
    if groq_key:
        if model is None:
            model = DEFAULT_TEXT_MODEL
        text, err = _call_provider(GROQ_BASE_URL, groq_key, model, groq_messages, temp, max_tokens, "Groq")
        if text:
            return text, ""
        # If Groq failed with rate limit (not auth error), try DeepSeek
        if "Invalid" not in err and "access denied" not in err:
            logger.info("Groq unavailable (%s), trying DeepSeek fallback...", err[:60])

    # ── Fallback: DeepSeek ──
    ds_key = _get_deepseek_key()
    if ds_key:
        ds_model = DEEPSEEK_MODEL if (model is None or model == DEFAULT_TEXT_MODEL) else model
        # DeepSeek doesn't support some Groq model names, use deepseek-chat
        if "llama" in ds_model.lower() or "meta" in ds_model.lower():
            ds_model = DEEPSEEK_MODEL
        text, err = _call_provider(DEEPSEEK_BASE_URL, ds_key, ds_model, groq_messages, temp, max_tokens, "DeepSeek")
        if text:
            return text, ""
        return "", err or "DeepSeek fallback also failed."

    return "", "No AI provider available. Configure GROQ_KEY or DEEPSEEK_KEY in secret.txt."


def call_groq(messages: list, model: str = None, temp: float = 0.3, max_tokens: int = 4000) -> str:
    """
    Dual-provider AI call — returns assistant's text response, or empty string on failure.
    Tries Groq → DeepSeek automatically.
    """
    text, _ = call_groq_with_error(messages, model=model, temp=temp, max_tokens=max_tokens)
    return text


# ════════════════════════════════════════════════════════════════════════════
# VISION — specifically for batch scan prescription reading
# ════════════════════════════════════════════════════════════════════════════

def call_groq_vision(image, context: str = "") -> str:
    """
    Call Groq vision model to parse handwritten prescriptions OR pathology lab reports.
    Extracts structured clinical data, lab parameters, abnormal flags, and medicines.
    """
    if not hasattr(image, 'save'):
        # It's a file-like object, convert to PIL Image
        try:
            from PIL import Image
            image = Image.open(image)
        except Exception:
            return ""

    messages = [
        f"""You are a world-class AI Clinical Specialist reading handwritten doctor prescriptions AND pathology lab reports.
Extract ALL clinical information from this document image.

Return in this EXACT JSON format (no markdown, no code fences, pure JSON):
{{"patient_name": "name or empty", "phone": "10 digits or empty", "age": "years or empty", "gender": "Male/Female/empty", "vitals": "BP/HR/Sugar/Weight or empty", "complaints": "chief complaints", "diagnosis": "diagnoses or impressions", "medicines": "all medicines with doses, frequency, and duration", "investigations": "lab test results with values and abnormal flags (e.g. Hb 9.2 L, HbA1c 8.5% H)", "advice": "lifestyle/diet advice", "follow_up": "follow up date or instructions"}}
{f"Context: {context}" if context else ""}""",
        image
    ]
    return call_groq(messages, model=DEFAULT_VISION_MODEL, temp=0.1, max_tokens=2500)


# ════════════════════════════════════════════════════════════════════════════
# GEMINI FLASH VISION — Primary handwriting OCR (no rate limit with paid key)
# ════════════════════════════════════════════════════════════════════════════

GEMINI_VISION_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

def call_gemini_vision(image, context: str = "") -> tuple[str, str]:
    """Call Google Gemini Flash Vision API for handwriting OCR.

    Uses gemini-1.5-flash — excellent handwriting accuracy, ~₹0.02/image.
    Free tier: 15 requests/minute (no API key cost needed for testing).

    Args:
        image: PIL Image object
        context: optional context hint
    Returns:
        (response_text, error_message)
    """
    gemini_key = _get_gemini_key()
    if not gemini_key:
        return "", "GEMINI_API_KEY not configured"

    try:
        buf = io.BytesIO()
        if image.mode in ('RGBA', 'LA', 'P'):
            bg = __import__('PIL.Image', fromlist=['Image']).Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            bg.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
            image = bg
        elif image.mode != 'RGB':
            image = image.convert('RGB')
        image.save(buf, format='JPEG', quality=90)
        img_b64 = base64.b64encode(buf.getvalue()).decode()

        prompt_text = (
            "You are a world-class AI Clinical Specialist reading handwritten doctor prescriptions.\n"
            "Extract ALL clinical information from this image.\n\n"
            "CRITICAL ABBREVIATIONS to expand:\n"
            "DM=Diabetes Mellitus, HTN=Hypertension, CAD=Coronary Artery Disease, IHD=Ischemic Heart Disease, "
            "CKD=Chronic Kidney Disease, COPD=Chronic Obstructive Pulmonary Disease, UTI=Urinary Tract Infection\n"
            "OD=Once Daily, BD=Twice Daily, TDS=Thrice Daily, QID=Four times daily, HS=At bedtime, SOS=As needed\n"
            "BF/AC=Before Food, AF/PC=After Food, Tab.=Tablet, Cap.=Capsule, Syp.=Syrup, Inj.=Injection\n\n"
            "Return ONLY valid JSON (no markdown, no code fences):\n"
            '{"vitals":"BP HR sugar weight etc","complaints":"chief complaints","diagnosis":"ALL diagnoses expanded",'
            '"medicines":"1. Tab. Drug Dose Freq Timing x Duration\\n2. ...","investigations":"comma-separated tests",'
            '"advice":"diet/lifestyle advice","follow_up":"next visit timeline"}'
            + (f"\n\nContext: {context}" if context else "")
        )

        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt_text},
                    {"inline_data": {"mime_type": "image/jpeg", "data": img_b64}},
                ]
            }],
            "generationConfig": {
                "temperature": 0.0,
                "maxOutputTokens": 2000,
            }
        }

        resp = requests.post(
            f"{GEMINI_VISION_URL}?key={gemini_key}",
            json=payload,
            timeout=30,
        )

        if resp.status_code == 429:
            return "", "Gemini rate limited (429) — try again in a moment"
        if resp.status_code == 400:
            err = resp.json().get("error", {}).get("message", "Bad request")
            return "", f"Gemini error: {err}"
        if not resp.ok:
            return "", f"Gemini HTTP {resp.status_code}"

        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            return "", "Gemini returned no candidates"
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts).strip()
        logger.info("Gemini Vision extracted %d chars", len(text))
        return sanitize_output(text), ""

    except requests.exceptions.Timeout:
        return "", "Gemini timeout"
    except Exception as e:
        logger.error("Gemini Vision error: %s", e)
        return "", str(e)


def call_vision_with_fallback(image, context: str = "") -> tuple[str, str, str]:
    """Smart vision OCR: tries Gemini → Groq Vision → Google Vision in priority order.

    Returns:
        (response_text, error_message, provider_used)
        provider_used: "gemini" | "groq_vision" | "google_vision" | "none"

    Priority:
        1. Gemini Flash (best quality, ₹0.02/image, no hard daily limit)
        2. Groq Vision (good quality, 1000/day free limit shared)
        3. Google Cloud Vision (85-90%, 1000/month free, needs structuring)
    """
    # ── 1. Try Gemini Flash ──────────────────────────────────────────────────
    gemini_key = _get_gemini_key()
    if gemini_key:
        text, err = call_gemini_vision(image, context=context)
        if text and len(text.strip()) > 5:
            logger.info("Vision OCR: Gemini Flash success (%d chars)", len(text))
            return text, "", "gemini"
        logger.info("Gemini unavailable (%s), trying Groq Vision...", err[:60] if err else "empty")

    # ── 2. Try Groq Vision (Llama-4 Scout) ──────────────────────────────────
    groq_key = _get_api_key()
    if groq_key:
        text = call_groq_vision(image, context=context)
        if text and len(text.strip()) > 5:
            logger.info("Vision OCR: Groq Vision success (%d chars)", len(text))
            return text, "", "groq_vision"
        logger.info("Groq Vision empty, trying Google Vision...")

    # ── 3. Try Google Cloud Vision ───────────────────────────────────────────
    google_key = _get_google_vision_key()
    if google_key:
        try:
            from src.ai_engine.google_vision_handler import ocr_handwriting_google
            text, err = ocr_handwriting_google(image, google_key)
            if text and len(text.strip()) > 5:
                logger.info("Vision OCR: Google Vision success (%d chars)", len(text))
                return text, "", "google_vision"
            logger.info("Google Vision empty (%s)", err or "no text")
        except Exception as ge:
            logger.error("Google Vision import error: %s", ge)

    return "", "All vision providers unavailable or returned empty results", "none"


def parse_ai_json(text: str) -> dict:
    """Parse AI response that should be JSON. Tolerates markdown fences."""
    if not text:
        return {}
    try:
        # Strip markdown fences
        cleaned = re.sub(r"```json?\s*", "", text)
        cleaned = re.sub(r"```", "", cleaned).strip()
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to find JSON object in the text
        try:
            match = re.search(r'\{[^{}]+\}', text, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception:
            pass
    return {}


# ════════════════════════════════════════════════════════════════════════════
# AUDIO TRANSCRIPTION (Voice Scribe)
# ════════════════════════════════════════════════════════════════════════════

def call_whisper(audio_bytes: bytes, filename: str = "audio.webm") -> str:
    """
    Transcribe audio using Groq Whisper API.
    Accepts raw audio bytes and filename (for content-type detection).
    Returns transcribed text or empty string on failure.
    """
    api_key = _get_api_key()
    if not api_key:
        logger.error("Groq API key not configured for Whisper.")
        return ""

    url = f"{GROQ_BASE_URL}/audio/transcriptions"
    try:
        # Determine content type from filename
        ext = filename.lower().split('.')[-1] if '.' in filename else 'webm'
        mime_map = {
            'webm': 'audio/webm', 'wav': 'audio/wav', 'mp3': 'audio/mpeg',
            'm4a': 'audio/mp4', 'ogg': 'audio/ogg', 'mp4': 'audio/mp4',
        }
        content_type = mime_map.get(ext, 'audio/webm')

        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": (filename, audio_bytes, content_type)},
            data={"model": DEFAULT_WHISPER_MODEL},
            timeout=60,
        )
        resp.raise_for_status()
        text = resp.json().get("text", "")
        return sanitize_output(text)
    except requests.exceptions.RequestException as e:
        logger.error("Whisper transcription error: %s", e)
    except (KeyError, ValueError) as e:
        logger.error("Transcription parse error: %s", e)
    return ""
