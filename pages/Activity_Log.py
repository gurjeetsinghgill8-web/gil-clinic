"""
Activity Log — Staff Audit Trail
===================================
Shows recent staff actions (call, complete, remind, report_ready, register)
with timestamps and actor names. Access: Manager and Admin only.
"""
import streamlit as st
from datetime import datetime

from llm_harness import get_harness
from utils.config import HOSPITAL_NAME


ACTIVITY_ICONS = {
    "registration": "🆕",
    "called": "🔵",
    "completed": "✅",
    "report_ready": "📋",
    "reminder": "🔔",
    "misscall": "📞",
}


def show():
    harness = get_harness()
    now = datetime.now()
    today = now.strftime("%d-%b-%Y %I:%M %p")

    st.title("📋 Activity Log")
    st.markdown(f"### {HOSPITAL_NAME} — Staff Audit Trail")
    st.caption(f"🗓️ {today}")

    # ─── Fetch activity ──────────────────────────────────────────────────────
    with st.spinner("Loading activity log..."):
        entries = harness.get_recent_activity(limit=100)

    if not entries:
        st.info("📭 No activity recorded yet. Actions will appear here as staff work.")
        return

    # ─── Summary ─────────────────────────────────────────────────────────────
    total = len(entries)
    action_types = {}
    actors = set()
    for e in entries:
        t = e.get("message_type", "unknown")
        action_types[t] = action_types.get(t, 0) + 1
        a = e.get("actor", "")
        if a:
            actors.add(a)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📝 Total Actions", total)
    with col2:
        st.metric("👤 Unique Staff", len(actors))
    with col3:
        most_common = max(action_types, key=action_types.get) if action_types else "—"
        icon = ACTIVITY_ICONS.get(most_common, "❓")
        st.metric(f"{icon} Most Common", f"{action_types.get(most_common, 0)}× {most_common}")

    st.divider()

    # ─── Activity Feed ───────────────────────────────────────────────────────
    for entry in entries:
        msg_type = entry.get("message_type", "")
        icon = ACTIVITY_ICONS.get(msg_type, "❓")
        msg_text = entry.get("message_text", "")
        actor = entry.get("actor", "System")
        patient_name = entry.get("patient_name", entry.get("patient_id", "—"))
        sent_at_raw = entry.get("sent_at", "")
        try:
            dt = datetime.fromisoformat(sent_at_raw)
            time_str = dt.strftime("%d-%b %I:%M %p").lstrip("0")
        except Exception:
            time_str = sent_at_raw

        # Color-code by type
        border_color = {
            "registration": "#667eea",
            "called": "#3498db",
            "completed": "#00b894",
            "report_ready": "#fdcb6e",
            "reminder": "#e17055",
            "misscall": "#d63031",
        }.get(msg_type, "#ddd")

        with st.container(border=True):
            cols = st.columns([0.5, 3, 1.5])
            with cols[0]:
                st.markdown(
                    f"<div style='font-size:1.5rem;text-align:center;'>{icon}</div>",
                    unsafe_allow_html=True,
                )
            with cols[1]:
                st.markdown(
                    f"<span style='font-weight:600;'>{msg_text[:120]}</span>",
                    unsafe_allow_html=True,
                )
                st.caption(f"👤 {patient_name} &middot; by **{actor}**")
            with cols[2]:
                st.markdown(
                    f"<div style='text-align:right;font-size:0.8rem;color:#888;'>{time_str}</div>",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"<div style='text-align:right;'><span style='background:{border_color};"
                    f"color:white;padding:1px 10px;border-radius:10px;font-size:0.7rem;"
                    f"font-weight:600;'>{msg_type}</span></div>",
                    unsafe_allow_html=True,
                )

    # ─── Footer ───────────────────────────────────────────────────────────────
    st.divider()
    st.caption(f"🔍 Showing last {total} actions")
