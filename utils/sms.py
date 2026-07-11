"""
SMS Notification Module — Twilio Integration
=============================================
Sends SMS alerts to patients and staff via Twilio API.
Queue-based background delivery to avoid freezing Streamlit UI.

Configuration (via .env or config):
    TWILIO_ACCOUNT_SID  — Twilio account SID
    TWILIO_AUTH_TOKEN   — Twilio auth token
    TWILIO_FROM_NUMBER  — Twilio phone number (e.g. +1234567890)
    SMS_ENABLED         — Set to "true" to enable SMS sending

Usage:
    from utils.sms import send_sms_message
    result = send_sms_message("9876543210", "Hello from GIL CLINIC")
"""
import os
import queue
import threading
import time
from datetime import datetime

# ─── Twilio optional import ───────────────────────────────────────────────────
try:
    from twilio.rest import Client
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False

# ─── Config ───────────────────────────────────────────────────────────────────
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "")
SMS_ENABLED = os.getenv("SMS_ENABLED", "false").lower() == "true"

# Track whether we've warned about missing config once
_warned = False

# Thread-safe queue for sequential SMS sending
_sms_queue = queue.Queue()


def _sms_worker():
    """Background worker thread that processes the message queue sequentially."""
    if not TWILIO_AVAILABLE:
        print("[SMS Worker] Twilio not installed. SMS inactive.")
        return

    global _warned
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_FROM_NUMBER:
        if not _warned:
            print("[SMS Worker] Twilio credentials not configured. SMS inactive.")
            _warned = True
        return

    print("[SMS Worker] Background worker thread started.")
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    except Exception as e:
        print(f"[SMS Worker] Failed to create Twilio client: {e}")
        return

    while True:
        try:
            task = _sms_queue.get()
            if task is None:
                break

            mobile, message_text = task

            # Format mobile: ensure +91 prefix for Indian numbers
            to_number = mobile
            if not to_number.startswith("+"):
                if len(mobile) == 10 and mobile.isdigit():
                    to_number = f"+91{mobile}"
                else:
                    to_number = f"+{mobile}"

            print(f"[SMS Worker] Sending SMS to {to_number}...")
            try:
                sms = client.messages.create(
                    body=message_text,
                    from_=TWILIO_FROM_NUMBER,
                    to=to_number
                )
                print(f"[SMS Worker] ✅ Sent to {to_number} (SID: {sms.sid})")
            except Exception as e:
                print(f"[SMS Worker] ❌ Failed to send to {to_number}: {e}")

            # Rate-limit: Twilio allows ~1 msg/sec with standard account
            time.sleep(1.5)

        except Exception as e:
            print(f"[SMS Worker] Error: {e}")
        finally:
            _sms_queue.task_done()


# Start background worker thread (if Twilio is available and configured)
if TWILIO_AVAILABLE and TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER:
    _worker_thread = threading.Thread(target=_sms_worker, daemon=True)
    _worker_thread.start()


def send_sms_message(mobile: str, message: str) -> dict:
    """
    Queue an SMS message for non-blocking asynchronous delivery.

    Args:
        mobile: 10-digit Indian mobile number
        message: Plain-text SMS content

    Returns:
        dict with "success" bool and "message" string
    """
    if not SMS_ENABLED:
        return {
            "success": False,
            "message": "SMS is disabled. Set SMS_ENABLED=true in .env to enable."
        }

    if not TWILIO_AVAILABLE:
        return {
            "success": False,
            "message": "Twilio not installed. Run: pip install twilio"
        }

    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_FROM_NUMBER:
        return {
            "success": False,
            "message": "Twilio credentials not configured. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_FROM_NUMBER in .env"
        }

    if not mobile or not message:
        return {"success": False, "message": "Mobile number and message are required."}

    if len(mobile) != 10 or not mobile.isdigit():
        return {"success": False, "message": f"Invalid mobile number: {mobile}. Must be 10 digits."}

    try:
        _sms_queue.put((mobile, message))
        return {
            "success": True,
            "message": f"SMS queued for {mobile} in the background worker."
        }
    except Exception as e:
        return {"success": False, "message": f"Failed to queue SMS: {str(e)}"}


# ─── SMS Message Templates ────────────────────────────────────────────────────
# SMS has 160-char limit per segment. These templates are kept concise.

def get_sms_template(msg_type: str, **kwargs) -> str:
    """
    Get an SMS-optimized message template.

    Templates (all under 160 chars):
        - registration: "GIL CLINIC: {name}, your {test} token #{token} confirmed. Wait time ~{wait} min. Track: {url}"
        - called: "GIL CLINIC: {name}, please come to {room}. Token #{token} is now being served."
        - completed: "GIL CLINIC: {name}, your {test} is done. Report will be ready shortly."
        - report_ready: "GIL CLINIC: {name}, your {test} report is ready. Please collect from counter."
        - reminder: "GIL CLINIC: {name}, your turn is coming soon! Please be ready at the department."
    """
    hospital = kwargs.get("hospital", "GIL CLINIC")
    name = kwargs.get("name", "")
    test = kwargs.get("test", "")
    token = kwargs.get("token", "")
    room = kwargs.get("room", "")
    wait = kwargs.get("wait", "")
    url = kwargs.get("url", "")

    templates = {
        "registration": (
            f"{hospital}: {name}, your {test} token #{token} confirmed. "
            f"Wait time ~{wait} min. Track: {url}" if url
            else f"{hospital}: {name}, your {test} token #{token} confirmed. Please wait."
        ),
        "called": (
            f"{hospital}: {name}, please come to {room}. "
            f"Token #{token} is now being served."
        ),
        "completed": (
            f"{hospital}: {name}, your {test} is done. "
            f"Report will be ready shortly."
        ),
        "report_ready": (
            f"{hospital}: {name}, your {test} report is ready. "
            f"Please collect from counter."
        ),
        "reminder": (
            f"{hospital}: {name}, your turn is coming soon! "
            f"Please be ready at the department."
        ),
    }

    return templates.get(msg_type, "")


def format_indian_mobile(mobile: str) -> str:
    """Ensure mobile starts with +91 for Indian numbers."""
    if mobile.startswith("+"):
        return mobile
    if len(mobile) == 10 and mobile.isdigit():
        return f"+91{mobile}"
    return mobile
