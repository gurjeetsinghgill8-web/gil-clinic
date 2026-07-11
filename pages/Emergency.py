"""
Emergency / Casualty Dashboard — Triage, Queue, Disposition
"""
import streamlit as st
from datetime import datetime

from llm_harness import get_harness
from utils.config import HOSPITAL_NAME
from utils.emergency import (
    register_emergency, get_emergency_queue, update_emergency_status,
    get_emergency_stats, TRIAGE_LEVELS, CASE_STATUSES, DISPOSITIONS,
)


def show():
    harness = get_harness()
    now = datetime.now().strftime("%d-%b-%Y %I:%M %p")

    st.title("🚑 Emergency / Casualty")
    st.markdown(f"### {HOSPITAL_NAME}")
    st.caption(f"🗓️ {now}")

    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=10000, key="refresh_er")
    except ImportError:
        pass

    stats = get_emergency_stats()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("🟥 Waiting", stats.get("waiting", 0), delta_color="inverse")
    with col2:
        st.metric("🟦 In Treatment", stats.get("in_treatment", 0))
    with col3:
        st.metric("📋 Today Total", stats.get("today", 0))

    st.divider()

    tab1, tab2 = st.tabs(["🚑 Emergency Queue", "➕ New Case"])

    with tab1:
        show_queue()
    with tab2:
        show_new_case(harness)


def show_queue():
    st.subheader("🚑 Emergency Queue (Priority Sorted)")
    cases = get_emergency_queue()
    if not cases:
        st.success("✅ No active emergency cases.")
        return

    for c in cases:
        triage = c.get("triage_level", "")
        t_color = "#FF5722" if "1-Emergency" in triage else "#FF9800" if "2-Urgent" in triage else "#2196F3" if "3-Moderate" in triage else "#4CAF50"
        with st.container(border=True):
            cols = st.columns([2.5, 1.5, 1.5, 1.5, 2])
            with cols[0]:
                st.markdown(f"**{c.get('patient_name', '?')}**")
                st.caption(f"{c.get('age', '')}y {c.get('gender', '')} | {c.get('mobile', '')}")
            with cols[1]:
                st.markdown(f"<span style='color:{t_color};font-weight:bold;'>{triage}</span>",
                            unsafe_allow_html=True)
                st.caption(c.get('chief_complaint', '')[:30])
            with cols[2]:
                vitals = f"BP:{c.get('bp','—')} P:{c.get('pulse','—')}"
                st.caption(vitals)
                st.caption(f"SpO₂:{c.get('spo2','—')} Temp:{c.get('temperature','—')}")
            with cols[3]:
                status = c.get("status", "")
                st.caption(f"Status: {status}")
                if status == "waiting":
                    st.markdown("<span style='color:#FF5722;'>⏳ Waiting</span>", unsafe_allow_html=True)
            with cols[4]:
                col_a, col_b = st.columns(2)
                with col_a:
                    if status == "waiting":
                        if st.button("🩺 Treat", key=f"treat_{c['id']}", use_container_width=True):
                            update_emergency_status(c["id"], "in_treatment",
                                                   attending_doctor=st.session_state.get("auth_name", ""))
                            st.rerun()
                with col_b:
                    if status == "in_treatment":
                        if st.button("✅ Done", key=f"done_{c['id']}", use_container_width=True):
                            update_emergency_status(c["id"], "discharged", disposition="discharged")
                            st.rerun()

            if status == "in_treatment":
                st.divider()
                cols_d = st.columns(3)
                with cols_d[0]:
                    disposition = st.selectbox("Disposition", DISPOSITIONS, key=f"disp_{c['id']}")
                with cols_d[1]:
                    notes = st.text_area("Notes", key=f"er_notes_{c['id']}", height=60, label_visibility="collapsed",
                                        placeholder="Discharge notes / referral info")
                with cols_d[2]:
                    if st.button("✅ Complete Case", key=f"complete_{c['id']}", type="primary", use_container_width=True):
                        update_emergency_status(c["id"], "discharged", disposition=disposition, notes=notes)
                        st.rerun()


def show_new_case(harness):
    st.subheader("➕ New Emergency Case")

    with st.form("er_case_form"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Patient Name *", placeholder="Full name")
            age = st.number_input("Age", min_value=0, max_value=120, value=30)
            mobile = st.text_input("Mobile", max_chars=10, placeholder="10-digit")
        with col2:
            gender = st.selectbox("Gender", ["Male", "Female", "Other"])
            triage = st.selectbox("Triage Level", TRIAGE_LEVELS,
                                 format_func=lambda x: {"1-Emergency": "🔴 1-Emergency", "2-Urgent": "🟠 2-Urgent",
                                                        "3-Moderate": "🔵 3-Moderate", "4-Mild": "🟢 4-Mild",
                                                        "5-Non-urgent": "⚪ 5-Non-urgent"}.get(x, x))
            complaint = st.text_area("Chief Complaint *", placeholder="e.g., Chest pain, difficulty breathing")

        st.markdown("**Vitals (optional)**")
        col_v1, col_v2, col_v3, col_v4 = st.columns(4)
        with col_v1:
            bp = st.text_input("BP", placeholder="120/80")
        with col_v2:
            pulse = st.text_input("Pulse", placeholder="72")
        with col_v3:
            spo2 = st.text_input("SpO₂", placeholder="98")
        with col_v4:
            temp = st.text_input("Temperature", placeholder="98.6")

        symptoms = st.text_area("Symptoms Details", placeholder="Describe symptoms in detail...")

        submitted = st.form_submit_button("🚑 Register Emergency Case", type="primary", use_container_width=True)
        if submitted:
            if not name or not complaint:
                st.error("Patient name and chief complaint are required.")
            else:
                result = register_emergency(
                    patient_name=name, mobile=mobile, age=age, gender=gender,
                    chief_complaint=complaint, triage_level=triage, symptoms=symptoms,
                    bp=bp, pulse=pulse, spo2=spo2, temperature=temp,
                )
                if result["success"]:
                    st.success(result["message"])
                    st.balloons()
                else:
                    st.error(result["message"])
