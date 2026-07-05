"""
Department Base — Shared Dashboard for ECG / Echo / TMT / OPD
===============================================================
All technician dashboards share the same layout:
  - Stats row with gradient metric cards
  - Current Patient card with actions
  - Waiting List with call/start/complete buttons
  - Auto-refresh every 5 seconds

Each department page calls this with its test_name.
"""
import streamlit as st
from datetime import datetime

from llm_harness import get_harness
from utils.config import HOSPITAL_NAME, STATUS_ICONS, STATUS_LABELS, AVG_TEST_TIME


def show_department(test_name: str, emoji: str = "📊"):
    """
    Render a modern department dashboard for a given test type.

    Parameters:
        test_name (str): One of "ECG", "Echo", "TMT", "OPD"
        emoji (str): Icon for the department
    """
    harness = get_harness()
    now = datetime.now()
    today = now.strftime("%d-%b-%Y %I:%M %p")

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

    # ─── Modern Stats Row ────────────────────────────────────────────────
    st.markdown("### 📊 Today's Status")

    stat_configs = [
        ("🟡 Waiting", "waiting", "#FF9800"),
        ("🔵 Called", "called", "#2196F3"),
        ("🟠 In Progress", "in_progress", "#FF5722"),
        ("✅ Completed", "completed", "#4CAF50"),
        ("📋 Report Ready", "report_ready", "#9C27B0"),
    ]

    cols = st.columns(len(stat_configs))
    for col, (label, key, color) in zip(cols, stat_configs):
        with col:
            value = stats.get(key, 0)
            st.markdown(f"""
            <div class="dept-metric-card" style="border-top: 3px solid {color};">
                <div class="value" style="color: {color};">{value}</div>
                <div class="label">{label}</div>
            </div>
            """, unsafe_allow_html=True)

    st.divider()

    # ─── Current Patient ─────────────────────────────────────────────────
    st.subheader("🟢 Current Patient")

    if current:
        p = current
        p_name = p.get("patients", {}).get("name", "Unknown")
        p_mobile = p.get("patients", {}).get("mobile", "")
        p_age = p.get("patients", {}).get("age", "")
        token = p.get("token_number", 0)
        current_status = p.get("status", "called")
        status_display = f"{STATUS_ICONS.get(current_status, '❓')} {STATUS_LABELS.get(current_status, current_status)}"

        # Color based on status
        status_colors = {
            "called": "#2196F3",
            "in_progress": "#FF5722",
            "completed": "#4CAF50",
        }
        border_color = status_colors.get(current_status, "#667eea")

        st.markdown(f"""
        <div style="background:linear-gradient(135deg,#667eea08,#764ba208);
                    border:2px solid {border_color}40;border-radius:12px;
                    padding:1rem 1.25rem;margin-bottom:1rem;">
            <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:0.5rem;">
                <div>
                    <span style="font-size:1.2rem;font-weight:700;">{p_name}</span>
                    <span style="color:#636e72;margin-left:0.5rem;font-size:0.9rem;">
                        Token #{token} | 📱 {p_mobile} | Age: {p_age}
                    </span>
                </div>
                <div style="font-size:1.1rem;font-weight:600;">{status_display}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Action buttons
        cols = st.columns([1, 1, 1, 1, 1])

        with cols[0]:
            if current_status == "called":
                if st.button("▶️ Start", key=f"start_{p['id']}",
                             type="primary", use_container_width=True):
                    result = harness.start_test(p["id"])
                    if result["success"]:
                        st.success(result["message"])
                        st.rerun()
                    else:
                        st.error(result["message"])

        with cols[1]:
            if current_status in ["called", "in_progress"]:
                btn_label = "✅ Complete" if current_status == "in_progress" else "❌ Skip"
                if st.button(btn_label, key=f"complete_{p['id']}",
                             use_container_width=True):
                    result = harness.complete_test(
                        p["id"], p_name, test_name, p_mobile, p.get("patient_id", "")
                    )
                    if result["success"]:
                        st.success(result["message"])
                        if result.get("notification"):
                            script = harness.get_notification_script(
                                f"✅ {test_name} Completed", result["notification"], urgent=True
                            )
                            st.markdown(script, unsafe_allow_html=True)
                        st.rerun()
                    else:
                        st.error(result["message"])

        with cols[2]:
            # 🔔 Reminder button — always visible for current patient
            if st.button("🔔 Remind", key=f"remind_curr_{p['id']}",
                         use_container_width=True):
                result = harness.send_reminder(
                    p_name, test_name, p_mobile, token
                )
                if result["success"]:
                    st.success(result["message"])
                    if result.get("notification"):
                        script = harness.get_notification_script(
                            f"🔔 Reminder — {test_name}",
                            result["notification"], urgent=True
                        )
                        st.markdown(script, unsafe_allow_html=True)

        with cols[3]:
            # 📞 Miss Call Alert — works without notification permission
            if st.button("📞 Miss Call", key=f"misscall_curr_{p['id']}",
                         use_container_width=True,
                         help="Sends alert to patient page WITHOUT needing notification permission."):
                p_id_full = p.get("patient_id", "")
                result = harness.send_misscall_alert(p_name, test_name, token, patient_id=p_id_full)
                if result["success"]:
                    st.success(result["message"])
                    misscall_url = result.get("misscall_url", "")
                    if misscall_url:
                        st.info(f"📤 [Open Miss Call on Patient Page]({misscall_url})")

        with cols[4]:
            called_time = p.get("called_at", "")
            if called_time:
                try:
                    ct = datetime.fromisoformat(called_time.replace("Z", "+00:00"))
                    elapsed = (datetime.utcnow() - ct.replace(tzinfo=None)).seconds // 60
                    st.info(f"⏱️ {elapsed} min ago")
                except Exception:
                    pass
    else:
        st.info(f"👀 No patient currently being served in {test_name}.")

    st.divider()

    # ─── Waiting List ────────────────────────────────────────────────────
    st.subheader("⏳ Waiting List")
    st.caption(f"{len(waiting)} patient(s) waiting")

    if waiting:
        for w in waiting:
            p = w.get("patients", {})
            w_name = p.get("name", "Unknown")
            w_mobile = p.get("mobile", "")
            w_age = p.get("age", "")
            token = w.get("token_number", 0)
            pos = w.get("queue_position", 0)

            from utils.queue import calculate_wait_time
            wait_time = calculate_wait_time(test_name, pos)

            with st.container(border=True):
                cols = st.columns([2, 1, 1, 1, 1, 1])

                with cols[0]:
                    st.markdown(f"**{w_name}** — Token #{token}")
                    st.caption(f"📱 {w_mobile} | Age: {w_age}")

                with cols[1]:
                    st.markdown(f"⏱️ ~**{wait_time} min**")
                    st.caption(f"Position: #{pos}")

                with cols[2]:
                    if st.button("🔵 Call", key=f"call_{w['id']}",
                                 type="primary", use_container_width=True):
                        result = harness.call_patient(
                            w["id"], w_name, test_name, token,
                            w_mobile, w.get("patient_id", "")
                        )
                        if result["success"]:
                            st.success(result["message"])
                            if result.get("notification"):
                                script = harness.get_notification_script(
                                    f"🔵 {test_name} — Patient Called",
                                    result["notification"], urgent=True
                                )
                                st.markdown(script, unsafe_allow_html=True)
                            st.rerun()
                        else:
                            st.error(result["message"])

                with cols[3]:
                    if st.button("🔔 Remind", key=f"remind_{w['id']}",
                                 use_container_width=True):
                        result = harness.send_reminder(
                            w_name, test_name, w_mobile, token
                        )
                        if result["success"]:
                            st.success(result["message"])
                            if result.get("notification"):
                                script = harness.get_notification_script(
                                    f"🔔 Reminder — {test_name}",
                                    result["notification"], urgent=True
                                )
                                st.markdown(script, unsafe_allow_html=True)

                with cols[4]:
                    # 📞 Miss Call Alert
                    if st.button("📞 Miss Call", key=f"misscall_{w['id']}",
                                 use_container_width=True,
                                 help="Sends alert without notification permission."):
                        w_patient_id = w.get("patient_id", "")
                        result = harness.send_misscall_alert(w_name, test_name, token, patient_id=w_patient_id)
                        if result["success"]:
                            st.success(result["message"])
                            misscall_url = result.get("misscall_url", "")
                            if misscall_url:
                                st.info(f"📤 [Open Miss Call on Patient Page]({misscall_url})")

                with cols[5]:
                    registered_time = w.get("created_at", "")
                    if registered_time:
                        try:
                            rt = datetime.fromisoformat(registered_time.replace("Z", "+00:00"))
                            elapsed = (datetime.utcnow() - rt.replace(tzinfo=None)).seconds // 60
                            st.caption(f"⏳ {elapsed} min")
                        except Exception:
                            pass
    else:
        st.success(f"✅ No patients waiting for {test_name}.")

    # ─── Sidebar Info ────────────────────────────────────────────────────
    with st.sidebar:
        st.divider()
        st.markdown("### ℹ️ Quick Info")
        st.markdown(f"**Department:** {test_name}")
        st.markdown(f"**Avg. time:** {AVG_TEST_TIME.get(test_name, 15)} min")
        st.markdown(f"**Room:** {test_name} Room 1")
        st.markdown(f"**Patients today:** {sum(stats.values())}")
