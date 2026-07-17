"""
Compliance Page — Consent Management, Data Rights
====================================================
"""
import streamlit as st
from utils.compliance import (record_consent, get_consent_status,
                               create_data_rights_request, CONSENT_TYPES)

try:
    st.set_page_config("Compliance", layout="wide")
except Exception:
    pass


def show():
    st.title("📋 Compliance Dashboard")

    tab1, tab2 = st.tabs(["✅ Consent Management", "📝 Data Rights Requests"])

    with tab1:
        st.subheader("Patient Consent Records")
        patient_id = st.text_input("Patient ID", key="consent_pid")
        if patient_id:
            statuses = get_consent_status(patient_id)
            if statuses:
                for s in statuses:
                    with st.container(border=True):
                        cols = st.columns([2, 1, 1, 1])
                        cols[0].write(f"**{s.get('consent_type','')}**")
                        cols[1].write(f"{'✅ Granted' if s.get('granted') else '❌ Revoked'}")
                        cols[2].write(s.get("purpose","")[:30])
                        cols[3].write(s.get("granted_at","")[:10] if s.get("granted_at") else "")
            else:
                st.info("No consent records for this patient.")

        st.divider()
        st.subheader("Record Consent")
        pid = st.text_input("Patient ID (to record)", key="record_pid")
        consent_type = st.selectbox("Consent Type", CONSENT_TYPES)
        granted = st.checkbox("Grant Consent", True)
        purpose = st.text_input("Purpose")
        if st.button("💾 Record Consent", type="primary"):
            if not pid:
                st.error("Patient ID required.")
            else:
                r = record_consent(pid, consent_type, granted, purpose)
                if r.get("success"):
                    st.success(r["message"])
                else:
                    st.error(r.get("message"))

    with tab2:
        st.subheader("Data Rights Requests (DPDP Act 2023)")
        req_pid = st.text_input("Patient ID", key="dr_pid")
        req_name = st.text_input("Patient Name")
        req_type = st.selectbox("Request Type", ["access", "correction", "deletion",
                                                   "portability", "restrict"])
        req_details = st.text_area("Details")
        if st.button("📝 Submit Request", type="primary"):
            if not req_pid or not req_name:
                st.error("Patient ID and name required.")
            else:
                r = create_data_rights_request(req_pid, req_name, req_type, req_details)
                if r.get("success"):
                    st.success(r["message"])
                else:
                    st.error(r.get("message"))

        st.info("Under DPDP Act 2023, patients have rights to access, correct, delete, and port their data.")
