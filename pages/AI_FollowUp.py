"""
AI Follow-up Suggestions — Smart Diagnosis-Based Recommendations
"""
import streamlit as st
from datetime import date, datetime

from utils.config import HOSPITAL_NAME
from utils.ai_followup import (
    suggest_followup, get_pending_suggestions, diagnose_to_followup_days,
)
from llm_harness import get_harness


def show():
    harness = get_harness()
    now = datetime.now().strftime("%d-%b-%Y %I:%M %p")

    st.title("🤖 AI Follow-up Suggestions")
    st.markdown(f"### {HOSPITAL_NAME}")
    st.caption(f"🗓️ {now}")

    tab1, tab2 = st.tabs(["🧠 Suggest Follow-up", "📋 Pending Suggestions"])

    with tab1:
        show_suggest(harness)
    with tab2:
        show_pending()


def show_suggest(harness):
    st.subheader("🧠 AI Follow-up Suggestion")

    with st.form("ai_fu_form"):
        col1, col2 = st.columns(2)
        with col1:
            mobile = st.text_input("Patient Mobile", max_chars=10, placeholder="10-digit")
            name = st.text_input("Patient Name", placeholder="Auto-filled on lookup")
        with col2:
            diagnosis = st.text_area("Diagnosis / Condition", placeholder="e.g., Hypertension, Post-MI, Diabetes",
                                    height=80)

        if st.form_submit_button("🔍 Auto-detect Days", type="secondary"):
            if diagnosis:
                days = diagnose_to_followup_days(diagnosis)
                st.session_state.ai_fu_days = days
                st.info(f"🤖 AI suggests follow-up in **{days} days** ({date.today().isoformat()} → {(date.today() + __import__('datetime').timedelta(days=days)).isoformat()})")
            else:
                st.warning("Enter diagnosis first.")

        col3, col4 = st.columns(2)
        with col3:
            days = st.number_input("Follow-up in (days)", min_value=1, max_value=365,
                                   value=st.session_state.get("ai_fu_days", 14))
        with col4:
            dept = st.text_input("Department", placeholder="e.g., Cardiology")

        priority = st.selectbox("Priority", ["normal", "high", "urgent"])

        if st.form_submit_button("✅ Generate Suggestion", use_container_width=True):
            # Lookup patient
            patient = harness.get_patient_details(mobile, by_mobile=True) if mobile else None
            pid = patient.get("patient_id", "") if patient else ""
            pname = patient.get("name", name) if patient else name

            result = suggest_followup(
                patient_id=pid, patient_name=pname, mobile=mobile,
                diagnosis=diagnosis, suggested_days=days,
                suggested_dept=dept, priority=priority,
            )
            if result["success"]:
                st.success(result["message"])
                st.info(f"📅 Suggested date: {result.get('suggested_date', '')}")
                st.session_state.ai_fu_days = None
                st.rerun()
            else:
                st.error(result["message"])


def show_pending():
    st.subheader("📋 Pending AI Suggestions")
    suggestions = get_pending_suggestions()
    if not suggestions:
        st.success("✅ No pending suggestions.")
        return

    for s in suggestions:
        with st.container(border=True):
            cols = st.columns([2, 1, 1.5, 1])
            with cols[0]:
                st.markdown(f"**{s.get('patient_name', '?')}**")
                st.caption(f"📱 {s.get('mobile', '')} | {s.get('diagnosis', '')[:30]}")
            with cols[1]:
                st.caption(f"Due: {s.get('suggested_days', '?')}d")
            with cols[2]:
                st.caption(f"Priority: {s.get('priority', 'normal')}")
            with cols[3]:
                st.caption(f"Dept: {s.get('suggested_dept', '—')}")
