"""
AI Triage Dashboard — Symptom Assessment & Severity Classification
"""
import streamlit as st
from datetime import datetime

from utils.config import HOSPITAL_NAME
from utils.ai_triage import (
    assess_symptoms, get_triage_history, get_triage_stats,
    TRIAGE_LEVELS,
)


def show():
    now = datetime.now().strftime("%d-%b-%Y %I:%M %p")

    st.title("🤖 AI Triage")
    st.markdown(f"### {HOSPITAL_NAME}")
    st.caption(f"🗓️ {now} ⚕️ Decision Support Only — Not a Diagnostic Tool")

    tab1, tab2 = st.tabs(["🔍 Assess Symptoms", "📋 History"])

    with tab1:
        show_assessment()
    with tab2:
        show_history()


def show_assessment():
    st.subheader("🔍 Symptom Assessment")

    with st.form("triage_form"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Patient Name", placeholder="Optional")
            age = st.number_input("Age", min_value=0, max_value=120, value=30)
        with col2:
            gender = st.selectbox("Gender", ["", "Male", "Female", "Other"])
            pid = st.text_input("Patient ID", placeholder="Optional")

        chief = st.text_area("🚨 Chief Complaint *", placeholder="e.g., Chest pain since 2 hours",
                            height=80)
        symptoms = st.text_area("Additional Symptoms", placeholder="Describe all symptoms in detail",
                               height=100)

        st.info("⚠️ This is an AI-assisted decision support tool. Always consult a doctor for final diagnosis.")

        submitted = st.form_submit_button("🔍 Assess", type="primary", use_container_width=True)
        if submitted:
            if not chief.strip():
                st.error("Chief complaint is required.")
            else:
                with st.spinner("🤖 Analyzing symptoms..."):
                    result = assess_symptoms(
                        chief_complaint=chief, symptoms=symptoms,
                        patient_name=name, age=age, gender=gender,
                        patient_id=pid,
                    )

                if result["success"]:
                    sev = result["severity"]
                    sev_info = result["severity_info"]
                    color = sev_info.get("color", "#666")

                    st.markdown(f"""
                    <div style="background:linear-gradient(135deg,{color}20,{color}08);
                                border:2px solid {color};border-radius:12px;padding:1.5rem;margin:1rem 0;">
                        <h3 style="color:{color};margin:0;">{sev_info.get('label', sev)}</h3>
                        <p style="font-size:1.1rem;"><strong>Response Time:</strong> {sev_info.get('wait_time', '')}</p>
                        <p><strong>Confidence:</strong> {result.get('confidence', 0)*100:.0f}%</p>
                        <p><strong>Recommended Department:</strong> {result.get('recommended_dept', 'General Medicine')}</p>
                        <p><strong>ICD-10 Code:</strong> {result.get('icd10_code', '—')}</p>
                    </div>
                    """, unsafe_allow_html=True)

                    if result.get("red_flags"):
                        st.error(f"🚨 Red Flag Detected: {', '.join(result['red_flags'])}")

                    if result.get("is_escalated"):
                        st.warning("⚠️ This case has been escalated for immediate doctor review.")

                    if sev in ("1-Emergency", "2-Urgent"):
                        st.error("🚑 **Emergency!** Call 108 immediately or rush to nearest hospital.")
                        st.markdown("""
                        <div style="background:#FF5722;color:white;padding:1rem;border-radius:8px;text-align:center;font-size:1.2rem;font-weight:bold;">
                            🚑 DIAL 108 — EMERGENCY
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.error(result["message"])


def show_history():
    st.subheader("📋 Triage History")
    history = get_triage_history()
    if not history:
        st.info("No assessments yet.")
        return

    for h in history:
        sev = h.get("severity", "")
        info = TRIAGE_LEVELS.get(sev, {})
        color = info.get("color", "#666")
        with st.container(border=True):
            cols = st.columns([2, 1.5, 1.5, 2])
            with cols[0]:
                st.markdown(f"**{h.get('patient_name', 'Anonymous')}**")
                st.caption(h.get('created_at', '')[:19])
            with cols[1]:
                st.markdown(f"<span style='color:{color};font-weight:bold;'>{info.get('label', sev)}</span>",
                            unsafe_allow_html=True)
            with cols[2]:
                st.caption(f"Dept: {h.get('recommended_dept', '—')}")
            with cols[3]:
                st.caption(f"ICD-10: {h.get('icd10_code', '—')}")
