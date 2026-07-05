"""
Reception Dashboard — Patient Registration
============================================
The front desk staff uses this page to register new patients,
print tokens, and view today's registered patients.

All actions go through llm_harness.py — no direct DB calls.
Modern UI with gradient cards QR code display.
"""
import streamlit as st
from datetime import date, datetime

from llm_harness import get_harness
from utils.config import TEST_TYPES, HOSPITAL_NAME, STATUS_LABELS, STATUS_ICONS, BASE_URL
from utils.notifications import request_notification_permission_script


def show():
    harness = get_harness()
    now = datetime.now()
    today = now.strftime("%d-%b-%Y %I:%M %p")

    st.title("📋 Reception Dashboard")
    st.markdown(f"### {HOSPITAL_NAME}")
    st.caption(f"🗓️ {today}")

    # ─── Registration Form ───────────────────────────────────────────────────
    with st.container(border=True):
        st.subheader("🆕 New Patient Registration")

        col1, col2 = st.columns(2)

        with col1:
            name = st.text_input("Patient Name *", placeholder="Enter full name",
                                 key="reg_name")
            mobile = st.text_input("Mobile Number *", placeholder="10-digit number",
                                   max_chars=10, key="reg_mobile",
                                   help="Indian mobile number without +91")

        with col2:
            age = st.number_input("Age *", min_value=0, max_value=150,
                                  step=1, key="reg_age")
            gender = st.selectbox("Gender *", ["Male", "Female", "Other"],
                                  key="reg_gender")

        st.markdown("**Tests Required ***")
        test_cols = st.columns(len(TEST_TYPES))
        selected_tests = []
        for i, test in enumerate(TEST_TYPES):
            with test_cols[i]:
                if st.checkbox(test, key=f"test_{test}"):
                    selected_tests.append(test)

        # ─── Action Buttons ──────────────────────────────────────────────
        btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 2])

        with btn_col1:
            save_clicked = st.button("💾 Save", type="primary", use_container_width=True)

        with btn_col2:
            print_clicked = st.button("🖨️ Print Token", use_container_width=True)

        with btn_col3:
            view_status_clicked = st.button("🔍 View Status", use_container_width=True)

        # ─── Handle Save ─────────────────────────────────────────────────
        if save_clicked:
            result = harness.register_patient(name, mobile, age, gender, selected_tests)

            if result["success"]:
                st.success(result["message"])

                # Trigger browser notification with sound + vibration
                if result["notification"]:
                    script = harness.get_notification_script(
                        "🏥 New Patient Registered", result["notification"], urgent=False
                    )
                    st.markdown(script, unsafe_allow_html=True)

                patient_id = result["patient"]["patient_id"]

                # Store last registered patient for token printing
                st.session_state.last_patient = {
                    "name": name,
                    "patient_id": patient_id,
                    "tests": result["tests"],
                    "mobile": mobile,
                }

                # Show QR Code and Token Preview side by side
                qr_col, token_col = st.columns([1, 2])

                with qr_col:
                    qr_data_uri = harness.generate_qr_code_base64(patient_id)
                    if qr_data_uri:
                        qr_url = harness.get_qr_url(patient_id)
                        st.markdown(
                            f"""
                            <div style="text-align:center;padding:1rem;border:2px dashed #667eea;
                                        border-radius:12px;background:#f8f9ff;">
                                <h4 style="margin-bottom:0.5rem;">📱 Patient QR</h4>
                                <img src="{qr_data_uri}" style="width:160px;height:160px;
                                     border-radius:8px;background:white;padding:8px;" alt="QR Code">
                                <p style="font-size:0.85rem;color:#667eea;margin-top:8px;font-weight:600;">
                                    Scan to track live status
                                </p>
                                <a href="{qr_url}" target="_blank"
                                   style="text-decoration:none;">
                                    <button style="background:linear-gradient(135deg,#667eea,#764ba2);
                                                   color:white;border:none;padding:8px 20px;
                                                   border-radius:8px;cursor:pointer;font-size:0.9rem;
                                                   font-weight:600;">
                                        🔗 Open Link
                                    </button>
                                </a>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                    else:
                        st.info("📱 Install 'qrcode' package for QR generation:\n`pip install qrcode[pil]`")

                with token_col:
                    with st.expander("🖨️ Token Preview", expanded=True):
                        slip = harness.generate_token_slip(
                            name, patient_id, result["tests"]
                        )
                        st.code(slip, language="text")
                        st.markdown(
                            "👉 Click **Print Token** button above or use Ctrl+P to print.",
                            help="Print this token slip",
                        )
            else:
                st.error(result["message"])

        # ─── Handle Print ────────────────────────────────────────────────
        if print_clicked:
            if "last_patient" in st.session_state:
                lp = st.session_state.last_patient
                slip = harness.generate_token_slip(
                    lp["name"], lp["patient_id"], lp["tests"]
                )
                # Use HTML + CSS for better print formatting
                html_slip = f"""
                <html>
                <head><style>
                    body {{ font-family: monospace; padding: 20px; }}
                    .slip {{ white-space: pre; font-size: 14px; line-height: 1.6; }}
                </style></head>
                <body>
                    <div class="slip">{slip}</div>
                    <script>window.print();</script>
                </body>
                </html>
                """
                st.components.v1.html(html_slip, height=0, width=0)
                st.success("🖨️ Token sent to printer!")

                # Also show it
                st.code(slip, language="text")
            else:
                st.warning("⚠️ Please register a patient first before printing.")

        # ─── Handle View Status ──────────────────────────────────────────
        if view_status_clicked:
            if "last_patient" in st.session_state:
                st.info(
                    f"📱 Patient {st.session_state.last_patient['name']} — "
                    f"ID: {st.session_state.last_patient['patient_id']}\n\n"
                    "Go to **Patient Status** page and enter the mobile number "
                    f"{st.session_state.last_patient['mobile']} to see live status."
                )
            else:
                st.info(
                    "Go to **Patient Status** page and enter a patient's mobile "
                    "number to see their live test statuses."
                )

    # ─── Common QR Code for Patient Status ─────────────────────────────────────
    st.divider()
    st.subheader("📸 एक ही QR Code सबके लिए / One QR Code for All Patients")

    st.markdown(
        "इस QR Code को रिसेप्शन पर चिपका दें। मरीज़ स्कैन करें → अपना मोबाइल नंबर डालें → "
        "अपने टेस्ट का स्टेटस देखें। **हर मरीज़ के लिए अलग QR बनाने की ज़रूरत नहीं!**\n\n"
        "Place this QR at reception. Patients scan → enter their mobile → see live status. "
        "**No need for per-patient QR codes!**"
    )

    common_qr_url = f"{BASE_URL}/?patient=common"
    qr_data_uri = harness.generate_qr_code_base64("common")
    if qr_data_uri:
        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown(
                f"""
                <div style="text-align:center;padding:1rem;border:2px dashed #667eea;
                            border-radius:12px;background:#f8f9ff;">
                    <img src="{qr_data_uri}" style="width:160px;height:160px;
                         border-radius:8px;background:white;padding:8px;" alt="Common QR">
                    <p style="font-size:0.85rem;color:#667eea;margin-top:8px;font-weight:600;">
                        📱 Scan → Enter Mobile
                    </p>
                    <a href="{common_qr_url}" target="_blank"
                       style="text-decoration:none;">
                        <button style="background:linear-gradient(135deg,#667eea,#764ba2);
                                       color:white;border:none;padding:8px 20px;
                                       border-radius:8px;cursor:pointer;font-size:0.9rem;
                                       font-weight:600;">
                            🔗 Test Link
                        </button>
                    </a>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with col2:
            st.markdown(
                """
                ### 📋 कैसे काम करता है / How It Works
                1. 🖨️ **Print this QR code** and paste at reception counter
                2. 📱 **Patient scans** QR with their phone camera
                3. 🔢 **Enters mobile number** they gave at registration
                4. 👁️ **Sees live status** of all their tests
                5. 🔄 **Auto-refreshes** every 5 seconds with sound + vibration
                """,
                unsafe_allow_html=True,
            )

    # ─── Today's Patients Table ──────────────────────────────────────────────
    st.divider()
    st.subheader("📋 Today's Registered Patients")

    try:
        patients = harness.get_patient_details("", by_mobile=False)
        # Refresh from DB directly for today's list
        from utils.db import get_today_patients
        today_patients = get_today_patients()

        if today_patients:
            # Show each patient with remind button
            for p in today_patients:
                p_id = p.get("patient_id", "")
                p_name = p.get("name", "")
                p_mobile = p.get("mobile", "")
                tests = harness.get_patient_details(p["patient_id"], by_mobile=False)
                test_names = [t["test_name"] for t in tests["tests"]]
                status_text = " | ".join(
                    f"{STATUS_ICONS.get(t['status'], '❓')} {t['test_name']}: {STATUS_LABELS.get(t['status'], t['status'])}"
                    for t in tests["tests"]
                )

                with st.container(border=True):
                    col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
                    with col1:
                        st.markdown(f"**{p_name}** — `{p_id}`")
                        st.caption(f"📱 {p_mobile} | Tests: {', '.join(test_names)}")
                    with col2:
                        st.markdown(f"{status_text}")
                    with col3:
                        if st.button("🔔 Remind", key=f"remind_rec_{p_id}",
                                     use_container_width=True):
                            result = harness.send_reminder(
                                p_name, ", ".join(test_names), p_mobile
                            )
                            if result["success"]:
                                st.success(result["message"])
                                if result.get("notification"):
                                    script = harness.get_notification_script(
                                        "🔔 Reminder from Reception",
                                        result["notification"], urgent=True
                                    )
                                    st.markdown(script, unsafe_allow_html=True)
                    with col4:
                        if st.button("📞 Miss Call", key=f"misscall_rec_{p_id}",
                                     use_container_width=True, type="secondary",
                                     help="Sends alert to patient page WITHOUT needing notification permission. Works on all phones."):
                            result = harness.send_misscall_alert(
                                p_name, ", ".join(test_names), patient_pid=p_id
                            )
                            if result["success"]:
                                st.success(result["message"])
                                # Show the misscall URL — staff can share via WhatsApp
                                misscall_url = result.get("misscall_url", "")
                                if misscall_url:
                                    st.info(f"📤 Share this link with patient:\n`{misscall_url}`")
                                    st.markdown(
                                        f'<a href="{misscall_url}" target="_blank">'
                                        f'<button style="background:linear-gradient(135deg,#ff4444,#cc0000);color:white;'
                                        f'border:none;padding:10px 20px;border-radius:8px;cursor:pointer;font-size:14px;'
                                        f'font-weight:600;">📞 Open Miss Call Alert on Patient Page</button></a>',
                                        unsafe_allow_html=True,
                                    )
        else:
            st.info("📭 No patients registered today yet.")

    except Exception as e:
        st.warning(f"Could not load patient list. Check database connection.\nError: {e}")

    # ─── Quick Stats ─────────────────────────────────────────────────────────
    with st.sidebar:
        st.divider()
        st.markdown("### 📊 Quick Stats")
        try:
            stats = harness.get_all_dashboard_stats()
            for dept, s in stats.items():
                waiting = s.get("waiting", 0)
                in_prog = s.get("in_progress", 0)
                done = s.get("completed", 0)
                st.metric(
                    f"{dept}",
                    f"{waiting} waiting",
                    f"{in_prog} active · {done} done",
                )
        except Exception:
            pass
