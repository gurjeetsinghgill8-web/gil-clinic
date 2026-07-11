# WhatsApp Integration (legacy — use utils/whatsapp_upgrade.py for Meta Cloud API)
"""
WhatsApp Notification Module — Phase 2
========================================
Free notification system using pywhatkit + WhatsApp Web automation.
Queue-based background delivery to avoid freezing Streamlit UI and resolve pyautogui conflicts.
"""
import queue
import threading
import time
from datetime import datetime

# Optional import — will only work when pywhatkit is installed
try:
    import pywhatkit
    PYWHATKIT_AVAILABLE = True
except ImportError:
    PYWHATKIT_AVAILABLE = False


# Thread-safe queue for sequential WhatsApp message sending
_whatsapp_queue = queue.Queue()


def _whatsapp_worker():
    """Background worker thread that processes the message queue sequentially."""
    if not PYWHATKIT_AVAILABLE:
        print("[WhatsApp Worker] pywhatkit not available. Background worker inactive.")
        return

    print("[WhatsApp Worker] Background worker thread started.")
    while True:
        try:
            # Block until an item is available
            task = _whatsapp_queue.get()
            if task is None:
                break
            
            mobile, message = task
            print(f"[WhatsApp Worker] Sending message to {mobile}...")
            
            # Use sendwhatmsg_instantly which takes wait_time (time to wait before hitting send)
            # and tab_close (automatically closes the opened chrome tab)
            # We wait 15 seconds for WhatsApp Web to load, and then close the tab after 3 seconds.
            full_number = f"+91{mobile}"
            pywhatkit.sendwhatmsg_instantly(
                phone_no=full_number,
                message=message,
                wait_time=15,
                tab_close=True,
                close_time=3
            )
            print(f"[WhatsApp Worker] Message successfully sent to {mobile}.")
            
            # Delay to allow clean browser closure and prevent overlap
            time.sleep(3)
        except Exception as e:
            print(f"[WhatsApp Worker] Failed to send message to {mobile}: {e}")
        finally:
            _whatsapp_queue.task_done()


# Start background worker thread
if PYWHATKIT_AVAILABLE:
    _worker_thread = threading.Thread(target=_whatsapp_worker, daemon=True)
    _worker_thread.start()


def send_whatsapp_message(mobile: str, message: str) -> dict:
    """
    Queue a WhatsApp message for non-blocking asynchronous delivery.
    """
    if not PYWHATKIT_AVAILABLE:
        return {
            "success": False,
            "message": "pywhatkit not installed. Run: pip install pywhatkit pyautogui"
        }

    if not mobile or len(mobile) != 10 or not mobile.isdigit():
        return {"success": False, "message": f"Invalid mobile number: {mobile}"}

    try:
        # Enqueue the message task
        _whatsapp_queue.put((mobile, message))
        return {
            "success": True,
            "message": f"Message queued for {mobile} in the background worker."
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to queue message: {str(e)}"
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
            f"🏥 *{kwargs.get('hospital', 'GIL CLINIC')}*\n"
            f"{kwargs.get('name', '')} जी, आपका *{kwargs.get('test', '')}* का "
            f"रजिस्ट्रेशन हो गया है।\n"
            f"टोकन संख्या: *#{kwargs.get('token', '')}*\n"
            f"कृपया अपनी बारी का इंतज़ार करें।\n"
            f"अनुमानित समय: ~{kwargs.get('wait', '')} मिनट"
        ),
        "called": (
            f"🔵 *{kwargs.get('hospital', 'GIL CLINIC')}*\n"
            f"{kwargs.get('name', '')} जी, कृपया *{kwargs.get('room', '')}* (कमरा नंबर) में आएं।\n"
            f"आपका टोकन *#{kwargs.get('token', '')}* आ गया है।"
        ),
        "completed": (
            f"✅ *{kwargs.get('hospital', 'GIL CLINIC')}*\n"
            f"{kwargs.get('name', '')} जी, आपका *{kwargs.get('test', '')}* टेस्ट पूरा हो गया है।\n"
            f"रिपोर्ट जल्द ही तैयार हो जाएगी।"
        ),
        "report_ready": (
            f"📋 *{kwargs.get('hospital', 'GIL CLINIC')}*\n"
            f"{kwargs.get('name', '')} जी, आपकी *{kwargs.get('test', '')}* "
            f"रिपोर्ट तैयार है।\n"
            f"कृपया काउंटर से अपनी रिपोर्ट प्राप्त करें।"
        ),
    }

    return templates.get(msg_type, "")
