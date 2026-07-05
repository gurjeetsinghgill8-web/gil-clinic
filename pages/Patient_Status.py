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

    <!-- Service Worker Registration + Notif Perm + Audio Warmup -->
    <script>
    if ("serviceWorker" in navigator) {{
        navigator.serviceWorker.register("/assets/service-worker.js")
            .then(function() {{ console.log("[PWA] Service Worker registered"); }})
            .catch(function(err) {{ console.log("[PWA] SW registration failed:", err); }});
    }}

    // Request notification permission on first visit
    if ("Notification" in window && Notification.permission === "default") {{
        Notification.requestPermission();
    }}

    // ─── Mobile Audio: Touch-to-Enable ──────────────────────────────────
    // Mobile browsers block AudioContext until user gesture.
    // Create one global AudioContext and resume on first touch.
    window.__audioCtx = null;
    function getAudioCtx() {{
        if (!window.__audioCtx) {{
            try {{
                window.__audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            }} catch(e) {{ return null; }}
        }}
        if (window.__audioCtx.state === "suspended") {{
            window.__audioCtx.resume();
        }}
        return window.__audioCtx;
    }}
    // Resume on first ANY touch/click on the page
    document.addEventListener("touchstart", function() {{ getAudioCtx(); }}, {{ once: true }});
    document.addEventListener("click", function() {{ getAudioCtx(); }}, {{ once: true }});
    // Also try immediate resume (works on some browsers)
    setTimeout(function() {{ try {{ getAudioCtx(); }} catch(e) {{}} }}, 100);

    // Display a "Tap to enable sound" hint for 5 seconds on mobile
    (function() {{
        var isMobile = /android|iphone|ipad|ipod/i.test(navigator.userAgent);
        if (!isMobile) return;
        var hint = document.createElement("div");
        hint.id = "sound-hint";
        hint.innerHTML = "🔊 Tap screen to enable sound alerts";
        hint.style.cssText = "position:fixed;bottom:80px;left:50%;transform:translateX(-50%);background:#667eea;color:#fff;padding:10px 20px;border-radius:25px;font-size:14px;z-index:9999;opacity:0.9;box-shadow:0 4px 15px rgba(0,0,0,0.3);text-align:center;max-width:90%;animation:fadeIn 0.5s;";
        document.body.appendChild(hint);
        setTimeout(function() {{
            var h = document.getElementById("sound-hint");
            if (h) h.style.display = "none";
        }}, 5000);
    }})();

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

