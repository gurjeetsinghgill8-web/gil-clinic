"""
GIL CLINIC — Universal WhatsApp Phone Number Sanitizer (Python Engine)

Ensures Indian phone numbers are formatted with 91 country code without spaces,
dashes, parentheses, or leading zeros.
"""

import re
import urllib.parse
from typing import Optional


def format_whatsapp_number(phone: str | int | None) -> Optional[str]:
    """Sanitize and format phone numbers for WhatsApp API / wa.me links.
    
    Examples:
        '9876543210'      -> '919876543210'
        '09876543210'     -> '919876543210'
        '+91 98765-43210' -> '919876543210'
        '919876543210'    -> '919876543210'
        '123'             -> None (invalid)
    """
    if not phone:
        return None

    cleaned = re.sub(r"\D", "", str(phone))

    if len(cleaned) == 10:
        return f"91{cleaned}"

    if len(cleaned) == 11 and cleaned.startswith("0"):
        return f"91{cleaned[1:]}"

    if len(cleaned) == 12 and cleaned.startswith("91"):
        return cleaned

    if 10 <= len(cleaned) <= 15:
        return cleaned

    return None


def build_whatsapp_link(phone: str | None, message: str = "") -> str:
    """Build a sanitized wa.me link."""
    sanitized = format_whatsapp_number(phone)
    encoded_msg = urllib.parse.quote(message)
    if sanitized:
        return f"https://wa.me/{sanitized}?text={encoded_msg}"
    return f"https://wa.me/?text={encoded_msg}"
