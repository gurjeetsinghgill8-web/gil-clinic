"""
Manager Dashboard — Full Clinic Overview
==========================================
Real-time view of all departments, patient counts, and status flow.
Access: Manager role only (password: manager123 / env: MANAGER_PASS)
"""
import streamlit as st
from datetime import datetime

from llm_harness import get_harness
from utils.config import HOSPITAL_NAME, TEST_TYPES, STATUS_ICONS, STATUS_LABELS, AVG_TEST_TIME


def show():
    harness = get_harness()
    today = datetime.now().strftime("%d-%b-%Y %I:%M %p")

    st.title("📈 Manager Dashboard")
    st.subheader(f"{HOSPITAL_NAME} — Cardiology Department")
    st.caption(f"🗓️ {today}")

    # ─── Summary Cards ───────────────────────────────────────────────────────
    st.markdown("### 📊 Overall Status")

    dept_stats = harness.get_all_dashboard_stats()

    # Compute totals
    total_waiting = sum(s.get("waiting", 0) for s in dept_stats.values())
    total_in_progress = sum(s.get("in_progress", 0) for s in dept_stats.values())
    total_completed = sum(s.get("completed", 0) for s in dept_stats.values())
    total_report_ready = sum(s.get("report_ready", 0) for s in dept_stats.values())
    total_delivered = sum(s.get("delivered", 0) for s in dept_stats.values())
    total_today = total_waiting + total_in_progress + total_completed + total_report_ready + total_delivered

    cols = st.columns(5)
    with cols[0]:
        st.metric("👥 Total Today", total_today)
    with cols[1]:
        st.metric("⏳ Waiting", total_waiting)
    with cols[2]:
        st.metric("🟠 In Progress", total_in_progress)
    with cols[3]:
        st.metric("✅ Completed", total_completed)
    with cols[4]:
        st.metric("📋 Report Ready", total_report_ready)

    st.divider()

    # ─── Department-wise Breakdown ───────────────────────────────────────────
    st.markdown("### 🏥 Department-wise Status")

    for test_name in TEST_TYPES:
        stats = dept_stats.get(test_name, {})
        with st.container(border=True):
            icon_map = {"ECG": "🩺", "Echo": "🔬", "TMT": "🏃", "Holter": "📟", "ABPM": "💓", "OPD": "🩺"}
            icon = icon_map.get(test_name, "📊")

            cols = st.columns([1, 3, 3, 3])

            with cols[0]:
                st.markdown(f"## {icon}")

            with cols[1]:
                st.markdown(f"**{test_name}**")
                st.caption(f"Avg: {AVG_TEST_TIME.get(test_name, 15)} min")
                st.caption(f"Room: {test_name} Room 1")

            with cols[2]:
                waiting = stats.get("waiting", 0)
                progress = stats.get("in_progress", 0)
                done = stats.get("completed", 0)
                ready = stats.get("report_ready", 0)
                st.markdown(
                    f"⏳ Waiting: **{waiting}**  \n"
                    f"🟠 In Progress: **{progress}**  \n"
                    f"✅ Completed: **{done}**  \n"
                    f"📋 Report Ready: **{ready}**"
                )

            with cols[3]:
                # Quick action info
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

    # ─── Today's Recent Patients ─────────────────────────────────────────────
    st.markdown("### 📋 Today's Patients")
    try:
        from utils.db import get_today_patients, get_tests_for_patient
        patients = get_today_patients()
        if patients:
            for p in reversed(patients[-15:]):  # Latest 15
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
