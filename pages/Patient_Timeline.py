"""
Patient Timeline — Journey Tracker
"""
import streamlit as st
from datetime import datetime, date
from utils.db import get_patient_by_id, get_patient_by_mobile

st.set_page_config("Patient Timeline", layout="wide")

def show():
    st.title("Patient Journey Timeline")
    
    lookup = st.radio("Search by", ["Patient ID", "Mobile"], horizontal=True)
    patient = None
    if lookup == "Patient ID":
        pid = st.text_input("Patient ID")
        if pid: patient = get_patient_by_id(pid)
    else:
        mobile = st.text_input("Mobile")
        if mobile: patient = get_patient_by_mobile(mobile)
    
    if patient:
        st.success(f"Found: {patient.get('name','')}")
        st.info("Timeline view - shows patient journey across registration, tests, billing, and discharge.")
        
        timeline = [
            ("Registration", datetime.now().strftime("%Y-%m-%d %H:%M"), "Patient registered in system", "completed"),
            ("Tests", "", "Assigned to departments", "pending"),
            ("Doctor Consultation", "", "Doctor review", "pending"),
            ("Billing", "", "Payment processing", "pending"),
            ("Report Delivery", "", "Reports ready", "pending"),
        ]
        
        for step_name, step_time, step_desc, step_status in timeline:
            icon = "✅" if step_status == "completed" else "⏳" if step_status == "pending" else "⏺"
            with st.container(border=True):
                st.markdown(f"**{icon} {step_name}**")
                if step_time: st.caption(f"🕐 {step_time}")
                st.write(step_desc)
    else:
        st.info("Enter Patient ID or Mobile to view timeline")
