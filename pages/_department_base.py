"""
Department Base — Shared Dashboard for ECG / Echo / TMT
=========================================================
All three technician dashboards share the same layout:
  - Current Patient card (called or in_progress)
  - Waiting List table
  - Action buttons: Call → Start → Complete
  - Auto-refresh

Each department page calls this with its test_name.
"""
import streamlit as st
from datetime import datetime

from llm_harness import get_harness
from utils.config import HOSPITAL_NAME, STATUS_ICONS, STATUS_LABELS, AVG_TEST_TIME
from utils.queue import calculate_wait_time


def show_department(test_name: str, emoji: str = "📊"):
    """
    Render a department dashboard for a given test type.

    Parameters:
        test_name (str): One of "ECG", "Echo", "TMT"
        emoji (str): Icon for the department
    """
    harness = get_harness()
    today = datetime.now().strftime("%d-%b-%Y %I:%M %p")

    st.title(f"{emoji} {test_name} Dashboard")
    st.caption(f"{HOSPITAL_NAME} — {today}")

    # Auto-refresh every 5 seconds
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=5000, key=f"refresh_{test_name}")
    except ImportError:
        pass

    # Get queue data
    queue_data = harness.get_department_queue(test_name)
    current = queue_data["current"]
    waiting = queue_data["waiting"]
    stats = queue_data["stats"]

    # ─── Stats Row ───────────────────────────────────────────────────────────
    stat_cols = st.columns(5)
    stat_labels = [
        ("🟡 Waiting", "waiting"),
        ("🔵 Called", "called"),
        ("🟠 In Progress", "in_progress"),
        ("✅ Completed", "completed"),
        ("📋 Report Ready", "report_ready"),
    ]
    for col, (label, key) in zip(stat_cols, stat_labels):
        with col:
            st.metric(label, stats.get(key, 0))

    st.divider()

    # ─── Current Patient ─────────────────────────────────────────────────────
    st.subheader("🟢 Current Patient")

    if current:
        p = current
        p_name = p.get("patients", {}).get("name", "Unknown")
        p_mobile = p.get("patients", {}).get("mobile", "")
        p_age = p.get("patients", {}).get("age", "")
        token = p.get("token_number", 0)
        current_status = p.get("status", "called")
        status_display = f"{STATUS_ICONS.get(current_status, '❓')} {STATUS_LABELS.get(current_status, current_status)}"

        with st.container(border=True):
            cols = st.columns([2, 1, 1, 1, 1])

            with cols[0]:
                st.markdown(f"### {p_name}")
                st.caption(f"Token #{token} | Mobile: {p_mobile} | Age: {p_age}")

            with cols[1]:
                st.markdown(f"**Status**")
                st.markdown(f"### {status_display}")

            with cols[2]:
                if current_status == "called":
                    if st.button("▶️ Start", key=f"start_{p['id']}",
                                 type="primary", use_container_width=True):
                        result = harness.start_test(p["id"])
                        if result["success"]:
                            st.success(result["message"])
                            st.rerun()
                        else:
                            st.error(result["message"])

            with cols[3]:
                if current_status in ["called", "in_progress"]:
                    btn_label = "✅ Complete" if current_status == "in_progress" else "❌ Complete (skip)"
                    if st.button(btn_label, key=f"complete_{p['id']}",
                                 use_container_width=True):
                        result = harness.complete_test(
                            p["id"], p_name, test_name, p_mobile, p.get("patient_id", "")
                        )
                        if result["success"]:
                            st.success(result["message"])
                            # Trigger urgent notification with sound + vibration
                            if result.get("notification"):
                                script = harness.get_notification_script(
                                    f"✅ {test_name} Completed", result["notification"],
                                    urgent=True
                                )
                                st.markdown(script, unsafe_allow_html=True)
                            st.rerun()
                        else:
                            st.error(result["message"])

            with cols[4]:
                called_time = p.get("called_at", "")
                if called_time:
                    try:
                        ct = datetime.fromisoformat(called_time.replace("Z", "+00:00"))
                        elapsed = (datetime.utcnow() - ct.replace(tzinfo=None)).seconds // 60
                        st.markdown(f"**⏱️ {elapsed} min**")
                    except Exception:
                        pass
    else:
        st.info(f"👀 No patient currently being served in {test_name}.")

    st.divider()

    # ─── Waiting List ────────────────────────────────────────────────────────
    st.subheader("⏳ Waiting List")

    if waiting:
        for w in waiting:
            p = w.get("patients", {})
            w_name = p.get("name", "Unknown")
            w_mobile = p.get("mobile", "")
            w_age = p.get("age", "")
            token = w.get("token_number", 0)
            pos = w.get("queue_position", 0)
            wait_time = calculate_wait_time(test_name, pos)

            with st.container(border=True):
                cols = st.columns([2, 1, 1, 1])

                with cols[0]:
                    st.markdown(f"**{w_name}** — Token #{token}")
                    st.caption(f"Mobile: {w_mobile} | Age: {w_age}")

                with cols[1]:
                    st.markdown(f"⏱️ Est. wait: **{wait_time} min**")
                    st.markdown(f"Position: #{pos}")

                with cols[2]:
                    if st.button("🔵 Call Patient", key=f"call_{w['id']}",
                                 type="primary", use_container_width=True):
                        result = harness.call_patient(
                            w["id"], w_name, test_name, token,
                            w_mobile, w.get("patient_id", "")
                        )
                        if result["success"]:
                            st.success(result["message"])
                            # Trigger urgent notification with sound + vibration
                            if result.get("notification"):
                                script = harness.get_notification_script(
                                    f"🔵 {test_name} — Patient Called",
                                    result["notification"],
                                    urgent=True
                                )
                                st.markdown(script, unsafe_allow_html=True)
                            st.rerun()
                        else:
                            st.error(result["message"])

                with cols[3]:
                    registered_time = w.get("created_at", "")
                    if registered_time:
                        try:
                            rt = datetime.fromisoformat(registered_time.replace("Z", "+00:00"))
                            elapsed = (datetime.utcnow() - rt.replace(tzinfo=None)).seconds // 60
                            st.caption(f"Waiting: {elapsed} min")
                        except Exception:
                            pass
    else:
        st.info(f"✅ No patients waiting for {test_name}.")

    # ─── Sidebar Info ────────────────────────────────────────────────────────
    with st.sidebar:
        st.divider()
        st.markdown("### ℹ️ Quick Info")
        st.markdown(f"**Department:** {test_name}")
        st.markdown(f"**Avg. time:** {AVG_TEST_TIME.get(test_name, 15)} min")
        st.markdown(f"**Room:** {test_name} Room 1")
        st.markdown(f"**Patients today:** {sum(stats.values())}")
