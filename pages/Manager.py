"""
Manager Dashboard — Full Clinic Overview
==========================================
Real-time view of all departments, patient counts, and status flow.
Access: Manager role only.

Modern UI with gradient stat cards, department breakdowns, and quick actions.
"""
import streamlit as st
from datetime import datetime

from llm_harness import get_harness
from utils.config import HOSPITAL_NAME, TEST_TYPES, STATUS_ICONS, STATUS_LABELS, AVG_TEST_TIME


def show():
    harness = get_harness()
    now = datetime.now()
    today = now.strftime("%d-%b-%Y %I:%M %p")

    st.title("📈 Manager Dashboard")
    st.markdown(f"### {HOSPITAL_NAME} — Cardiology Department")
    st.caption(f"🗓️ {today}")

    # ─── Summary Cards ───────────────────────────────────────────────────────
    st.markdown("### 📊 Overall Status")
    st.caption("Real-time summary across all departments")

    dept_stats = harness.get_all_dashboard_stats()

    # Compute totals
    total_waiting = sum(s.get("waiting", 0) for s in dept_stats.values())
    total_in_progress = sum(s.get("in_progress", 0) for s in dept_stats.values())
    total_completed = sum(s.get("completed", 0) for s in dept_stats.values())
    total_report_ready = sum(s.get("report_ready", 0) for s in dept_stats.values())
    total_delivered = sum(s.get("delivered", 0) for s in dept_stats.values())
    total_today = total_waiting + total_in_progress + total_completed + total_report_ready + total_delivered

    # Gradient summary cards
    metric_colors = [
        ("👥 Total Today", total_today, "linear-gradient(135deg, #667eea, #764ba2)"),
        ("⏳ Waiting", total_waiting, "linear-gradient(135deg, #f093fb, #f5576c)"),
        ("🟠 In Progress", total_in_progress, "linear-gradient(135deg, #4facfe, #00f2fe)"),
        ("✅ Completed", total_completed, "linear-gradient(135deg, #43e97b, #38f9d7)"),
        ("📋 Report Ready", total_report_ready, "linear-gradient(135deg, #fa709a, #fee140)"),
    ]

    cols = st.columns(len(metric_colors))
    for col, (label, value, gradient) in zip(cols, metric_colors):
        with col:
            st.markdown(f"""
            <div class="status-gradient-card" style="background:{gradient};">
                <div style="font-size:2rem;font-weight:700;">{value}</div>
                <div style="font-size:0.9rem;opacity:0.9;">{label}</div>
            </div>
            """, unsafe_allow_html=True)

    st.divider()

    # ─── Department-wise Breakdown ───────────────────────────────────────────
    st.markdown("### 🏥 Department-wise Status")
    st.caption("Click on any department for details")

    dept_icons = {"ECG": "🩺", "Echo": "🔬", "TMT": "🏃", "Holter": "📟", "ABPM": "💓", "OPD": "🩺"}

    for test_name in TEST_TYPES:
        stats = dept_stats.get(test_name, {})
        icon = dept_icons.get(test_name, "📊")

        waiting = stats.get("waiting", 0)
        progress = stats.get("in_progress", 0)
        done = stats.get("completed", 0)
        ready = stats.get("report_ready", 0)

        with st.container(border=True):
            cols = st.columns([0.8, 2, 3, 2.5])

            with cols[0]:
                st.markdown(f"## {icon}")

            with cols[1]:
                st.markdown(f"**{test_name}**")
                st.caption(f"Avg: {AVG_TEST_TIME.get(test_name, 15)} min")

            with cols[2]:
                st.markdown(
                    f"⏳ Waiting: **{waiting}**  \n"
                    f"🟠 In Progress: **{progress}**  \n"
                    f"✅ Completed: **{done}**  \n"
                    f"📋 Report Ready: **{ready}**"
                )

            with cols[3]:
                if waiting > 0:
                    st.info(f"👥 {waiting} patient(s) waiting")
                elif progress > 0:
                    st.info(f"🟠 {progress} in progress")
                elif done > 0:
                    st.success(f"✅ {done} completed")
                elif ready > 0:
                    st.success(f"📋 {ready} report(s) ready")
                else:
                    st.markdown("— No activity —")

    st.divider()

    # ─── Quick Actions: Manager can call/complete patients in any dept ────────
    st.markdown("### ⚡ Department Quick Actions")
    st.caption("Manager can call the next waiting patient or mark the current patient as complete for any department.")

    dept_actions = {
        "ECG": "📊",
        "Echo": "🔬",
        "TMT": "🏃",
        "OPD": "🩺",
    }

    for dept_name, dept_icon in dept_actions.items():
        queue_data = harness.get_department_queue(dept_name)
        dept_current = queue_data["current"]
        dept_waiting = queue_data["waiting"]

        with st.container(border=True):
            cols = st.columns([0.8, 2, 3, 3])
            with cols[0]:
                st.markdown(f"## {dept_icon}")
            with cols[1]:
                st.markdown(f"**{dept_name}**")
                waiting_count = len(dept_waiting)
                st.caption(f"⏳ Waiting: {waiting_count}")

            with cols[2]:
                if dept_current:
                    p = dept_current
                    p_name = p.get("patients", {}).get("name", "Unknown")
                    p_status = p.get("status", "")
                    st.markdown(f"**Current:** {p_name}")
                    st.caption(f"Status: {STATUS_LABELS.get(p_status, p_status)}")

                    if p_status in ["called", "in_progress"]:
                        if st.button(
                            f"✅ Mark Complete — {p_name}",
                            key=f"mgr_complete_{dept_name}",
                            use_container_width=True,
                        ):
                            p_mobile = p.get("patients", {}).get("mobile", "")
                            result = harness.complete_test(
                                p["id"], p_name, dept_name,
                                p_mobile, p.get("patient_id", "")
                            )
                            if result["success"]:
                                st.success(result["message"])
                                if result.get("notification"):
                                    script = harness.get_notification_script(
                                        f"✅ {dept_name} Completed", result["notification"], urgent=True
                                    )
                                    st.markdown(script, unsafe_allow_html=True)
                                st.rerun()
                            else:
                                st.error(result["message"])
                else:
                    st.markdown("— No current patient —")

            with cols[3]:
                if dept_waiting:
                    next_p = dept_waiting[0]
                    p = next_p.get("patients", {})
                    w_name = p.get("name", "Unknown")
                    w_mobile = p.get("mobile", "")
                    token = next_p.get("token_number", 0)
                    st.markdown(f"**Next:** {w_name} (Token #{token})")

                    if st.button(
                        f"🔵 Call — {w_name}",
                        key=f"mgr_call_{dept_name}",
                        type="primary",
                        use_container_width=True,
                    ):
                        result = harness.call_patient(
                            next_p["id"], w_name, dept_name, token,
                            w_mobile, next_p.get("patient_id", "")
                        )
                        if result["success"]:
                            st.success(result["message"])
                            if result.get("notification"):
                                script = harness.get_notification_script(
                                    f"🔵 {dept_name} — Patient Called",
                                    result["notification"], urgent=True
                                )
                                st.markdown(script, unsafe_allow_html=True)
                            st.rerun()
                        else:
                            st.error(result["message"])
                else:
                    st.markdown("✅ No waiting patients")

    st.divider()

    # ─── Today's Recent Patients ─────────────────────────────────────────────
    st.markdown("### 📋 Today's Patients")
    try:
        from utils.db import get_today_patients, get_tests_for_patient
        patients = get_today_patients()
        if patients:
            for p in reversed(patients[-15:]):
                p_id = p.get("patient_id", "")
                tests = get_tests_for_patient(p_id) if p_id else []
                test_names = ", ".join(t.get("test_name", "?") for t in tests) if tests else "—"
                statuses = ", ".join(
                    f"{STATUS_ICONS.get(t.get('status', ''), '❓')} {t.get('status', '?')}"
                    for t in tests
                ) if tests else "No tests"

                with st.expander(
                    f"👤 {p.get('name', 'Unknown')} "
                    f"| 📱 {p.get('mobile', '—')} "
                    f"| 🎫 {p.get('patient_id', '—')}"
                ):
                    cols = st.columns(2)
                    with cols[0]:
                        st.markdown(f"**Age:** {p.get('age', '—')}  |  **Gender:** {p.get('gender', '—')}")
                        st.markdown(f"**Tests:** {test_names}")
                    with cols[1]:
                        st.markdown(f"**Status:** {statuses}")
                        st.caption(f"Registered: {p.get('registration_date', '—')}")
        else:
            st.info("No patients registered today.")
    except Exception as e:
        st.warning(f"Could not load today's patients: {e}")

    # ─── Data Source indicator ───────────────────────────────────────────────
    with st.sidebar:
        st.divider()
        st.markdown("### ℹ️ Manager Dashboard")
        st.markdown("Real-time overview of all departments.")
        try:
            from utils.db import USE_GOOGLE_SHEETS, USE_SUPABASE
            if USE_GOOGLE_SHEETS:
                st.success("☁️ Google Sheets Active")
            elif USE_SUPABASE:
                st.success("☁️ Supabase Cloud Active")
            else:
                st.warning("💾 Local SQLite Mode")
        except Exception:
            pass
