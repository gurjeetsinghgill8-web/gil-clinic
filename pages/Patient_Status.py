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
import textwrap

from llm_harness import get_harness
from utils.config import (
    HOSPITAL_NAME, CLINIC_SPECIALTY, CLINIC_LOGO,
    STATUS_ICONS, STATUS_LABELS, ROOM_NAMES, AVG_TEST_TIME, BASE_URL
)
from utils.queue import calculate_wait_time, calculate_expected_time


def clean_html(html_str: str) -> str:
    """Strip all leading whitespace from every line of HTML to prevent markdown code block rendering."""
    return "\n".join(line.lstrip() for line in html_str.splitlines())


def inject_pwa_meta():
    """Inject PWA manifest link, service worker registration, and audio setup."""
    return clean_html("""
    <!-- PWA Manifest -->
    <link rel="manifest" href="/assets/manifest.json">
    <meta name="theme-color" content="#667eea">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="default">
    <meta name="apple-mobile-web-app-title" content="CardioQueue">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">

	    <!-- ─── GLOBAL AUDIO ENGINE ────────────────────────────────────────── -->
	    <script>
	    (function() {
	        window.__audioCtx = null;
	        window.__audioReady = false;

	        // SessionStorage flag survives st_autorefresh page reloads
	        var __audioActivated = sessionStorage.getItem("cq_audio_ready") === "1";

	        // Create + resume AudioContext (MUST be called from user gesture)
	        function unlockAudio() {
	            if (window.__audioReady) return true;
	            try {
	                if (!window.__audioCtx) {
	                    window.__audioCtx = new (window.AudioContext || window.webkitAudioContext)();
	                }
	                if (window.__audioCtx.state === "suspended") {
	                    window.__audioCtx.resume().then(function() {
	                        window.__audioReady = true;
	                        sessionStorage.setItem("cq_audio_ready", "1");
	                    });
	                } else {
	                    window.__audioReady = true;
	                    sessionStorage.setItem("cq_audio_ready", "1");
	                }
	                return window.__audioReady;
	            } catch(e) {
	                return false;
	            }
	        }

	        function getAudioCtx() { return window.__audioCtx; }

	        // Play beep(s) after AudioContext is unlocked
	        function playBeepNow(freq, duration, volume) {
	            var ctx = window.__audioCtx;
	            if (!ctx) return;
	            try {
	                var osc = ctx.createOscillator();
	                var g = ctx.createGain();
	                osc.connect(g); g.connect(ctx.destination);
	                osc.frequency.value = freq;
	                osc.type = "sine";
	                g.gain.value = volume || 0.3;
	                osc.start();
	                osc.stop(ctx.currentTime + (duration || 0.15));
	            } catch(e) {}
	        }

	        // Public: call from onclick — unlocks + plays beep instantly
	        window.playTestBeep = function() {
	            unlockAudio();
	            setTimeout(function() {
	                playBeepNow(880, 0.2, 0.5);
	                setTimeout(function() { playBeepNow(660, 0.15, 0.4); }, 150);
	                setTimeout(function() { playBeepNow(1000, 0.25, 0.4); }, 350);
	            }, 30);
	            if (navigator.vibrate) navigator.vibrate(300);
	            sessionStorage.setItem("cq_test_sound", "1");
	        };

	        // Public: ensure audio is ready
	        window.resumeAudio = function() { unlockAudio(); };

	        // If previously activated, resume on load
	        if (__audioActivated) {
	            setTimeout(function() {
	                var ctx = new (window.AudioContext || window.webkitAudioContext)();
	                window.__audioCtx = ctx;
	                if (ctx.state === "suspended") ctx.resume();
	            }, 100);
	        }

	        // Re-attach listeners on every page load (survives st_autorefresh)
	        function attachAudioListeners() {
	            ["touchstart", "click", "touchend"].forEach(function(evt) {
	                document.removeEventListener(evt, unlockAudio);
	                document.addEventListener(evt, unlockAudio, { once: true });
	            });
	        }
	        attachAudioListeners();

	        // Periodic resume (every 3s — handles st_autorefresh reloads)
	        setInterval(function() {
	            var ctx = window.__audioCtx;
	            if (ctx && ctx.state === "suspended") {
	                ctx.resume().then(function() {
	                    window.__audioReady = true;
	                    sessionStorage.setItem("cq_audio_ready", "1");
	                });
	            }
	            attachAudioListeners();
	            // Check test sound flag (set before st_autorefresh reload)
	            if (sessionStorage.getItem("cq_test_sound") === "1") {
	                sessionStorage.removeItem("cq_test_sound");
	                setTimeout(function() {
	                    playBeepNow(880, 0.2, 0.5);
	                    setTimeout(function() { playBeepNow(660, 0.15, 0.4); }, 150);
	                    if (navigator.vibrate) navigator.vibrate(200);
	                }, 50);
	            }
	        }, 3000);
	    })();
	
    // ─── Service Worker ─────────────────────────────────────────────────
    if ("serviceWorker" in navigator) {{
        navigator.serviceWorker.register("/assets/service-worker.js")
            .then(function() {{ console.log("[PWA] SW registered"); }})
            .catch(function(err) {{ console.log("[PWA] SW reg failed:", err); }});
    }}

    // Request notification permission
    if ("Notification" in window && Notification.permission === "default") {{
        Notification.requestPermission();
    }}

    // Add to Home Screen prompt
    window.addEventListener("beforeinstallprompt", function(e) {{
        e.preventDefault();
        window.deferredInstallPrompt = e;
        setTimeout(function() {{
            var btn = document.getElementById("install-pwa-btn");
            if (btn) btn.style.display = "block";
        }}, 3000);
    }});

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
    """)


