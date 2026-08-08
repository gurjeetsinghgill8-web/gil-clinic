"""
easyocr_handler — Self-hosted handwriting OCR using EasyOCR.
No API key needed. Works offline after first model download.

Two-step pipeline:
  1. EasyOCR: image → raw text (handwriting recognition)
  2. AI text model (DeepSeek/Groq): raw text → structured clinical JSON
"""

from __future__ import annotations

import io
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_easyocr_reader = None
_model_loaded = False
_model_error: Optional[str] = None


def _get_reader():
    """Lazy-load EasyOCR reader (singleton). Downloads models on first call."""
    global _easyocr_reader, _model_loaded, _model_error

    if _model_loaded:
        return _easyocr_reader

    if _model_error:
        return None

    try:
        import easyocr
        # English only for speed; add 'hi' for Hindi if needed
        _easyocr_reader = easyocr.Reader(
            ['en'],
            gpu=False,  # Railway uses CPU
            verbose=False,
        )
        _model_loaded = True
        logger.info("EasyOCR reader initialized successfully (EN)")
        return _easyocr_reader
    except Exception as e:
        _model_error = str(e)
        logger.error("EasyOCR initialization failed: %s", e)
        return None


def ocr_handwriting(image) -> tuple[str, Optional[str]]:
    """
    Extract handwritten text from a PIL Image using EasyOCR.

    Args:
        image: PIL Image object (RGB recommended)

    Returns:
        (extracted_text, error_message)
        - text: All recognized text joined with newlines
        - error: None on success, error string on failure
    """
    reader = _get_reader()
    if reader is None:
        return "", _model_error or "EasyOCR model not loaded"

    try:
        # Convert PIL to numpy array
        import numpy as np
        img_array = np.array(image)

        # Run OCR
        results = reader.readtext(img_array, detail=0, paragraph=True)

        if not results:
            return "", None  # empty = no text found, not an error

        # Join all detected text lines
        text = "\n".join(str(r) for r in results if r and str(r).strip())
        return text.strip(), None

    except Exception as e:
        logger.error("EasyOCR readtext error: %s", e)
        return "", str(e)


def ocr_handwriting_from_bytes(image_bytes: bytes) -> tuple[str, Optional[str]]:
    """
    Extract handwritten text from raw image bytes (JPEG/PNG).
    """
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode not in ('RGB', 'L'):
            img = img.convert('RGB')
        return ocr_handwriting(img)
    except Exception as e:
        return "", f"Image decode error: {e}"
