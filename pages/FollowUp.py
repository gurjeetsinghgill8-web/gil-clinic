"""
Follow-up Scheduling Dashboard — Schedule, Track, Manage Follow-ups
"""
import streamlit as st
from datetime import date, datetime, timedelta

from llm_harness import get_harness
from utils.config import HOSPITAL_NAME
from utils.followup import (
    schedule_followup, get_today_followups, get_pending_followups,
    update_followup_status, get_missed_followups, get_followups_for_patient,
    record_outcome, FOLLOWUP_TYPES, RECURRENCE_PATTERNS,
)


def show():
    harness = get_harness()
    now = datetime.now().strftime("%d-%b-%Y %I:%M %p")

    st.title("📅 Follow-up Scheduling")
    st.markdown(f"### {HOSPITAL_NAME}")
    st.caption(f"🗓️ {now}")

    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=15000, key="refresh_fu")
    except ImportError:
        pass

    tab1, tab2, tab3, tab4 = st.tabs(["📅 Today", "📋 Upcoming", "➕ Schedule New", "⚠️ Missed"])

    with tab1:
        show_today()
    with tab2:
        show_upcoming()
    with tab3:
        show_schedule(harness)
    with tab4:
        show_missed()


def show_today():
    st.subheader(f"📅 Today's Follow-ups ({date.today().isoformat()})")
    followups = get_today_followups()
    if not followups:
        st.success("✅ No follow-ups scheduled for today.")
        return

    for fu in followups:
        with st.container(border=True):
            cols = st.columns([2, 1.5, 1.5, 1, 1.5])
            with cols[0]:
                st.markdown(f"**{fu.get('patient_name', '?')}**")
                st.caption(f"{fu.get('mobile', '')} | Dr. {fu.get('doctor_name', '')}")
            with cols[1]:
                ftype = fu.get("followup_type", "")
                st.markdown(FOLLOWUP_TYPES.get(ftype, ftype))
            with cols[2]:
                st.caption(f"Time: {fu.get('scheduled_time', '10:00')}")
            with cols[3]:
                status = fu.get("status", "")
                icon = {"scheduled": "🟡", "confirmed": "🔵", "reminded": "🟠", "attended": "✅", "missed": "❌"}.get(status, "⬜")
                st.markdown(f"{icon} {status}")
            with cols[4]:
                if status in ("scheduled", "reminded", "confirmed"):
                    if st.button("✅ Attended", key=f"att_{fu['id']}", use_container_width=True):
                        update_followup_status(fu["id"], "attended")
                        st.rerun()


def show_upcoming():
    st.subheader("📋 Upcoming Follow-ups (Next 7 Days)")
    days = st.slider("Days ahead", 1, 30, 7, key="fu_days")
    followups = get_pending_followups(days)
    if not followups:
        st.success(f"✅ No follow-ups in next {days} days.")
        return

    for fu in followups:
        with st.container(border=True):
            cols = st.columns([2, 1.5, 1, 1, 1.5])
            with cols[0]:
                st.markdown(f"**{fu.get('patient_name', '?')}**")
                st.caption(fu.get('mobile', ''))
            with cols[1]:
                st.caption(f"📅 {fu.get('scheduled_date', '')[:10]}")
            with cols[2]:
                st.caption(FOLLOWUP_TYPES.get(fu.get("followup_type", ""), ""))
            with cols[3]:
                st.caption(f"Dr. {fu.get('doctor_name', '')}")
            with cols[4]:
                if st.button("✅ Mark Attended", key=f"up_att_{fu['id']}", use_container_width=True):
                    update_followup_status(fu["id"], "attended")
                    st.rerun()


def show_schedule(harness):
    st.subheader("➕ Schedule New Follow-up")

    with st.form("schedule_fu_form"):
        col1, col2 = st.columns(2)
        with col1:
            mobile = st.text_input("Patient Mobile", max_chars=10, placeholder="10-digit mobile")
        with col2:
            if st.form_submit_button("🔍 Lookup", type="secondary"):
                patient = harness.get_patient_details(mobile, by_mobile=True)
                if patient:
                    st.session_state.fu_patient = patient
                else:
                    st.error("Patient not found.")

    patient = st.session_state.get("fu_patient")
    if not patient:
        st.info("Search for a patient first.")
        return

    st.success(f"✅ {patient.get('name', '')} ({patient.get('patient_id', '')})")

    with st.form("schedule_form"):
        col1, col2 = st.columns(2)
        with col1:
            ftype = st.selectbox("Follow-up Type", list(FOLLOWUP_TYPES.keys()),
                                 format_func=lambda x: FOLLOWUP_TYPES[x])
            doctor = st.text_input("Doctor Name", value=st.session_state.get("auth_name", ""))
        with col2:
            sched_date = st.date_input("Scheduled Date", min_value=date.today())
            recurrence = st.selectbox("Recurrence", RECURRENCE_PATTERNS)

        notes = st.text_area("Notes / Instructions", placeholder="e.g., Bring previous reports")

        if st.form_submit_button("✅ Schedule Follow-up", use_container_width=True):
            result = schedule_followup(
                patient_id=patient.get("patient_id", ""),
                patient_name=patient.get("name", ""),
                mobile=patient.get("mobile", ""),
                doctor_name=doctor,
                followup_type=ftype,
                scheduled_date=sched_date.isoformat(),
                notes=notes,
                recurrence=recurrence,
            )
            if result["success"]:
                st.success(result["message"])
                st.session_state.fu_patient = None
                st.rerun()
            else:
                st.error(result["message"])


def show_missed():
    st.subheader("⚠️ Missed / Overdue Follow-ups")
    missed = get_missed_followups()
    if not missed:
        st.success("✅ No missed follow-ups.")
        return

    for fu in missed:
        with st.container(border=True):
            cols = st.columns([2, 1.5, 1, 1.5, 1.5])
            with cols[0]:
                st.markdown(f"**{fu.get('patient_name', '?')}**")
                st.caption(fu.get('mobile', ''))
            with cols[1]:
                sched = fu.get('scheduled_date', '')[:10]
                days_overdue = (date.today() - date.fromisoformat(sched)).days if sched else 0
                st.markdown(f"<span style='color:#FF5722;'>📅 {sched} ({days_overdue}d overdue)</span>",
                            unsafe_allow_html=True)
            with cols[2]:
                st.caption(FOLLOWUP_TYPES.get(fu.get("followup_type", ""), ""))
            with cols[3]:
                if st.button("✅ Mark Attended", key=f"mis_att_{fu['id']}", use_container_width=True):
                    update_followup_status(fu["id"], "attended")
                    st.rerun()
            with cols[4]:
                if st.button("❌ Cancel", key=f"mis_can_{fu['id']}", use_container_width=True):
                    update_followup_status(fu["id"], "cancelled")
                    st.rerun()