def get_status_watcher_js(prev_status_hash: str, patient_name: str, patient_id: str = "") -> str:
    """
    Inject JavaScript that watches for status changes and triggers:
      - Sound (Web Audio API — double beep)
      - Vibration (long pattern)
      - Browser Notification (if permission granted)
      - Service Worker background tracking

    Uses sessionStorage so hash survives Streamlit reruns/auto-refresh.
    On every page load, compares current hash with stored hash → triggers alert if changed.
    Also exposes window.__playPatientAlert(status) so staff can trigger remotely via server.
    """
    safe_name = patient_name.replace("'", "\\'").replace('"', '\\"')
    return f"""
    <script>
    (function() {{
        var PID = "{patient_id}";
        var PNAME = "{safe_name}";
        var HASH = "{prev_status_hash}";
        var STORAGE_KEY = "cq_h_" + PID;

        // ─── Helper: play beep on shared AudioContext ────────────────────────
        function playBeep(freq, duration, gainVal, delay) {{
            setTimeout(function() {{
                try {{
                    var ctx = getAudioCtx();
                    if (!ctx) return;
                    var osc = ctx.createOscillator();
                    var g = ctx.createGain();
                    osc.connect(g); g.connect(ctx.destination);
                    osc.frequency.value = freq;
                    osc.type = "sine";
                    g.gain.value = gainVal;
                    osc.start();
                    osc.stop(ctx.currentTime + duration);
                }} catch(e) {{}}
            }}, delay || 0);
        }}

        // ─── Global alert function — can be called from anywhere ──────────────
        window.__playPatientAlert = function(statusLabel) {{
            // Sound — triple beep pattern using shared AudioContext
            playBeep(880, 0.5, 0.6, 0);
            playBeep(660, 0.4, 0.5, 250);
            playBeep(1000, 0.6, 0.5, 500);

            // Vibration — long pattern
            try {{ if (navigator.vibrate) navigator.vibrate([500, 200, 500, 200, 700]); }} catch(e) {{}}

            // Browser Notification
            if ("Notification" in window && Notification.permission === "granted") {{
                try {{
                    new Notification("🔔 " + PNAME, {{
                        body: "Status: " + statusLabel,
                        icon: "https://img.icons8.com/color/48/hospital.png",
                        tag: "cq-" + Date.now(),
                        requireInteraction: true,
                        silent: false,
                        vibrate: [500, 200, 500, 200, 700]
                    }});
                }} catch(e) {{}}
            }}

            // Flash page title
            try {{
                var ot = document.title;
                var fi = setInterval(function() {{ document.title = (document.title === ot) ? "🔔 " + statusLabel : ot; }}, 700);
                setTimeout(function() {{ clearInterval(fi); document.title = ot; }}, 6000);
            }} catch(e) {{}}
        }};

        // ─── 1. Compare with stored hash → alert on change ────────────────────
        var oldHash = sessionStorage.getItem(STORAGE_KEY);
        var justChanged = (oldHash && oldHash !== HASH);
        sessionStorage.setItem(STORAGE_KEY, HASH);

        if (justChanged) {{
            var el = document.getElementById("status-hash");
            var st = el ? el.getAttribute("data-status") || "Updated" : "Updated";
            window.__playPatientAlert(st);
        }}

        // ─── 2. Register Service Worker for background tracking ────────────────
        if ("serviceWorker" in navigator) {{
            navigator.serviceWorker.ready.then(function(reg) {{
                if (reg.active) {{
                    reg.active.postMessage({{
                        type: "TRACK_PATIENT",
                        patientId: PID,
                        patientName: PNAME,
                        statusHash: HASH
                    }});
                }}
            }});
        }}

        // ─── 3. Poll every 3 sec for DOM changes (st_autorefresh updates) ──────
        setInterval(function() {{
            var el = document.getElementById("status-hash");
            if (!el) return;
            var nh = el.getAttribute("data-hash") || "";
            var ns = el.getAttribute("data-status") || "";
            var oh = sessionStorage.getItem(STORAGE_KEY) || "";
            if (oh && nh && oh !== nh) {{
                sessionStorage.setItem(STORAGE_KEY, nh);
                // Sound + vibration (using shared AudioContext)
                try {{
                    var ctx = getAudioCtx();
                    if (ctx) {{
                        var o = ctx.createOscillator();
                        var g = ctx.createGain();
                        o.connect(g); g.connect(ctx.destination);
                        o.frequency.value = 880;
                        o.type = "sine";
                        g.gain.value = 0.6;
                        o.start();
                        o.stop(ctx.currentTime + 0.5);
                    }}
                try {{ if (navigator.vibrate) navigator.vibrate([500, 200, 500]); }} catch(e) {{}}
                if ("Notification" in window && Notification.permission === "granted") {{
                    try {{
                        new Notification("🔔 " + PNAME, {{
                            body: "Status: " + ns,
                            icon: "https://img.icons8.com/color/48/hospital.png",
                            tag: "cq-" + Date.now(),
                            requireInteraction: true,
                            silent: false,
                            vibrate: [500, 200, 500]
                        }});
                    }} catch(e) {{}}
                }}
                if ("serviceWorker" in navigator) {{
                    navigator.serviceWorker.ready.then(function(reg) {{
                        if (reg.active) reg.active.postMessage({{ type: "UPDATE_STATUS_HASH", statusHash: nh }});
                    }});
                }}
            }}
        }}, 3000);
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
    mobile_from_url = query_params.get("mobile", None)
    if isinstance(patient_id_from_url, list):
        patient_id_from_url = patient_id_from_url[0] if patient_id_from_url else None
    if isinstance(mobile_from_url, list):
        mobile_from_url = mobile_from_url[0] if mobile_from_url else None

    # ─── Mobile Input OR auto-load from URL ────────────────────────────────
    result = None
    auto_loaded = False

    if patient_id_from_url and patient_id_from_url != "common":
        # Auto-loaded from per-patient QR scan — no mobile input needed
        result = harness.get_patient_details(patient_id_from_url, by_mobile=False)
        auto_loaded = True
    elif mobile_from_url:
        # Auto-loaded from mobile param (PWA redirect)
        result = harness.get_patient_status(mobile_from_url)
        auto_loaded = True

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

    # ─── Education Messages Section ──────────────────────────────────────────
    st.divider()
    st.markdown("### 📚 स्वास्थ्य शिक्षा / Health Education")
    st.caption("आपके टेस्ट से जुड़ी महत्वपूर्ण जानकारी / Important info about your tests")

    # Show education tips based on what tests are booked
    test_tips = {
        "ECG": "🫀 **ECG (Electrocardiogram)**: बिल्कुल सामान्य प्रक्रिया है। आराम से लेटें और गहरी सांस लें।\nNo special preparation needed. Lie still and breathe normally.",
        "Echo": "🫀 **Echo (Echocardiography)**: अल्ट्रासाउंड जैसी प्रक्रिया है — पूरी तरह दर्द रहित।\nPainless ultrasound of your heart. Lie on your left side as instructed.",
        "TMT": "🏃 **TMT (Treadmill Test)**: हल्के कपड़े पहनें। टेस्ट से 2 घंटे पहले कुछ न खाएं।\nWear comfortable shoes. Don't eat 2 hours before the test.",
        "Holter": "📟 **Holter Monitor**: 24 घंटे portable ECG machine लगाई जाएगी। सामान्य काम करें।\nA portable ECG device for 24 hours. Continue normal activities.",
        "ABPM": "💓 **ABPM (Ambulatory BP)**: 24 घंटे BP monitor लगेगा। हर 30 मिनट में BP लेगा।\n24-hour blood pressure monitor. Records BP every 30 minutes.",
        "OPD": "🩺 **OPD Consultation**: डॉक्टर से परामर्श लें। अपनी सारी पुरानी रिपोर्ट लेकर आएं।\nDoctor consultation. Bring all previous medical reports.",
    }

    # Get unique test types from the patient's tests
    booked_tests = set(t["test_name"] for t in tests)
    for test_name in sorted(booked_tests):
        if test_name in test_tips:
            with st.container(border=True):
                st.markdown(test_tips[test_name])

    st.caption(
        "🔔 **Miss Call Alert System Active!** अब बिना Notification Permission के भी "
        "साउंड + वाइब्रेशन आएगा। बस स्क्रीन पर एक बार टैप करें 'Tap to enable sound' दिखे तो।  \n"
        "Sound + vibration work WITHOUT browser notification permission. Just tap the screen once if you see the hint."
    )

    # ─── Inject Status Watcher JS ──────────────────────────────────────────
    st.markdown(
        get_status_watcher_js(status_hash, patient["name"], patient["patient_id"]),
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
