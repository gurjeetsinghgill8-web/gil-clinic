"""
Patient Portal — Self-Service Dashboard
==========================================
Patient-facing page for appointment booking, report viewing, and status tracking.
Accessed via "Patient" login role.
"""
import streamlit as st
from datetime import datetime, date
from llm_harness import get_harness
from utils.db import get_patient_by_id, get_patient_by_mobile
from utils.config import HOSPITAL_NAME, CLINIC_SPECIALTY, CLINIC_LOGO

st.set_page_config("Patient Portal", layout="wide")


def show():
    st.title(f"{CLINIC_LOGO} Patient Portal")
    st.markdown(f"### {HOSPITAL_NAME} — {CLINIC_SPECIALTY} Department")

    tab1, tab2, tab3 = st.tabs(["🔍 Track Status", "📋 My Reports", "📅 Book Appointment"])

    with tab1:
        st.subheader("Track Your Test Status")
        st.caption("अपने टेस्ट की स्थिति देखें")

        lookup_method = st.radio("Search by:", ["Patient ID", "Mobile Number"], horizontal=True)
        patient = None

        if lookup_method == "Patient ID":
            pid = st.text_input("Enter Patient ID", placeholder="e.g. PAT-XXXXX")
            if pid:
                patient = get_patient_by_id(pid)
                if not patient:
                    st.error("❌ Patient not found with this ID.")
        else:
            mobile = st.text_input("Enter Mobile Number", placeholder="10-digit mobile")
            if mobile:
                patient = get_patient_by_mobile(mobile)
                if not patient:
                    st.error("❌ No patient found with this mobile.")

        if patient:
            st.success(f"✅ Found: **{patient.get('name','')}**")
            harness = get_harness()
            tests = harness.get_reception_queue()  # uses LLM harness
            patient_tests = [t for t in tests if t.get("patient_id") == patient.get("patient_id")]

            if patient_tests:
                for t in patient_tests:
                    status = t.get("status", "registered")
                    test_name = t.get("test_name", "")
                    token = t.get("token_number", "")
                    status_icon = {"registered": "📝", "waiting": "⏳", "in_progress": "🟠",
                                   "completed": "✅", "report_ready": "📄"}.get(status, "📝")
                    with st.container(border=True):
                        st.markdown(f"**{status_icon} {test_name}** — Token #{token}")
                        st.progress({"registered": 0.1, "waiting": 0.3, "in_progress": 0.6,
                                     "completed": 0.9, "report_ready": 1.0}.get(status, 0))
                        st.caption(f"Status: {status.replace('_', ' ').title()}")
            else:
                st.info("No active tests found. Please visit reception.")

    with tab2:
        st.subheader("Your Reports")
        st.caption("डाउनलोड करें या देखें अपनी रिपोर्ट")
        mobile_reports = st.text_input("Enter Mobile Number for Reports", placeholder="10-digit mobile")
        if mobile_reports:
            patient = get_patient_by_mobile(mobile_reports)
            if patient:
                harness = get_harness()
                bills = harness.get_all_dashboard_stats()  # placeholder
                st.info("📄 Reports ready can be collected from reception.")
                st.markdown("""
                ### 📄 Report Collection
                - Visit the reception desk with your Patient ID
                - Reports are available in printed format
                - Digital copies coming soon
                """)
            else:
                st.error("No patient found with this mobile.")

    with tab3:
        st.subheader("Book an Appointment")
        st.caption("अपॉइंटमेंट बुक करें")

        name = st.text_input("Full Name*")
        mobile = st.text_input("Mobile Number*")
        age = st.number_input("Age", min_value=1, max_value=120, value=30)
        test_type = st.selectbox("Test Type", ["ECG", "Echo", "TMT", "OPD Consultation", "X-Ray", "Ultrasound", "Lab Test"])
        preferred_date = st.date_input("Preferred Date", min_value=date.today())
        preferred_time = st.time_input("Preferred Time")
        notes = st.text_area("Any notes or symptoms")

        if st.button("📅 Book Appointment", type="primary"):
            if not name or not mobile:
                st.error("Name and mobile are required.")
            else:
                # Register via reception flow
                harness = get_harness()
                result = harness.register_patient(name, mobile, age, test_type,
                                                  source="portal",
                                                  notes=notes)
                if result.get("success"):
                    st.success(f"✅ Appointment booked! Token: #{result.get('token', '')}")
                    st.info(f"📱 You will receive a confirmation on {mobile}")
                    st.balloons()
                else:
                    st.error(result.get("message", "Booking failed. Please visit reception."))
