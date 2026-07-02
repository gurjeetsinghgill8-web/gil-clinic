"""
Patient PWA Dashboard — Self-Service Queue Tracker
====================================================
A mobile-first Progressive Web App dashboard for patients.

Features:
  - QR scan / URL param auto-load (?patient=XXX)
  - Live auto-refresh (5s) with pulse indicator
  - Browser notifications on status changes
  - Sound/vibration alert when called or report_ready
  - Full journey progress bar
  - "Add to Home Screen" PWA install prompt
  - Bilingual: Hindi + English

Architecture: Patient scans QR → opens this page with ?patient=ID
             → auto-loads patient data → refreshes every 5s
             → JS bridge detects status changes → Notification + Sound
"""
import streamlit as st
from datetime import datetime

from llm_harness import get_harness
from utils.config import (
    HOSPITAL_NAME, STATUS_ICONS, STATUS_LABELS, ROOM_NAMES, AVG_TEST_TIME, BASE_URL
)
from utils.queue import calculate_wait_time


# ─── PWA / META INJECTION ───────────────────────────────────────────────────────

def inject_pwa_meta():
    """Inject PWA manifest link, service worker registration, and install prompt JS."""
    return f"""
    <!-- PWA Manifest -->
    <link rel="manifest" href="/assets/manifest.json">
    <meta name="theme-color" content="#667eea">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="default">
    <meta name="apple-mobile-web-app-title" content="CardioQueue">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">

    <!-- Service Worker Registration -->
    <script>
    if ("serviceWorker" in navigator) {{
        navigator.serviceWorker.register("/assets/service-worker.js")
            .then(function() {{ console.log("[PWA] Service Worker registered"); }})
            .catch(function(err) {{ console.log("[PWA] SW registration failed:", err); }});
    }}

    // Add to Home Screen prompt handler
    window.addEventListener("beforeinstallprompt", function(e) {{
        e.preventDefault();
        window.deferredInstallPrompt = e;
        // Show install button after 3 seconds
        setTimeout(function() {{
            var btn = document.getElementById("install-pwa-btn");
            if (btn) btn.style.display = "block";
        }}, 3000);
    }});

    // Handle install button click
    function installPWA() {{
        var prompt = window.deferredInstallPrompt;
        if (prompt) {{
            prompt.prompt();
            prompt.userChoice.then(function(choice) {{
                if (choice.outcome === "accepted") {{
                    console.log("[PWA] User accepted install");
                }}
                window.deferredInstallPrompt = null;
                var btn = document.getElementById("install-pwa-btn");
                if (btn) btn.style.display = "none";
            }});
        }}
    }}
    </script>
    """


def get_pwa_install_button() -> str:
    """Return HTML for the PWA install button (hidden by default)."""
    return """
    <div id="install-pwa-btn" style="display: none; text-align: center; margin: 10px 0;">
        <button onclick="installPWA()" style="
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white; border: none; padding: 12px 24px;
            border-radius: 12px; font-size: 1rem; font-weight: 600;
            width: 100%; cursor: pointer; box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        ">
            📲 Add to Home Screen
        </button>
        <p style="font-size: 0.75rem; color: #888; margin-top: 6px;">
            Install for one-tap access & offline support
        </p>
    </div>
    """


# ─── STATUS CHANGE DETECTION JS ─────────────────────────────────────────────────

