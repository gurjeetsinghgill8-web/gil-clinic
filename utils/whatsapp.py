"""
WhatsApp Notification Module — Phase 2
========================================
Free notification system using pywhatkit + WhatsApp Web automation.

Setup Required:
  1. Install: pip install pywhatkit pyautogui
  2. An Android phone with WhatsApp Web connected to the same number
  3. Chrome browser (pywhatkit uses web.whatsapp.com)
  4. Phone must stay on with WhatsApp Web connected 24/7

Architecture Note:
  - This module is called FROM the notification triggers in llm_harness.py
  - In Phase 2, each notification trigger will ALSO call send_whatsapp_message()
  - The Harness orchestrator manages both browser and WhatsApp notifications
"""
import os
from datetime import datetime

# Optional import — will only work when pywhatkit is installed
try:
    import pywhatkit
    PYWHATKIT_AVAILABLE = True
except ImportError:
    PYWHATKIT_AVAILABLE = False


def send_whatsapp_message(mobile: str, message: str, wait_time: int = 30) -> dict:
    """
    Send a WhatsApp message via pywhatkit automation.

    Args:
        mobile: 10-digit Indian mobile number (without +91)
        message: Message text to send
        wait_time: Seconds to wait before sending (pywhatkit default)

    Returns:
        {"success": bool, "message": str}
    """
    if not PYWHATKIT_AVAILABLE:
        return {
            "success": False,
            "message": "pywhatkit not installed. Run: pip install pywhatkit pyautogui"
        }

    if len(mobile) != 10 or not mobile.isdigit():
        return {"success": False, "message": f"Invalid mobile number: {mobile}"}

    try:
        # pywhatkit.sendwhatmsg takes: phone_no (with +91), message, hour, minute
        # We schedule for 1 minute from now to give browser time to open
        now = datetime.now()
        send_hour = now.hour
        send_min = now.minute + 1

        if send_min >= 60:
            send_min -= 60
            send_hour = (send_hour + 1) % 24

        full_number = f"+91{mobile}"
        pywhatkit.sendwhatmsg(
            full_number,
            message,
            send_hour,
            send_min,
            wait_time=wait_time,
            tab_close=True,
        )

        return {
            "success": True,
            "message": f"WhatsApp message queued for {mobile}",
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"WhatsApp send failed: {str(e)}",
        }


# ─── Message Templates for WhatsApp ──────────────────────────────────────────

def get_whatsapp_template(msg_type: str, **kwargs) -> str:
    """
    Get a WhatsApp-optimized message template.
    Shorter than browser notifications — WhatsApp has display limits.

    Templates:
        - registration: "🏥 GIL CLINIC\n{name} आपका {test} टोकन #{token} मिल गया है।\nकृपया अपनी बारी का इंतज़ार करें।\nEstimated wait: {wait} min"
        - called: "🔵 {name} जी, कृपया {room} में आएं।\nआपका टोकन #{token} का नंबर आ गया है।"
        - completed: "✅ {name} जी, आपका {test} हो गया है।\nरिपोर्ट जल्द तैयार हो जाएगी।"
        - report_ready: "📋 {name} जी, आपकी {test} रिपोर्ट तैयार है।\nकृपया काउंटर से ले लें।"
    """
    templates = {
        "registration": (
            f"🏥 {kwargs.get('hospital', 'GIL CLINIC')}\n"
            f"{kwargs.get('name', '')} जी, आपका {kwargs.get('test', '')} "
            f"टोकन #{kwargs.get('token', '')} मिल गया है।\n"
            f"कृपया अपनी बारी का इंतज़ार करें।\n"
            f"Estimated wait: {kwargs.get('wait', '')} min"
        ),
        "called": (
            f"🔵 {kwargs.get('name', '')} जी, कृपया {kwargs.get('room', '')} में आएं।\n"
            f"आपका टोकन #{kwargs.get('token', '')} का नंबर आ गया है।"
        ),
        "completed": (
            f"✅ {kwargs.get('name', '')} जी, आपका {kwargs.get('test', '')} हो गया है।\n"
            f"रिपोर्ट जल्द तैयार हो जाएगी।"
        ),
        "report_ready": (
            f"📋 {kwargs.get('name', '')} जी, आपकी {kwargs.get('test', '')} "
            f"रिपोर्ट तैयार है।\nकृपया काउंटर से ले लें।"
        ),
    }

    return templates.get(msg_type, "")
