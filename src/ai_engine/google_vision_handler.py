"""
google_vision_handler — Google Cloud Vision API for handwriting OCR.
Uses REST API (no heavy client library needed). Free tier: 1000 images/month.

Fallback when Groq Vision is unavailable. Google Lens-level quality.
"""

from __future__ import annotations

import base64
import io
import json
import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

GOOGLE_VISION_URL = "https://vision.googleapis.com/v1/images:annotate"


def ocr_handwriting_google(image, api_key: str) -> tuple[str, Optional[str]]:
    """
    Extract handwritten text using Google Cloud Vision API (REST).

    Args:
        image: PIL Image object
        api_key: Google Cloud Vision API key

    Returns:
        (extracted_text, error_message)
    """
    if not api_key or len(api_key) < 10:
        return "", "Google API key not configured"

    try:
        # Convert PIL image to base64 JPEG
        buf = io.BytesIO()
        if image.mode in ('RGBA', 'LA', 'P'):
            background = __import__('PIL.Image', fromlist=['Image']).new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
            image = background
        elif image.mode != 'RGB':
            image = image.convert('RGB')
        image.save(buf, format='JPEG', quality=90)
        img_b64 = base64.b64encode(buf.getvalue()).decode()

        # Build request
        request_body = {
            "requests": [{
                "image": {"content": img_b64},
                "features": [{
                    "type": "DOCUMENT_TEXT_DETECTION",
                    "maxResults": 1
                }],
                "imageContext": {
                    "languageHints": ["en"]
                }
            }]
        }

        resp = requests.post(
            f"{GOOGLE_VISION_URL}?key={api_key}",
            json=request_body,
            timeout=30
        )

        if resp.status_code != 200:
            error_msg = f"Google Vision HTTP {resp.status_code}"
            try:
                err_data = resp.json()
                error_msg = err_data.get("error", {}).get("message", error_msg)
            except Exception:
                pass
            logger.error("Google Vision error: %s", error_msg)
            return "", error_msg

        data = resp.json()
        responses = data.get("responses", [])
        if not responses:
            return "", "Google Vision returned empty response"

        result = responses[0]
        if "error" in result:
            return "", f"Google Vision: {result['error'].get('message', 'unknown')}"

        full_text = result.get("fullTextAnnotation", {}).get("text", "")
        if not full_text:
            # Try textAnnotations as fallback
            text_ann = result.get("textAnnotations", [])
            if text_ann:
                full_text = text_ann[0].get("description", "")

        if full_text and len(full_text.strip()) >= 3:
            logger.info("Google Vision extracted %d chars", len(full_text))
            return full_text.strip(), None
        else:
            return "", None  # no text found, not an error

    except requests.exceptions.Timeout:
        return "", "Google Vision timeout"
    except Exception as e:
        logger.error("Google Vision exception: %s", e)
        return "", str(e)
