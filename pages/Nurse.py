"""
Nurse Station Dashboard — Patient Queue Management, Vital Recording
"""
import streamlit as st
from datetime import datetime

from llm_harness import get_harness
from utils.config import HOSPITAL_NAME


def show():
    harness = get_harness()
    now = datetime.now().strftime("%d-%b-%Y %I:%M %p")

    st.title("👩‍⚕️ Nurse Station")
    st.markdown(f"### {HOSPITAL_NAME}")
    st.caption(f"🗓️ {now}")

    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=10000, key="refresh_nurse")
    except ImportError:
        pass

    tab1, tab2 = st.tabs(["📋 Patient Queue", "🩺 Record Vitals"])

    with tab1:
        show_queue(harness)
    with tab2:
        show_vitals(harness)


def show_queue(harness):
    st.subheader("📋 All Today's Patients")
    tests = harness.get_reception_queue()
    waiting = [t for t in tests if t.get("status") in ("waiting", "called")]
    if not waiting:
        st.success("✅ No patients waiting.")
        return

    for t in waiting:
        p = t.get("patients", {})
        name = p.get("name", "?")
        mobile = p.get("mobile", "")
        test_name = t.get("test_name", "")
        token = t.get("token_number", 0)
        status = t.get("status", "")

        with st.container(border=True):
            cols = st.columns([3, 1.5, 1.5, 1.5, 1.5])
            with cols[0]:
                st.markdown(f"**{name}** — {test_name}")
                st.caption(f"📱 {mobile} | Token #{token}")
            with cols[1]:
                st.caption(f"Status: {status}")
            with cols[2]:
                if status == "waiting":
                    if st.button("📞 Call", key=f"call_{t['id']}", use_container_width=True):
                        harness.call_patient(t["id"])
                        st.rerun()
            with cols[3]:
                if status == "called":
                    if st.button("🩺 Start", key=f"start_{t['id']}", use_container_width=True):
                        harness.start_test(t["id"])
                        st.rerun()
            with cols[4]:
                if status == "called":
                    if st.button("🔙 Back to Waiting", key=f"back_{t['id']}", use_container_width=True):
                        harness.update_test_status(t["id"], "waiting")
                        st.rerun()


def show_vitals(harness):
    st.subheader("🩺 Record Patient Vitals")
    mobile = st.text_input("Patient Mobile", max_chars=10, key="nurse_mobile")
    if st.button("🔍 Lookup", key="nurse_lookup"):
        patient = harness.get_patient_details(mobile, by_mobile=True)
        if patient:
            st.session_state.nurse_patient = patient
            st.success(f"✅ {patient.get('name', '')}")
        else:
            st.error("Patient not found.")

    if st.session_state.get("nurse_patient"):
        p = st.session_state.nurse_patient
        st.markdown(f"**{p.get('name', '')}** — {p.get('patient_id', '')}")

        with st.form("vitals_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                bp = st.text_input("BP", placeholder="120/80")
                pulse = st.number_input("Pulse", min_value=0, value=72)
            with col2:
                temp = st.number_input("Temperature (°F)", min_value=90.0, max_value=110.0, value=98.6, step=0.1)
                spo2 = st.number_input("SpO₂ (%)", min_value=0, max_value=100, value=98)
            with col3:
                weight = st.number_input("Weight (kg)", min_value=0.0, value=70.0, step=0.5)
                height = st.number_input("Height (cm)", min_value=0, value=170)

            if st.form_submit_button("✅ Save Vitals", use_container_width=True):
                st.success("✅ Vitals recorded.")
