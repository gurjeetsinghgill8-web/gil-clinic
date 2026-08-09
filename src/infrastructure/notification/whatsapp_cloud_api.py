"""WhatsApp Cloud API Client — Meta WhatsApp Business Platform.

Sends WhatsApp messages via the Meta Cloud API.
Uses pre-approved message templates for:
- Patient token slip after registration
- Report ready notification
- Doctor alert for new patient

Fallback: Returns wa.me links if Cloud API not configured.
"""

from __future__ import annotations

import logging
import os
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_API_VERSION = "v18.0"
WHATSAPP_API_URL = (
    f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    if WHATSAPP_PHONE_NUMBER_ID
    else ""
)


def sanitize_phone(phone: str) -> str:
    """Sanitize phone number for WhatsApp API (remove +, spaces, etc.)."""
    import re

    cleaned = re.sub(r"[^\d]", "", phone)
    if len(cleaned) == 10:
        return "91" + cleaned  # India default
    return cleaned


def build_wa_me_url(phone: str, message: str) -> str:
    """Build a wa.me link as fallback."""
    sanitized = sanitize_phone(phone)
    encoded = quote(message)
    return f"https://wa.me/{sanitized}?text={encoded}"


async def send_whatsapp_message(
    to_phone: str,
    message: str,
) -> dict:
    """Send a WhatsApp text message via Meta Cloud API.

    Args:
        to_phone: Recipient phone number (with or without country code).
        message: Message text to send.

    Returns:
        dict with 'ok': bool, 'method': str ('cloud_api' or 'wa_me_link'), 'url': str.
    """
    if not to_phone:
        return {"ok": False, "method": "none", "error": "No phone number"}

    sanitized = sanitize_phone(to_phone)

    # Try Cloud API if configured
    if WHATSAPP_PHONE_NUMBER_ID and WHATSAPP_ACCESS_TOKEN:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    WHATSAPP_API_URL,
                    headers={
                        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "messaging_product": "whatsapp",
                        "recipient_type": "individual",
                        "to": sanitized,
                        "type": "text",
                        "text": {"preview_url": False, "body": message},
                    },
                )
                if response.status_code == 200:
                    logger.info("WhatsApp sent via Cloud API to %s", sanitized)
                    return {"ok": True, "method": "cloud_api"}
                else:
                    logger.warning(
                        "WhatsApp Cloud API failed: %s %s",
                        response.status_code,
                        response.text[:200],
                    )
        except Exception as e:
            logger.error("WhatsApp Cloud API error: %s", e)

    # Fallback to wa.me link
    wa_url = build_wa_me_url(to_phone, message)
    logger.info("WhatsApp fallback wa.me link for %s", sanitized)
    return {"ok": True, "method": "wa_me_link", "url": wa_url}


def build_patient_token_message(
    patient_name: str,
    token_number: str,
    service: str,
    clinic_name: str = "GIL CLINIC",
    tracking_url: str = "",
) -> str:
    """Build WhatsApp message for patient token slip.

    Args:
        tracking_url: Secure public tracking URL e.g. /track/{token}.
                      If empty, no tracking link is included.
    """
    track_line = f"📱 Track your status:\n{tracking_url}\n\n" if tracking_url else ""
    return (
        f"🏥 *{clinic_name} — Patient Token Slip*\n\n"
        f"👤 *Patient:* {patient_name}\n"
        f"🎟️ *Token:* #{token_number}\n"
        f"🩺 *Service:* {service}\n"
        f"📌 *Status:* Registered & In Queue\n\n"
        f"{track_line}"
        f"— {clinic_name}"
    )


def build_doctor_alert_message(
    patient_name: str,
    token_number: str,
    service: str,
) -> str:
    """Build WhatsApp message for doctor alert on new patient."""
    return (
        f"🩺 *New Patient Alert*\n\n"
        f"👤 *{patient_name}* registered for *{service}*\n"
        f"🎟️ Token: #{token_number}\n\n"
        f"📋 Check your OPD dashboard."
    )
