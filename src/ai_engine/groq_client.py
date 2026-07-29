"""
groq_client — Groq API: chat completions, vision, audio transcription, token tracking.
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
_token_tracker: Dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0}

# Default models (overridable via env or per-call)
DEFAULT_TEXT_MODEL = os.getenv("GROQ_TEXT_MODEL", "llama-3.3-70b-versatile")
DEFAULT_VISION_MODEL = os.getenv("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
DEFAULT_WHISPER_MODEL = os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3")


def _get_api_key() -> str:
    """Get Groq API key from env var, secret.txt, .env, or default fallback."""
    key = os.getenv("GROQ_API_KEY", "")
    if key and len(key.strip()) > 10:
        return key.strip()

    from pathlib import Path
    root_dir = Path(__file__).parents[2]

    # Fallback 1: secret.txt in project root
    try:
        secret_file = root_dir / "secret.txt"
        if secret_file.exists():
            for line in secret_file.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if len(line) > 10:
                    os.environ["GROQ_API_KEY"] = line
                    return line
    except Exception:
        pass

    # Fallback 2: .env in project root
    try:
        env_file = root_dir / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if line.startswith("GROQ_API_KEY="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if val and len(val) > 10:
                        os.environ["GROQ_API_KEY"] = val
                        return val
    except Exception:
        pass

    # Fallback 3: No valid key found
    return ""


# ════════════════════════════════════════════════════════════════════════════
# RATE LIMIT GUARD — prevents hitting Groq free tier limits (30 RPM)
# ════════════════════════════════════════════════════════════════════════════
import random as _random
_request_times: List[float] = []  # Timestamps of recent requests
_MAX_RPM = 15  # Very conservative for free tier (actual limit ~30 but throttles aggressively)
_WINDOW_SEC = 60  # Sliding window in seconds
_MIN_GAP_SEC = 2.0  # Minimum 2s gap between requests to avoid burst rate limits

def _rate_limit_guard():
    """Enforce rate limit: if too many requests in last 60s, sleep until safe."""
    now = time.time()
    # Clean old timestamps
    while _request_times and _request_times[0] < now - _WINDOW_SEC:
        _request_times.pop(0)
    # If at limit, wait until oldest request expires
    if len(_request_times) >= _MAX_RPM:
        wait = _request_times[0] - (now - _WINDOW_SEC) + 0.5
        if wait > 0:
            logger.info("Rate guard: %d requests in window, sleeping %.1fs", len(_request_times), wait)
            time.sleep(wait)
            return _rate_limit_guard()  # Re-check after sleep
    # Enforce minimum gap between requests
    if _request_times and (now - _request_times[-1]) < _MIN_GAP_SEC:
        time.sleep(_MIN_GAP_SEC - (now - _request_times[-1]))
    _request_times.append(time.time())


# Eagerly load API key on module import
if not os.getenv("GROQ_API_KEY"):
    _get_api_key()



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
# TEXT CHAT COMPLETIONS (for Rx generation, CME, Research, etc.)
# ════════════════════════════════════════════════════════════════════════════

def call_groq_with_error(messages: list, model: str = None, temp: float = 0.3, max_tokens: int = 4000) -> tuple[str, str]:
    """
    Groq chat completions — returns tuple of (response_text, error_message).
    """
    api_key = _get_api_key()
    if not api_key:
        return "", "Groq API key not configured."

    if model is None:
        model = DEFAULT_TEXT_MODEL

    url = f"{GROQ_BASE_URL}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

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
                content = [
                    {"type": "text", "text": "Analyze this prescription image carefully. Extract patient name, vitals, complaints, medications, and advice."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                ]
                groq_messages.append({"role": "user", "content": content})
            except Exception as e:
                logger.error("Image conversion error: %s", e)

    payload = {
        "model": model,
        "messages": groq_messages,
        "temperature": temp,
        "max_tokens": max_tokens,
    }

    _rate_limit_guard()  # Enforce RPM limit before each call

    last_error = ""
    for attempt in range(3):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=90)
            if resp.status_code == 429:
                # Exponential backoff with jitter: 2s, 4s, 8s + random
                wait = (2 ** (attempt + 1)) + _random.uniform(0, 1)
                last_error = f"Rate limited (attempt {attempt+1}/3, waiting {wait:.1f}s)"
                logger.warning(last_error)
                time.sleep(wait)
                continue
            if resp.status_code == 401:
                return "", "❌ Invalid Groq API key. Please update key in Settings or secret.txt."
            if resp.status_code == 403:
                return "", "❌ Groq API access denied. Check billing/credits at console.groq.com."
            if not resp.ok:
                last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                logger.error("Groq error: %s", last_error)
                time.sleep(1)
                continue
            data = resp.json()
            _update_token_usage(data.get("usage", {}))
            content = data["choices"][0]["message"]["content"]
            return sanitize_output(content), ""
        except requests.exceptions.Timeout:
            last_error = "Request timed out (90s). Groq servers may be slow."
            logger.warning("Groq timeout (attempt %d)", attempt + 1)
            time.sleep(2)
        except requests.exceptions.RequestException as e:
            last_error = f"Network error: {str(e)}"
            logger.error("Groq request error (attempt %d): %s", attempt + 1, e)
            time.sleep(2 ** (attempt + 1))

    return "", last_error or "Groq API failed after 3 attempts. Please try again."


def call_groq(messages: list, model: str = None, temp: float = 0.3, max_tokens: int = 4000) -> str:
    """
    Groq chat completions — returns assistant's text response (cleaned), or empty string on failure.
    """
    text, _ = call_groq_with_error(messages, model=model, temp=temp, max_tokens=max_tokens)
    return text


# ════════════════════════════════════════════════════════════════════════════
# VISION — specifically for batch scan prescription reading
# ════════════════════════════════════════════════════════════════════════════

def call_groq_vision(image, context: str = "") -> str:
    """
    Call Groq vision model with a single image to read handwritten prescription.
    Returns extracted text from the image.
    """
    if not hasattr(image, 'save'):
        # It's a file-like object, convert to PIL Image
        try:
            from PIL import Image
            image = Image.open(image)
        except Exception:
            return ""

    messages = [
        f"""You are an expert Indian pharmacist reading handwritten prescriptions.
Extract ALL information from this prescription image.

Return in this EXACT JSON format (no markdown, no code fences, pure JSON):
{{"patient_name": "name or empty", "phone": "10 digits or empty", "vitals": "BP/HR/Sugar/Weight or empty", "fee": "amount or 0", "complaints": "chief complaints", "diagnosis": "diagnosis if visible", "medicines": "all medicines with doses, frequency, duration", "advice": "lifestyle/diet advice", "follow_up": "follow up instructions", "investigations": "lab tests if mentioned"}}
{f"Context: {context}" if context else ""}""",
        image
    ]
    return call_groq(messages, model=DEFAULT_VISION_MODEL, temp=0.1, max_tokens=2000)


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