def get_status_watcher_js(prev_status_hash: str, patient_name: str) -> str:
    """
    Inject JavaScript that watches for status changes and triggers:
      - Browser Notification
      - Audio beep (via Web Audio API)
      - Vibration (on supported devices)
    """
    return f"""
    <script>
    (function() {{
        var prevHash = "{prev_status_hash}";
        var patientName = "{patient_name.replace("'", "\\'")}";

        function checkStatus() {{
            // Re-read the status element from the DOM
            var statusEl = document.getElementById("status-hash");
            if (!statusEl) return;
            var currHash = statusEl.getAttribute("data-hash") || "";
            var currStatus = statusEl.getAttribute("data-status") || "";
            var currTest = statusEl.getAttribute("data-test") || "";

            if (prevHash && currHash && currHash !== prevHash) {{
                // Status changed — notify patient
                var title = "🔄 Status Updated";
                var body = patientName + ", your status changed to: " + currStatus;

                // Browser Notification
                if ("Notification" in window && Notification.permission === "granted") {{
                    new Notification(title, {{
                        body: body,
                        icon: "https://img.icons8.com/color/48/hospital.png",
                        vibrate: [200, 100, 200]
                    }});
                }}

                // Audio alert via Web Audio API (no file needed)
                try {{
                    var ctx = new (window.AudioContext || window.webkitAudioContext)();
                    var osc = ctx.createOscillator();
                    var gain = ctx.createGain();
                    osc.connect(gain);
                    gain.connect(ctx.destination);
                    osc.frequency.value = 880;
                    osc.type = "sine";
                    gain.gain.value = 0.3;
                    osc.start();
                    osc.stop(ctx.currentTime + 0.3);
                }} catch(e) {{}}

                // Vibration
                if ("vibrate" in navigator) {{
                    navigator.vibrate([200, 100, 200, 100, 400]);
                }}

                prevHash = currHash;
            }}
        }}

        // Check every 3 seconds
        setInterval(checkStatus, 3000);
    }})();
    </script>
    """


# ─── MAIN PAGE ──────────────────────────────────────────────────────────────────

