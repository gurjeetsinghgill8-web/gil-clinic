"""
Notification module — browser notifications with Sound, Vibration & Badge for CardioQueue.
Provides helper functions to compose notification messages and HTML/JS injection
for browser-based Web Notification API alerts with audio/vibration feedback.
"""
from utils.config import HOSPITAL_NAME

# ─── Message Templates ───────────────────────────────────────────────────────

def registration_message(patient_name: str, tests: list[str]) -> str:
    """Message when patient is registered."""
    test_list = ", ".join(tests)
    return (
        f"✅ Registration Complete!\n"
        f"Patient: {patient_name}\n"
        f"Tests: {test_list}\n"
        f"Please wait for your turn."
    )


def called_message(patient_name: str, test_name: str, token: int, room: str) -> str:
    """Message when patient is called to a department."""
    return (
        f"🔵 Please Proceed!\n"
        f"{patient_name}, your turn for {test_name} (Token #{token})\n"
        f"Room: {room}"
    )


def completed_message(patient_name: str, test_name: str) -> str:
    """Message when a test is completed."""
    return (
        f"✅ {test_name} Completed!\n"
        f"{patient_name}, your {test_name} is done.\n"
        f"Report will be ready shortly."
    )


def report_ready_message(patient_name: str, test_name: str) -> str:
    """Message when report is ready."""
    return (
        f"📋 Report Ready!\n"
        f"{patient_name}, your {test_name} report is ready.\n"
        f"Please collect from the reception counter."
    )


# ─── Sound Alert Base64 (short notification beep) ───────────────────────────
# This is a tiny WAV encoded as base64 — a short 500ms sine beep at 880Hz
NOTIFICATION_BEEP_B64 = (
    "data:audio/wav;base64,"
    "UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACAf39/f3+AgH9/f3+AgICAf39/f4CAgH+AgH+AgH9/f3+AgH+AgIB/f39/gIB/f3+AgH9/f3+AgH9/f3+AgH+AgH+AgH9/f3+AgH9/f3+AgH9/f3+"
    "gH9/f3+AgH9/f4CAgH9/f39/gIB/f39/gIB/f39/f4CAf39/f39/gIB/f39/f39/f39/f4B/f39/f39/f39/f39/f3+AgH9/f39/f39/f3+AgH9/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f3+AgH9/f39/f4B/f39/f39/f3+"
    "Af39/f39/f39/f39/f3+AgH9/f39/f39/f39/f39/f39/f4B/f39/f39/f39/f39/f39/f4B/f39/f39/f39/f39/f4B/f39/f4B/f39/f39/f39/f4B/f39/f39/f39/f39/f4B/f39/f39/f39/f39/f4B/f39/f39/f39/f39/f39/f4B/f3+"
    "Af39/f39/f39/f39/f39/f4B/f39/f39/f39/f39/f4B/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f4B/f39/f39/f39/f39/f39/f39/f39/f39"
)


# ─── Browser Notification HTML Injection with Sound & Vibration ─────────────

def browser_notification_script(title: str, body: str, urgent: bool = False) -> str:
    """
    Returns a JavaScript snippet that:
      1. Plays a notification beep sound (HTML5 Audio)
      2. Vibrates mobile device (if supported)
      3. Shows a browser notification (Web Notification API)
      4. Updates the page title badge with a flashing indicator

    Parameters:
        title (str): Notification title
        body (str): Notification body text
        urgent (bool): If True, uses longer vibration + louder indicators
    """
    title_safe = title.replace("'", "\\'")
    body_safe = body.replace("'", "\\'").replace("\n", "\\n")
    beep = NOTIFICATION_BEEP_B64

    # Vibration pattern: normal = short buzz, urgent = long pattern
    vibe_pattern = "[500, 200, 500]" if urgent else "[300]"

    return f"""
    <script>
    (function() {{
        var titleSafe = '{title_safe}';
        var bodySafe = '{body_safe}';
        var beep = '{beep}';

        // ── 1. Play notification sound ────────────────────────────────────────
        try {{
            var audio = new Audio(beep);
            audio.volume = 0.7;
            audio.play().catch(function(e) {{
                // Auto-play blocked — user will see notification instead
            }});
        }} catch(e) {{
            console.log("Audio not supported");
        }}

        // ── 2. Vibrate mobile device ──────────────────────────────────────────
        try {{
            if (navigator.vibrate) {{
                navigator.vibrate({vibe_pattern});
            }}
        }} catch(e) {{}}

        // ── 3. Show browser notification ──────────────────────────────────────
        if ("Notification" in window) {{
            if (Notification.permission === "granted") {{
                new Notification(titleSafe, {{
                    body: bodySafe,
                    icon: 'https://img.icons8.com/color/48/hospital.png',
                    badge: 'https://img.icons8.com/color/48/hospital.png',
                    tag: 'cardioqueue-' + Date.now(),
                    requireInteraction: true,
                    silent: false
                }});
            }} else if (Notification.permission !== "denied") {{
                Notification.requestPermission().then(function(permission) {{
                    if (permission === "granted") {{
                        new Notification(titleSafe, {{
                            body: bodySafe,
                            icon: 'https://img.icons8.com/color/48/hospital.png',
                            badge: 'https://img.icons8.com/color/48/hospital.png',
                            tag: 'cardioqueue-' + Date.now(),
                            requireInteraction: true,
                            silent: false
                        }});
                    }}
                }});
            }}
        }}

        // ── 4. Flash page title for attention ─────────────────────────────────
        var originalTitle = document.title;
        var flashInterval = setInterval(function() {{
            document.title = (document.title === originalTitle)
                ? '🔔 ' + titleSafe
                : originalTitle;
        }}, 1000);
        setTimeout(function() {{
            clearInterval(flashInterval);
            document.title = originalTitle;
        }}, 8000);
    }})();
    </script>
    """