def get_pwa_install_button() -> str:
    """Return HTML for the PWA install button (hidden by default)."""
    return clean_html("""
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
    """)


# ─── STATUS CHANGE DETECTION JS ─────────────────────────────────────────────────

def get_status_watcher_js(prev_status_hash: str, patient_name: str, patient_id: str = "") -> str:
    """
    Inject JavaScript that watches for status changes and triggers:
      - Sound (Web Audio API — triple beep)
      - Vibration (long pattern)
      - Browser Notification (if permission granted)
      - Service Worker background tracking

    Also detects 'misscall' query param → if present, stores misscall flag in
    sessionStorage and plays alert on next page load. This is how staff "Miss Call"
    button reaches the patient — via URL param instead of direct JS injection.
    """
    safe_name = patient_name.replace("'", "\\'").replace('"', '\\"')
    return clean_html(f"""
    <script>
    (function() {{
        var PID = "{patient_id}";
        var PNAME = "{safe_name}";
        var HASH = "{prev_status_hash}";
        var STORAGE_KEY = "cq_h_" + PID;
        var MISS_STORAGE_KEY = "cq_miss_" + PID;

        // ─── Helper: play beep on shared AudioContext ────────────────────────
        function playBeep(freq, duration, gainVal, delay) {{
            setTimeout(function() {{
                try {{
                    // Ensure audio is unlocked first
                    if (window.resumeAudio) window.resumeAudio();
                    var ctx = window.__audioCtx;
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

        // ─── 0. Check for misscall flag in URL ──────────────────────────────
        (function() {{
            try {{
                var urlParams = new URLSearchParams(window.location.search);
                if (urlParams.get("misscall") === "1") {{
                    // Store misscall flag — will be picked on next poll cycle
                    sessionStorage.setItem(MISS_STORAGE_KEY, "1");
                    // Remove misscall param from URL without reload
                    var url = new URL(window.location);
                    url.searchParams.delete("misscall");
                    window.history.replaceState({{}}, "", url);
                }}
            }} catch(e) {{}}
        }})();

        // ─── 1. Check for pending misscall flag ──────────────────────────────
        var pendingMisscall = sessionStorage.getItem(MISS_STORAGE_KEY);
        if (pendingMisscall === "1") {{
            sessionStorage.removeItem(MISS_STORAGE_KEY);
            window.__playPatientAlert("📞 Miss Call Alert - " + PNAME);
        }}

        // ─── 1b. Check for test sound flag (set by HTML button) ──────────────
        (function() {{
            var testFlag = sessionStorage.getItem("cq_test_sound");
            if (testFlag === "1") {{
                sessionStorage.removeItem("cq_test_sound");
                // Force resume and play beep after a short delay for DOM readiness
                setTimeout(function() {{
                    try {{
                        if (window.resumeAudio) window.resumeAudio();
                        if (window.playTestBeep) window.playTestBeep();
                        if (navigator.vibrate) navigator.vibrate(300);
                    }} catch(e) {{}}
                }}, 100);
            }}
        }})();

        // ─── 2. Compare with stored hash → alert on change ────────────────────
        var oldHash = sessionStorage.getItem(STORAGE_KEY);
        var justChanged = (oldHash && oldHash !== HASH);
        sessionStorage.setItem(STORAGE_KEY, HASH);

        if (justChanged) {{
            var el = document.getElementById("status-hash");
            var st = el ? el.getAttribute("data-status") || "Updated" : "Updated";
            window.__playPatientAlert(st);
        }}

        // ─── 3. Register Service Worker for background tracking ────────────────
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

        // ─── 4. Poll every 2 sec for DOM changes + misscall flag ──────────────
        setInterval(function() {{
            var el = document.getElementById("status-hash");
            if (!el) return;
            var nh = el.getAttribute("data-hash") || "";
            var ns = el.getAttribute("data-status") || "";
            var oh = sessionStorage.getItem(STORAGE_KEY) || "";
            // Check misscall data-misscall attribute
            var missFlag = el.getAttribute("data-misscall") || "";
            if (missFlag === "1") {{
                el.setAttribute("data-misscall", "0");
                window.__playPatientAlert("📞 Miss Call - " + ns);
            }}
            if (oh && nh && oh !== nh) {{
                sessionStorage.setItem(STORAGE_KEY, nh);
                window.__playPatientAlert(ns);
            }}
            }}, 2000);
    }})();
    </script>
    """)


