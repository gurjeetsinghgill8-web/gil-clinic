"""
Notification module — browser notifications for CardioQueue.
Provides helper functions to compose notification messages and HTML/JS injection
for browser-based Web Notification API alerts.
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


# ─── Browser Notification HTML Injection ─────────────────────────────────────

def browser_notification_script(title: str, body: str) -> str:
    """
    Returns a JavaScript snippet that triggers a browser notification.
    Injects into Streamlit via components.html or st.markdown with unsafe_allow_html.
    """
    # Escape single quotes for JS safety
    title_safe = title.replace("'", "\\'")
    body_safe = body.replace("'", "\\'").replace("\n", "\\n")

    return f"""
    <script>
    (function() {{
        if (!("Notification" in window)) {{
            console.log("Browser does not support notifications.");
            return;
        }}
        if (Notification.permission === "granted") {{
            new Notification('{title_safe}', {{
                body: '{body_safe}',
                icon: 'https://img.icons8.com/color/48/hospital.png'
            }});
        }} else if (Notification.permission !== "denied") {{
            Notification.requestPermission().then(function(permission) {{
                if (permission === "granted") {{
                    new Notification('{title_safe}', {{
                        body: '{body_safe}',
                        icon: 'https://img.icons8.com/color/48/hospital.png'
                    }});
                }}
            }});
        }}
    }})();
    </script>
    """


def request_notification_permission_script() -> str:
    """Returns JS that requests notification permission on page load."""
    return """
    <script>
    (function() {
        if ("Notification" in window && Notification.permission === "default") {
            Notification.requestPermission();
        }
    })();
    </script>
    """
