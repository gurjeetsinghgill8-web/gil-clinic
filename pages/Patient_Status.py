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
"""
import streamlit as st
from datetime import datetime
import streamlit.components.v1 as components

from llm_harness import get_harness
from utils.config import (
    HOSPITAL_NAME, CLINIC_SPECIALTY, CLINIC_LOGO,
    STATUS_ICONS, STATUS_LABELS, ROOM_NAMES, AVG_TEST_TIME, BASE_URL
)
from utils.queue import calculate_wait_time, calculate_expected_time


# ─── PWA / META INJECTION ───────────────────────────────────────────────────────

def inject_pwa_meta() -> str:
    """Inject PWA static manifest links and viewport meta tags into parent page head."""
    return """
    <!-- PWA Manifest -->
    <link rel="manifest" href="/assets/manifest.json">
    <meta name="theme-color" content="#667eea">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="default">
    <meta name="apple-mobile-web-app-title" content="CardioQueue">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    """


def register_pwa_sw() -> str:
    """JavaScript string to register Service Worker and request notifications inside components.html."""
    return """
    <script>
    if ("serviceWorker" in navigator) {
        navigator.serviceWorker.register("/assets/service-worker.js")
            .then(function() { console.log("[PWA] SW registered"); })
            .catch(function(err) { console.log("[PWA] SW reg failed:", err); });
    }
    if ("Notification" in window && Notification.permission === "default") {
        Notification.requestPermission();
    }
    </script>
    """


def get_pwa_install_button() -> str:
    """Return HTML/JS for the PWA install button inside components.html."""
    return """
    <div id="install-pwa-btn" style="display: none; text-align: center; margin: 10px 0;">
        <button onclick="installPWA()" style="
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white; border: none; padding: 12px 24px;
            border-radius: 12px; font-size: 1rem; font-weight: 600;
            width: 100%; cursor: pointer; box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
            font-family: sans-serif;
        ">
            📲 Add to Home Screen
        </button>
        <p style="font-size: 0.75rem; color: #888; margin-top: 6px; font-family: sans-serif;">
            Install for one-tap access & offline support
        </p>
    </div>
    <script>
    window.addEventListener("beforeinstallprompt", function(e) {
        e.preventDefault();
        window.deferredInstallPrompt = e;
        var btn = document.getElementById("install-pwa-btn");
        if (btn) btn.style.display = "block";
    });

    function installPWA() {
        var prompt = window.deferredInstallPrompt;
        if (prompt) {
            prompt.prompt();
            prompt.userChoice.then(function(choice) {
                if (choice.outcome === "accepted") {
                    console.log("[PWA] User accepted install");
                }
                window.deferredInstallPrompt = null;
                var btn = document.getElementById("install-pwa-btn");
                if (btn) btn.style.display = "none";
            });
        }
    }
    </script>
    """


def trigger_alert_sound(message: str = ""):
    """Trigger voice text-to-speech alert and vibration in the browser via clean HTML components."""
    import streamlit.components.v1 as components
    safe_msg = message.replace("'", " ").replace('"', ' ').replace("\n", " ")
    js_code = """
    <script>
    (function() {
        try {
            window.speechSynthesis.cancel(); // Cancel any ongoing speech
            var voiceMsg = "{safe_msg}";
            if (voiceMsg === "") {
                voiceMsg = "Welcome to Doctor Gill Clinic";
            }
            
            // 1. Speak in English
            var speakEn = new SpeechSynthesisUtterance(voiceMsg);
            speakEn.lang = "en-US";
            speakEn.rate = 0.95;
            window.speechSynthesis.speak(speakEn);
            
            // 2. Speak in Hindi (if generic welcome)
            if ("{safe_msg}" === "" || "{safe_msg}".includes("Welcome")) {
                var speakHi = new SpeechSynthesisUtterance("डॉक्टर गिल के क्लिनिक में आपका स्वागत है");
                speakHi.lang = "hi-IN";
                speakHi.rate = 0.95;
                window.speechSynthesis.speak(speakHi);
            }
        } catch(e) {}
        if (navigator.vibrate) navigator.vibrate([500, 200, 500, 200, 700]);
        if ("Notification" in window && Notification.permission === "granted" && "{safe_msg}" !== "") {
            try {
                new Notification("🔔 CardioQueue Alert", { 
                    body: "{safe_msg}", 
                    icon: "https://img.icons8.com/color/48/hospital.png" 
                });
            } catch(err) {}
        }
    })();
    </script>
    """.replace("{safe_msg}", safe_msg)
    components.html(js_code, height=0)


def trigger_dynamic_voice_alert(test_name: str, status: str):
    """Trigger dynamic bilingual English and Hindi voice announcements based on test and status updates."""
    import streamlit.components.v1 as components
    
    # 1. Map status to custom patient directions
    en_msg = ""
    hi_msg = ""
    
    hi_test = {
        "ECG": "ई सी जी",
        "Echo": "इको",
        "TMT": "टी एम टी",
        "Holter": "होल्टर",
        "ABPM": "ए बी पी एम",
        "OPD": "ओ पी डी consultation"
    }.get(test_name, test_name)
    
    if status == "called":
        en_msg = f"Welcome to Doctor Gill Clinic. Please proceed to the {test_name} Room for your test."
        hi_msg = f"डॉक्टर गिल के क्लिनिक में आपका स्वागत है। कृपया अपने {hi_test} टेस्ट के लिए रूम में प्रवेश करें।"
    elif status == "in_progress":
        en_msg = f"Your {test_name} test is now in progress."
        hi_msg = f"आपका {hi_test} टेस्ट शुरू हो चुका है और चल रहा है।"
    elif status == "report_ready":
        en_msg = f"Your {test_name} report is ready. Please collect it from the counter."
        hi_msg = f"आपकी {hi_test} रिपोर्ट तैयार है। कृपया काउंटर से इसे प्राप्त करें।"
    elif status in ["completed", "delivered"]:
        en_msg = "Thank you for visiting Doctor Gill Clinic. Have a nice day."
        hi_msg = "डॉक्टर गिल के क्लिनिक में आने के लिए आपका धन्यवाद। आपका दिन शुभ रहे।"
    else:
        en_msg = f"Your {test_name} test is updated to {status}."
        hi_msg = f"आपका {hi_test} टेस्ट {status} पर अपडेट हो गया है।"

    # Escape quotes for safety
    en_msg = en_msg.replace("'", "\\'").replace('"', '\\"').replace("\n", " ")
    hi_msg = hi_msg.replace("'", "\\'").replace('"', '\\"').replace("\n", " ")

    js_code = f"""
    <script>
    (function() {{
        try {{
            window.speechSynthesis.cancel(); // Cancel any ongoing speech
            
            // Speak English
            var speakEn = new SpeechSynthesisUtterance("{en_msg}");
            speakEn.lang = "en-US";
            speakEn.rate = 0.95;
            window.speechSynthesis.speak(speakEn);
            
            // Speak Hindi when English finishes
            speakEn.onend = function() {{
                try {{
                    var speakHi = new SpeechSynthesisUtterance("{hi_msg}");
                    speakHi.lang = "hi-IN";
                    speakHi.rate = 0.95;
                    window.speechSynthesis.speak(speakHi);
                }} catch(err) {{}}
            }};
        }} catch(e) {{}}
        if (navigator.vibrate) navigator.vibrate([500, 200, 500, 200, 700]);
    }})();
    </script>
    """
    components.html(js_code, height=0)


# ─── MAIN PAGE ──────────────────────────────────────────────────────────────────

def show():
    harness = get_harness()
    today = datetime.now().strftime("%d-%b-%Y %I:%M %p")

    st.title(f"{CLINIC_LOGO} {CLINIC_SPECIALTY} Department")
    st.caption(f"{HOSPITAL_NAME} — {today}")

    # ─── Inject PWA Meta ──────────────────────────────────────────────────
    st.markdown(inject_pwa_meta(), unsafe_allow_html=True)
    components.html(register_pwa_sw(), height=0)

    # ─── Auto-refresh ─────────────────────────────────────────────────────
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
        # Auto-loaded from mobile param
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

    # Build a status hash to detect status changes
    status_hash = "|".join(f"{t['test_name']}:{t['status']}" for t in tests)
    all_statuses = [t["status"] for t in tests]
    primary_status = all_statuses[0] if all_statuses else "waiting"
    primary_test = tests[0]["test_name"] if tests else ""

    # ─── Python-Side Status Change Detection ──────────────────────────────────
    if "prev_test_statuses" not in st.session_state:
        st.session_state.prev_test_statuses = {t["test_name"]: t["status"] for t in tests}
    else:
        prev = st.session_state.prev_test_statuses
        for t in tests:
            t_name = t["test_name"]
            curr_status = t["status"]
            old_status = prev.get(t_name, None)
            if old_status is not None and old_status != curr_status:
                trigger_dynamic_voice_alert(t_name, curr_status)
        st.session_state.prev_test_statuses = {t["test_name"]: t["status"] for t in tests}

    # ─── BRICK 1: DB-Poll Alert Check ────────────────────────────────────────
    try:
        from utils.db import get_patient_alert, clear_patient_alert
        _alert_data = get_patient_alert(patient["patient_id"])
        if _alert_data["has_alert"]:
            clear_patient_alert(patient["patient_id"])  # Clear immediately
            _alert_msg = _alert_data["message"] or "Your turn is coming soon!"
            st.warning(f"**Staff Alert:** {_alert_msg}")
            # Trigger triple-beep sound
            trigger_alert_sound(_alert_msg)
    except Exception:
        pass

    # ─── Detect misscall param from URL ───────────────────────────────────
    misscall_triggered = query_params.get("misscall", None)
    if isinstance(misscall_triggered, list):
        misscall_triggered = misscall_triggered[0] if misscall_triggered else None

    if misscall_triggered == "1":
        # Clear param and play misscall beep
        st.query_params.pop("misscall", None)
        trigger_alert_sound("Missed Call Alert!")

    # ─── Test Sound Button (Iframe Sandbox, safe from React error #231) ────
    components.html("""
    <div style="text-align:center;">
        <button id="ts-btn" style="background:linear-gradient(135deg,#667eea,#764ba2);color:white;
               border:none;padding:14px 24px;border-radius:12px;font-size:16px;
               font-weight:600;cursor:pointer;width:100%;font-family:sans-serif;
               box-shadow:0 4px 15px rgba(102,126,234,0.4);">
            🔊 Test Sound — Tap to Enable Alert Sounds
        </button>
        <p style="font-size:0.75rem;color:#888;margin-top:4px;font-family:sans-serif;">
            इसे टैप करें — Tap this to enable sound + vibration alerts
        </p>
        <div id="test-res"></div>
     </div>
     <script>
     document.getElementById('ts-btn').onclick = function() {
         try {
             window.speechSynthesis.cancel(); // Stop any currently speaking voice
             
             // Speak English Welcome
             var speakEn = new SpeechSynthesisUtterance("Welcome to Doctor Gill Clinic");
             speakEn.lang = "en-US";
             speakEn.rate = 0.95;
             window.speechSynthesis.speak(speakEn);
             
             // Speak Hindi Welcome
             var speakHi = new SpeechSynthesisUtterance("डॉक्टर गिल के क्लिनिक में आपका स्वागत है");
             speakHi.lang = "hi-IN";
             speakHi.rate = 0.95;
             window.speechSynthesis.speak(speakHi);
         } catch(e) {}
         if (navigator.vibrate) navigator.vibrate(300);
         var res = document.getElementById('test-res');
         res.innerHTML = '<div style="text-align:center;padding:8px;margin:6px 0;background:#4CAF50;color:white;border-radius:8px;font-weight:600;font-family:sans-serif;font-size:0.85rem;">✅ Voice greeting playing! / स्वागत संदेश बज रहा है!</div>';
         setTimeout(function() { res.innerHTML = ''; }, 3000);
     };
     </script>
    """, height=120)

    # ─── PWA Install Button ────────────────────────────────────────────────
    components.html(get_pwa_install_button(), height=100)

    # ─── Patient Info Card ─────────────────────────────────────────────────
    with st.container(border=True):
        cols = st.columns([2, 1])
        with cols[0]:
            visits = harness.get_patient_visit_count(patient.get("mobile", ""))
            visit_badge = f"<span style='background:#667eea;color:white;font-size:0.75rem;padding:2px 10px;border-radius:12px;margin-left:8px;font-weight:600;'>🔄 #{visits}</span>" if visits > 1 else ""
            st.markdown(f"### 👤 {patient['name']}{visit_badge}", unsafe_allow_html=True)
            st.markdown(f"🆔 `{patient['patient_id']}`")
            # Copy link button
            status_url = harness.get_patient_status_url(patient["patient_id"])
            copy_script = harness.get_copy_link_script(status_url, "Link copied!")
            st.markdown(copy_script, unsafe_allow_html=True)
        with cols[1]:
            st.markdown(f"### {STATUS_ICONS.get(primary_status, '❓')}")
            st.markdown(f"**{STATUS_LABELS.get(primary_status, primary_status)}**")

    # ─── Patient Help Desk: Ask Reception ──────────────────────────────────
    try:
        from utils.db import set_patient_inquiry, get_patient_inquiry
        active_inquiry = get_patient_inquiry(patient["patient_id"])
        
        inq_cols = st.columns([2, 1])
        with inq_cols[0]:
            if active_inquiry:
                st.warning("⏳ Status check request sent to Receptionist. / रिसेप्शनिस्ट से संपर्क किया जा रहा है...")
            else:
                st.info("💡 Want an update? Click 'Ask Reception' to notify the front desk. / समय की जानकारी के लिए रिसेप्शन से पूछें।")
        with inq_cols[1]:
            if not active_inquiry:
                if st.button("🙋 Ask Reception", key="ask_rec_btn", use_container_width=True, type="primary"):
                    set_patient_inquiry(patient["patient_id"], "How much time is left?")
                    # Speech synthesis confirmation
                    js_speech = """
                    <script>
                    (function() {
                        try {
                            window.speechSynthesis.cancel();
                            var speakEn = new SpeechSynthesisUtterance("Thank you. The receptionist is checking your queue status and will update you shortly.");
                            speakEn.lang = "en-US";
                            speakEn.rate = 0.95;
                            window.speechSynthesis.speak(speakEn);
                            
                            speakEn.onend = function() {
                                try {
                                    var speakHi = new SpeechSynthesisUtterance("धन्यवाद। रिसेप्शनिस्ट आपके क्यू का स्टेटस चेक कर रही हैं और जल्द ही आपको अपडेट करेंगी।");
                                    speakHi.lang = "hi-IN";
                                    speakHi.rate = 0.95;
                                    window.speechSynthesis.speak(speakHi);
                                } catch(err) {}
                            };
                        } catch(e) {}
                    })();
                    </script>
                    """
                    components.html(js_speech, height=0)
                    st.toast("📨 Status check requested!")
                    st.rerun()
    except Exception:
        pass

    # ─── Live Queue Pulse Indicator ────────────────────────────────────────
    st.markdown(
        f'<div class="glass-banner" style="margin-top: 1rem;">'
        f'<div style="display: flex; align-items: center; justify-content: space-between;">'
        f'<div>'
        f'<span class="live-dot"></span>'
        f'<span style="font-weight:600; font-size:1.1rem; color:var(--text-primary);">LIVE Queue Tracker</span>'
        f'<div style="font-size:0.8rem; color:var(--text-secondary);">Auto-refreshes every 5s • Auto-refresh चालू है</div>'
        f'</div>'
        f'<div style="text-align: right;">'
        f'<div style="font-size:0.75rem; text-transform:uppercase; color:var(--text-light); letter-spacing:0.05em;">Updated</div>'
        f'<div style="font-size:0.9rem; font-weight:700; color:var(--primary);">{datetime.now().strftime("%I:%M:%S %p")}</div>'
        f'</div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ─── Queue Status Summary ──────────────────────────────────────────────
    st.markdown("#### 📋 Queue Details / क्यू की जानकारी")
    st.divider()

    # Active tests list
    active_tests = [t for t in tests if t["status"] not in ["completed", "delivered", "report_ready"]]
    completed_tests = [t for t in tests if t["status"] in ["completed", "delivered", "report_ready"]]

    if active_tests:
        for idx, t in enumerate(active_tests):
            t_name = t["test_name"]
            status = t["status"]
            q_pos = t.get("queue_position", 0)
            token_num = t.get("token_number", 0)
            room = t.get("room", ROOM_NAMES.get(t_name, "Room 1"))

            # Calculate wait time & expected time
            wait_time = calculate_wait_time(t_name, q_pos)
            expected_time = calculate_expected_time(t_name, q_pos)

            # Build status badge HTML
            status_class = f"status-{status}"
            badge_html = f'<span class="status-badge {status_class}">{STATUS_ICONS.get(status, "")} {STATUS_LABELS.get(status, status)}</span>'

            # Header info
            st.markdown(
                f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">'
                f'<span style="font-size: 1.15rem; font-weight: 700; color: var(--text-primary);">{t_name}</span>'
                f'{badge_html}'
                f'</div>',
                unsafe_allow_html=True
            )

            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"🚪 **{room}**")
                st.markdown(f"🎫 Token Number: **#{token_num}**")
                # Wait time progress steps visual
                done_steps = {
                    "waiting": 1,
                    "called": 2,
                    "in_progress": 3,
                }.get(status, 1)

                steps_html = "".join(
                    f'<div class="progress-step {"done" if i < done_steps else "active" if i == done_steps else ""}"></div>'
                    for i in range(1, 5)
                )
                st.markdown(
                    f'<div class="progress-steps">{steps_html}</div>',
                    unsafe_allow_html=True
                )

            with col2:
                if status == "called":
                    st.markdown(
                        f'<div style="background:rgba(253,203,110,0.15); border:1px solid rgba(253,203,110,0.4); padding:10px; border-radius:8px; text-align:center;">'
                        f'<span style="font-size: 1.1rem; font-weight: 700; color: hsl(37,90%,38%);">📢 PLEASE PROCEED NOW</span><br/>'
                        f'<span style="font-size:0.8rem; color:hsl(37,90%,38%);">कृपया रूम में प्रवेश करें</span>'
                        f'</div>',
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(
                        f'<div style="background:var(--bg-glass); border:1px solid var(--border); padding:8px 12px; border-radius:8px; text-align:center;">'
                        f'<span style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-light);">Estimated Time</span><br/>'
                        f'<span class="token-number" style="font-size: 1.6rem !important;">{expected_time}</span><br/>'
                        f'<span style="font-size: 0.8rem; color: var(--text-secondary);">Waiting list position: <strong>#{q_pos}</strong> (~{wait_time} min)</span>'
                        f'</div>',
                        unsafe_allow_html=True
                    )
            st.markdown("<br/>", unsafe_allow_html=True)
    else:
        st.success("🎉 All your scheduled tests are completed today! / आपके आज के सभी टेस्ट पूरे हो चुके हैं!")

    # Completed tests summary
    if completed_tests:
        st.markdown("#### ✅ Completed Tests / पूरे हो चुके टेस्ट")
        for t in completed_tests:
            t_name = t["test_name"]
            status = t["status"]
            status_class = f"status-{status}"
            badge_html = f'<span class="status-badge {status_class}">{STATUS_ICONS.get(status, "")} {STATUS_LABELS.get(status, status)}</span>'

            st.markdown(
                f'<div style="display: flex; justify-content: space-between; align-items: center; background:rgba(0,184,148,0.06); padding:8px 16px; border-radius:8px; margin: 4px 0;">'
                f'<span style="font-weight: 600; color:var(--text-primary);">{t_name}</span>'
                f'{badge_html}'
                f'</div>',
                unsafe_allow_html=True
            )
            # Show doctor notes if present
            notes = t.get("doctor_notes", "").strip()
            if notes:
                st.markdown(
                    f'<div style="background:rgba(102,126,234,0.06); border-left:3px solid #667eea; '
                    f'padding:6px 12px; margin:2px 0 8px 0; border-radius:4px; font-size:0.9rem;">'
                    f'📝 <strong>Doctor\'s Notes:</strong> {notes}'
                    f'</div>',
                    unsafe_allow_html=True
                )

    # ─── Copy Tracking Link Button (Client-side, Free) ───────────────────────────────
    try:
        _status_url = f"{BASE_URL}/?patient={patient.get('patient_id', '')}"
        components.html(f"""
        <div style="text-align:center;">
            <button id="cp-btn" style="background:linear-gradient(135deg,#667eea,#764ba2);
            color:white;border:none;padding:10px 18px;border-radius:10px;text-align:center;
            font-weight:600;font-size:0.9rem;width:100%;cursor:pointer;transition:all 0.3s ease;
            font-family:sans-serif;">
            🔗 Copy Status Link / ट्रैकिंग लिंक कॉपी करें
            </button>
        </div>
        <script>
        document.getElementById('cp-btn').onclick = function() {{
            navigator.clipboard.writeText('{_status_url}');
            this.innerText = '✅ Link Copied! / लिंक कॉपी हो गया!';
            var t = this;
            setTimeout(function() {{ t.innerText = '🔗 Copy Status Link / ट्रैकिंग लिंक कॉपी करें'; }}, 2000);
        }};
        </script>
        """, height=50)
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
        "TMT": "🏃 **TMT (Treadmill Test)**: ट्रेडमिल पर चलने/दौड़ने की तैयारी रखें। ढीले कपडे और जूते पहनें।\nWear comfortable clothes and walking shoes. Inform staff if you feel chest pain.",
        "Holter": "📟 **Holter Monitor**: 24 घंटे का पोर्टेबल ईसीजी। डिवाइस को गीला न करें, सामान्य गतिविधियां जारी रखें।\nKeep monitor dry. Do not shower. Log any symptoms in the diary.",
        "ABPM": "🩺 **ABPM (Ambulatory BP)**: 24 घंटे का बीपी मॉनिटर। हर बार कफ फूलने पर हाथ सीधा और शांत रखें।\nKeep arm still and straight when cuff inflates. Keep device on at night.",
        "OPD": "🩺 **Doctor Consultation**: डॉक्टर से मिलने से पहले अपने सभी पुराने प्रिस्क्रिप्शन और रिपोर्ट्स तैयार रखें।\nKeep your medical history files ready. Write down questions for the doctor.",
    }

    shown_tips = 0
    for t in tests:
        t_name = t["test_name"]
        if t_name in test_tips:
            st.info(test_tips[t_name])
            shown_tips += 1

    if shown_tips == 0:
        st.info("🫀 स्वस्थ हृदय के लिए रोजाना 30 मिनट टहलें और कम नमक का सेवन करें।\nFor a healthy heart, walk 30 minutes daily and reduce salt intake.")