# ─── MAIN PAGE ──────────────────────────────────────────────────────────────────

def show():
    harness = get_harness()
    today = datetime.now().strftime("%d-%b-%Y %I:%M %p")

    st.title(f"{CLINIC_LOGO} {CLINIC_SPECIALTY} Department")
    st.caption(f"{HOSPITAL_NAME} — {today}")

    # ─── Inject PWA Meta & Service Worker ──────────────────────────────────
    st.markdown(inject_pwa_meta(), unsafe_allow_html=True)

    # ─── Auto-refresh via client-side meta tag ──────────────────────────────
    # Using meta refresh instead of st_autorefresh because st_autorefresh does
    # a full page reload that destroys AudioContext + event listeners.
    # Meta refresh also triggers full reload, BUT we handle it via sessionStorage
    # + status-hash comparison in get_status_watcher_js().
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

    # ─── BRICK 1: DB-Poll Alert Check ────────────────────────────────────────
    # On every 5s auto-refresh, check if staff pressed Remind.
    # If yes: play sound + vibrate on THIS patient's phone, then clear the flag.
    try:
        from utils.db import get_patient_alert, clear_patient_alert
        _alert_data = get_patient_alert(patient["patient_id"])
        if _alert_data["has_alert"]:
            clear_patient_alert(patient["patient_id"])  # Clear immediately — show only once
            _alert_msg = _alert_data["message"] or "Your turn is coming soon!"
            # Visual alert banner
            st.warning(f"**Staff Alert:** {_alert_msg}")
            # JS: force audio + vibration on patient's phone
            _safe_msg = _alert_msg.replace("'", " ").replace('"', ' ').replace("\n", " ")
            st.markdown(f"""
            <script>
            (function() {{
                function playUrgentBeep() {{
                    try {{
                        var ctx = new (window.AudioContext || window.webkitAudioContext)();
                        [0, 0.35, 0.7].forEach(function(t) {{
                            var osc = ctx.createOscillator();
                            var gain = ctx.createGain();
                            osc.connect(gain); gain.connect(ctx.destination);
                            osc.frequency.value = 880; osc.type = 'sine';
                            gain.gain.setValueAtTime(0.8, ctx.currentTime + t);
                            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + t + 0.3);
                            osc.start(ctx.currentTime + t); osc.stop(ctx.currentTime + t + 0.3);
                        }});
                    }} catch(e) {{}}
                }}
                if (navigator.vibrate) navigator.vibrate([200, 100, 400, 100, 200]);
                playUrgentBeep();
                setTimeout(playUrgentBeep, 500);
                if (window.Notification && Notification.permission === 'granted') {{
                    new Notification('Clinic Alert', {{ body: '{_safe_msg}', icon: '/favicon.ico' }});
                }}
            }})();
            </script>
            """, unsafe_allow_html=True)
    except Exception:
        pass  # Silent fail — alert system must never crash patient view

    # ─── Detect misscall param from URL ───────────────────────────────────
    misscall_triggered = query_params.get("misscall", None)
    if isinstance(misscall_triggered, list):
        misscall_triggered = misscall_triggered[0] if misscall_triggered else None

    # ─── Hidden element for JS status watcher ──────────────────────────────
    st.markdown(
        f'<div id="status-hash" data-hash="{status_hash}" '
        f'data-status="{STATUS_LABELS.get(primary_status, primary_status)}" '
        f'data-test="{primary_test}" '
        f'data-misscall="{"1" if misscall_triggered == "1" else "0"}" '
        f'style="display:none;"></div>',
        unsafe_allow_html=True,
    )

    # ─── Test Sound Button (Streamlit button — SURVIVES st_autorefresh) ────
    # ─── Test Sound Button (HTML button — no page reload) ──────────────────
    st.markdown("""
    <div style="text-align:center;margin:6px 0;">
        <button onclick="
            sessionStorage.setItem('cq_test_sound', '1');
            if(window.resumeAudio) window.resumeAudio();
            if(window.playTestBeep) window.playTestBeep();
            if(navigator.vibrate) navigator.vibrate(300);
            var el = document.createElement('div');
            el.id = 'sound-test-result';
            el.innerHTML = '✅ Sound + Vibration working!';
            el.style.cssText = 'text-align:center;padding:8px;margin:6px 0;'
                + 'background:#4CAF50;color:white;border-radius:8px;font-weight:600;';
            var parent = document.getElementById('sound-test-btn-container');
            if(parent) parent.appendChild(el);
            setTimeout(function() {
                var r = document.getElementById('sound-test-result');
                if(r) r.remove();
            }, 4000);
        "
        style="background:linear-gradient(135deg,#667eea,#764ba2);color:white;
               border:none;padding:14px 24px;border-radius:12px;font-size:16px;
               font-weight:600;cursor:pointer;width:100%;
               box-shadow:0 4px 15px rgba(102,126,234,0.4);">
            🔊 Test Sound — Tap to Enable Alert Sounds
        </button>
        <p style="font-size:0.75rem;color:#888;margin-top:4px;">
            इसे टैप करें — Tap this to enable sound + vibration alerts
        </p>
    </div>
    """, unsafe_allow_html=True)

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
                    expected_time = calculate_expected_time(test_name, pos)
                    st.markdown(f"### ⏰")
                    st.markdown(f"**{expected_time}**")
                    if wait_time > 0:
                        st.caption(f"~{wait_time} min | #{pos} in queue")
                    else:
                        st.caption("Your turn is now!")
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
        "🔔 **Miss Call Alert System Active!** अब बिना Notification Permission के भी "
        "साउंड + वाइब्रेशन आएगा।  \n"
        "Sound + vibration work WITHOUT browser notification permission."
    )

    # ─── Copy Tracking Link Button (Client-side, Free) ───────────────────────────────
    try:
        _status_url = f"{BASE_URL}/?patient={patient.get('patient_id', '')}"
        st.markdown(
            f"""
            <div style="text-align:center; margin: 8px 0;">
                <button onclick="
                    navigator.clipboard.writeText('{_status_url}');
                    this.innerText = '✅ Link Copied! / लिंक कॉपी हो गया!';
                    setTimeout(() => {{ this.innerText = '🔗 Copy Status Link / ट्रैकिंग लिंक कॉपी करें'; }}, 2000);
                "
                style="background:linear-gradient(135deg,#667eea,#764ba2);
                color:white;border:none;padding:10px 18px;border-radius:10px;text-align:center;
                font-weight:600;font-size:0.9rem;width:100%;cursor:pointer;transition:all 0.3s ease;">
                🔗 Copy Status Link / ट्रैकिंग लिंक कॉपी करें
                </button>
            </div>
            """,
            unsafe_allow_html=True
        )
    except Exception:
        pass

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
