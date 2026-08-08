"""
easyocr_handler — Self-hosted handwriting OCR using Tesseract.
No API key needed. Works offline after install.

Two-step pipeline:
  1. Tesseract OCR: image → raw text (handwriting recognition)
  2. AI text model (DeepSeek/Groq): raw text → structured clinical JSON

For digital ink (pen on white canvas), Tesseract works well with:
  - Grayscale conversion
  - Binary threshold (OTSU)
  - Sharpening filter
  - PSM 6 (assume uniform block of text)
"""

from __future__ import annotations

import io
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_tesseract_available: Optional[bool] = None


def _check_tesseract() -> bool:
    """Check if tesseract is installed and working."""
    global _tesseract_available
    if _tesseract_available is not None:
        return _tesseract_available
    try:
        import pytesseract
        version = pytesseract.get_tesseract_version()
        logger.info("Tesseract OCR available: v%s", version)
        _tesseract_available = True
        return True
    except Exception as e:
        logger.error("Tesseract not available: %s", e)
        _tesseract_available = False
        return False


def _preprocess_for_handwriting(image):
    """
    Preprocess image for better handwriting OCR:
    1. Convert to grayscale
    2. Apply binary threshold (OTSU) to make text black, bg white
    3. Apply slight sharpening
    """
    try:
        from PIL import ImageFilter, ImageOps
        import numpy as np

        # Grayscale
        if image.mode != 'L':
            img_gray = image.convert('L')
        else:
            img_gray = image

        # Invert if needed (assume dark text on light bg)
        # Check if most pixels are dark (inverted image)
        arr = np.array(img_gray)
        if np.mean(arr) < 128:
            img_gray = ImageOps.invert(img_gray)
            arr = np.array(img_gray)

        # OTSU threshold: separate text from background
        threshold = _otsu_threshold(arr)
        img_bw = img_gray.point(lambda p: 0 if p < threshold else 255, '1')

        # Convert back to 'L' for Tesseract
        img_final = img_bw.convert('L')

        # Slight sharpen
        img_final = img_final.filter(ImageFilter.SHARPEN)

        return img_final

    except Exception as e:
        logger.warning("Image preprocessing failed, using original: %s", e)
        return image.convert('L') if image.mode != 'L' else image


def _otsu_threshold(arr):
    """Simple OTSU threshold calculation."""
    try:
        import numpy as np
        hist, _ = np.histogram(arr, bins=256, range=(0, 256))
        total = arr.size
        sum_all = np.sum(np.arange(256) * hist)
        weight_bg = 0
        sum_bg = 0
        max_var = 0
        threshold = 128

        for t in range(256):
            weight_bg += hist[t]
            if weight_bg == 0:
                continue
            weight_fg = total - weight_bg
            if weight_fg == 0:
                break
            sum_bg += t * hist[t]
            mean_bg = sum_bg / weight_bg
            mean_fg = (sum_all - sum_bg) / weight_fg
            var_between = weight_bg * weight_fg * (mean_bg - mean_fg) ** 2
            if var_between > max_var:
                max_var = var_between
                threshold = t
        return threshold
    except Exception:
        return 128


def ocr_handwriting(image) -> tuple[str, Optional[str]]:
    """
    Extract handwritten text from a PIL Image using Tesseract OCR.

    Args:
        image: PIL Image object

    Returns:
        (extracted_text, error_message)
    """
    if not _check_tesseract():
        return "", "Tesseract OCR not installed on server"

    try:
        import pytesseract

        # Preprocess image
        processed = _preprocess_for_handwriting(image)

        # OCR with optimal settings for handwriting
        # PSM 6 = Assume a uniform block of text
        # PSM 11 = Sparse text (try both)
        configs = [
            '--psm 6 -c tessedit_char_whitelist="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,;:/\\-+()[]%&@!?\'\" "',
            '--psm 11',
            '--psm 3',
        ]

        best_text = ""
        for config in configs:
            try:
                text = pytesseract.image_to_string(processed, lang='eng', config=config)
                text = text.strip()
                if len(text) > len(best_text):
                    best_text = text
            except Exception:
                continue

        if not best_text or len(best_text.strip()) < 3:
            return "", None

        logger.info("Tesseract OCR extracted %d chars", len(best_text))
        return best_text.strip(), None

    except Exception as e:
        logger.error("Tesseract OCR error: %s", e)
        return "", str(e)


def ocr_handwriting_from_bytes(image_bytes: bytes) -> tuple[str, Optional[str]]:
    """Extract handwritten text from raw image bytes."""
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode not in ('RGB', 'L'):
            img = img.convert('RGB')
        return ocr_handwriting(img)
    except Exception as e:
        return "", f"Image decode error: {e}"