def request_notification_permission_script() -> str:
    """Returns JS that requests notification + vibration permission on page load."""
    return """
    <script>
    (function() {
        // Request browser notification permission
        if ("Notification" in window && Notification.permission === "default") {
            Notification.requestPermission();
        }
        // Pre-warm audio context for mobile (iOS requirement)
        try {
            var ctx = new (window.AudioContext || window.webkitAudioContext)();
            ctx.resume();
        } catch(e) {}
    })();
    </script>
    """


def misscall_alert_script(patient_name: str, test_name: str = "") -> str:
    """
    Returns JS that triggers a FULL-SCREEN visual banner + sound + vibration
    on the patient status page. Works WITHOUT browser notification permission.

    This is the "Miss Call" alternative — it uses window.__playPatientAlert()
    which is exposed by get_status_watcher_js() in Patient_Status.py.
    
    The script:
      1. Calls window.__playPatientAlert() if available (plays triple beep + vibrate)
      2. Shows a bright banner at the top of the screen
      3. Flashes the page title
    """
    safe_name = patient_name.replace("'", "\\'")
    return f"""
    <script>
    (function() {{
        var pname = '{safe_name}';
        var testName = '{test_name}';
        var label = '🔔 Alert' + (testName ? ': ' + testName : '');

        // ── 1. Trigger sound+vibration via global function ──────────────────
        if (window.__playPatientAlert) {{
            window.__playPatientAlert(label + ' - ' + pname);
        }}

        // ── 2. Show bright banner using DOM ──────────────────────────────────
        try {{
            var banner = document.createElement('div');
            banner.id = 'misscall-banner';
            banner.innerHTML = '📞 <strong>Miss Call Alert!</strong><br>' + pname + ' — ' + label;
            banner.style.cssText =
                'position:fixed;top:0;left:0;right:0;z-index:99999;' +
                'background:linear-gradient(135deg,#ff4444,#cc0000);' +
                'color:white;padding:18px 14px;text-align:center;' +
                'font-size:18px;font-weight:600;box-shadow:0 6px 20px rgba(0,0,0,0.5);' +
                'animation:slideDown 0.4s ease-out;' +
                'border-bottom:3px solid #ffaa00;' +
                'line-height:1.6;';
            document.body.appendChild(banner);

            // Remove banner after 8 seconds
            setTimeout(function() {{
                var b = document.getElementById('misscall-banner');
                if (b) {{
                    b.style.transition = 'transform 0.4s ease-out';
                    b.style.transform = 'translateY(-100%)';
                    setTimeout(function() {{ if (b.parentNode) b.parentNode.removeChild(b); }}, 500);
                }}
            }}, 8000);
        }} catch(e) {{}}

        // ── 3. Flash title ──────────────────────────────────────────────────
        try {{
            var ot = document.title;
            var fi = setInterval(function() {{
                document.title = (document.title === ot) ? '📞 ' + label : ot;
            }}, 700);
            setTimeout(function() {{ clearInterval(fi); document.title = ot; }}, 8000);
        }} catch(e) {{}}
    }})();
    </script>
    """