def show():
    harness = get_harness()
    today = datetime.now().strftime("%d-%b-%Y %I:%M %p")

    st.title("❤️ Cardio Department")
    st.caption(f"{HOSPITAL_NAME} — {today}")

    # ─── Inject PWA Meta & Service Worker ──────────────────────────────────
    st.markdown(inject_pwa_meta(), unsafe_allow_html=True)

    # ─── Auto-refresh every 5 seconds (live queue) ─────────────────────────
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=5000, key="patient_refresh")
    except ImportError:
        pass

    # ─── Detect patient from query param ───────────────────────────────────
    query_params = st.query_params
    patient_id_from_url = query_params.get("patient", None)
    if isinstance(patient_id_from_url, list):
        patient_id_from_url = patient_id_from_url[0] if patient_id_from_url else None

    # ─── Mobile Input OR auto-load from URL ────────────────────────────────
    if patient_id_from_url:
        # Auto-loaded from QR scan — no mobile input needed
        result = harness.get_patient_details(patient_id_from_url, by_mobile=False)
        auto_loaded = True
    else:
        result = None
        auto_loaded = False

    # Show manual input only when not auto-loaded
    if not auto_loaded:
        st.markdown("### 🔍 अपना स्टेटस देखें / Check Your Status")
        st.markdown(
            "अपना रजिस्टर्ड मोबाइल नंबर डालें — Enter your registered mobile number"
        )

        # Initialize session state for search
        if "ps_result" not in st.session_state:
            st.session_state.ps_result = None
        if "ps_mobile" not in st.session_state:
            st.session_state.ps_mobile = ""

        mobile = st.text_input(
            "📱 Mobile Number",
            placeholder="10-digit mobile number — auto-searches on typing",
            max_chars=10,
            key="patient_mobile",
        )

        # Auto-search when 10 digits entered
        if mobile and len(mobile) == 10 and mobile.isdigit():
            if mobile != st.session_state.ps_mobile:
                st.session_state.ps_mobile = mobile
                res = harness.get_patient_status(mobile)
                if res and res.get("found"):
                    st.session_state.ps_result = res
                    st.rerun()
                else:
                    st.warning("⚠️ इस नंबर पर कोई मरीज़ नहीं मिला / No patient found with this number")
                    st.session_state.ps_result = None

        # Fallback button
        search_clicked = st.button("🔍 Check Status", type="primary", use_container_width=True)

        if search_clicked:
            if not mobile or len(mobile) != 10 or not mobile.isdigit():
                st.warning("⚠️ कृपया सही 10 अंकों का मोबाइल नंबर डालें")
                return
            res = harness.get_patient_status(mobile)
            if res and res.get("found"):
                st.session_state.ps_result = res
                st.session_state.ps_mobile = mobile
                st.rerun()
            else:
                st.warning("⚠️ इस नंबर पर कोई मरीज़ नहीं मिला / No patient found with this number")
                st.session_state.ps_result = None

        # Manual entry instructions
        st.markdown("---")
        st.markdown(
            "📸 **QR Code मिला?** रिसेप्शन से QR Code स्कैन करें → "
            "अपना मोबाइल नंबर डालें → स्टेटस अपने आप दिख जाएगा।"
        )

        # If we have a result from auto-search, use it
        if st.session_state.ps_result:
            result = st.session_state.ps_result
        else:
            return

    # ─── Handle result ────────────────────────────────────────────────────────
    if not result or not result["found"]:
        st.error("❌ Patient not found. Please scan the QR code again or check with reception.")
        st.markdown(
            f"[🔄 Scan QR at Reception]({BASE_URL}/)",
            unsafe_allow_html=True,
        )
        return

    patient = result["patient"]
    tests = result["tests"]

    # Build a status hash for the JS watcher
    status_hash = "|".join(f"{t['test_name']}:{t['status']}" for t in tests)
    all_statuses = [t["status"] for t in tests]
    primary_status = all_statuses[0] if all_statuses else "waiting"
    primary_test = tests[0]["test_name"] if tests else ""

    # ─── Hidden element for JS status watcher ──────────────────────────────
    st.markdown(
        f'<div id="status-hash" data-hash="{status_hash}" '
        f'data-status="{STATUS_LABELS.get(primary_status, primary_status)}" '
        f'data-test="{primary_test}" style="display:none;"></div>',
        unsafe_allow_html=True,
    )

    # ─── PWA Install Button ────────────────────────────────────────────────
    st.markdown(get_pwa_install_button(), unsafe_allow_html=True)

    # ─── Patient Info Card ─────────────────────────────────────────────────
    with st.container(border=True):
        cols = st.columns([2, 1])
        with cols[0]:
            st.markdown(f"### 👤 {patient['name']}")
            st.markdown(f"🆔 `{patient['patient_id']}`")
        with cols[1]:
            st.markdown(f"### {STATUS_ICONS.get(primary_status, '❓')}")
            st.markdown(f"**{STATUS_LABELS.get(primary_status, primary_status)}**")

    # ─── Live Queue Pulse Indicator ────────────────────────────────────────
    st.markdown(
        """
        <div style="text-align: center; padding: 6px; margin: 8px 0;">
            <span style="display: inline-block; width: 10px; height: 10px;
                  background: #4CAF50; border-radius: 50%;
                  animation: pulse 2s infinite; margin-right: 8px;"></span>
            <span style="color: #666; font-size: 0.85rem;">
                Live — Auto-updating every 5 seconds
            </span>
        </div>
        <style>
        @keyframes pulse {
            0% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.5; transform: scale(1.3); }
            100% { opacity: 1; transform: scale(1); }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ─── Test Status Cards ─────────────────────────────────────────────────
    st.divider()
    st.markdown("### 📋 आपके टेस्ट / Your Tests")

    if not tests:
        st.info("📭 No tests registered yet.")
        return

    # Calculate overall progress
    status_order = ["waiting", "called", "in_progress", "completed", "report_ready", "delivered"]
    max_progress = 0
    for t in tests:
        try:
            idx = status_order.index(t["status"])
            max_progress = max(max_progress, (idx + 1) / len(status_order))
        except ValueError:
            pass

    # ─── Overall Progress Bar ──────────────────────────────────────────────
    st.markdown("**Overall Progress**")
    st.progress(max_progress, text=f"{int(max_progress * 100)}%")

    for test in tests:
        test_name = test["test_name"]
        status = test["status"]
        token = test.get("token_number", 0)
        room = ROOM_NAMES.get(test_name, f"{test_name} Room")
        wait_time = calculate_wait_time(test_name, test.get("queue_position", 0))
        pos = test.get("queue_position", 0)

        # Color mapping
        border_color = {
            "waiting": "#FFA500",
            "called": "#2196F3",
            "in_progress": "#FF9800",
            "completed": "#4CAF50",
            "report_ready": "#9C27B0",
            "delivered": "#607D8B",
        }.get(status, "#E0E0E0")

        with st.container(border=True):
            col1, col2 = st.columns([3, 1])

            with col1:
                st.markdown(f"### {test_name}")
                st.caption(f"🏠 {room} | 🎫 Token #{token}")

                # Status with icon
                icon = STATUS_ICONS.get(status, "❓")
                label = STATUS_LABELS.get(status, status.replace("_", " ").title())
                st.markdown(f"**{icon} {label}**")

            with col2:
                # Time / Position info
                if status in ["waiting", "called"]:
                    st.markdown(f"### ⏱️")
                    st.markdown(f"**~{wait_time} min**")
                    if pos:
                        st.caption(f"Position: #{pos}")
                elif status == "in_progress":
                    st.markdown(f"### 🔄")
                    st.markdown("**In Progress...**")
                elif status == "completed":
                    st.markdown(f"### ✅")
                    st.markdown("**Done**")
                elif status == "report_ready":
                    st.markdown(f"### 📋")
                    st.markdown("**Collect at Counter**")
                elif status == "delivered":
                    st.markdown(f"### 📄")
                    st.markdown("**Delivered**")

            # Individual progress for this test
            try:
                idx = status_order.index(status)
                test_progress = (idx + 1) / len(status_order)
            except ValueError:
                test_progress = 0
            st.progress(test_progress, text=f"{test_name}: {int(test_progress * 100)}%")

    # ─── Summary Section ───────────────────────────────────────────────────
    st.divider()
    st.markdown("### 📊 सारांश / Summary")

    all_completed = all(t["status"] in ["completed", "report_ready", "delivered"] for t in tests)
    any_in_progress = any(t["status"] == "in_progress" for t in tests)
    any_called = any(t["status"] == "called" for t in tests)

    if all_completed:
        st.success("🎉 सभी टेस्ट पूरे हो गए! कृपया काउंटर से रिपोर्ट लें।\n\nAll tests complete! Please collect reports from reception.")
    elif any_in_progress:
        st.info("🔄 कुछ टेस्ट चल रहे हैं। कृपया प्रतीक्षा करें।\n\nSome tests are in progress. Please wait.")
    elif any_called:
        st.info("🔵 आपको बुलाया गया है! कृपया संबंधित कमरे में जाएं।\n\nYou've been called! Please proceed to the test room.")
    else:
        max_wait = max((calculate_wait_time(t["test_name"], t.get("queue_position", 0)) for t in tests), default=0)
        st.info(f"⏳ अनुमानित प्रतीक्षा: ~{max_wait} मिनट\n\nEstimated wait: ~{max_wait} minutes")

    st.caption(
        "⚠️ Wait times are estimates only. Actual times may vary based on department workload."
    )

    # ─── Inject Status Watcher JS ──────────────────────────────────────────
    st.markdown(
        get_status_watcher_js(status_hash, patient["name"]),
        unsafe_allow_html=True,
    )

    # ─── Footer with QR re-scan option ─────────────────────────────────────
    st.divider()
    qr_data = harness.generate_qr_code_base64(patient["patient_id"])
    if qr_data:
        with st.expander("📱 अपना QR Code देखें / View Your QR Code"):
            st.markdown(
                f"""
                <div style="text-align: center; padding: 10px;">
                    <img src="{qr_data}" style="width: 150px; height: 150px;
                         border: 2px solid #e0e0e0; border-radius: 12px; padding: 8px;
                         background: white;" alt="QR Code">
                    <p style="font-size: 0.8rem; color: #666; margin-top: 8px;">
                        Scan to re-open this dashboard
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
