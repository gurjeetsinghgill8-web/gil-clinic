"""
Admin Panel — System Administration Dashboard
"""
import os
import streamlit as st
from datetime import datetime
from utils.config import HOSPITAL_NAME, CLINIC_SPECIALTY
from utils.db import get_all_active_users
from utils.hr import get_staff
from utils.billing import get_today_billing_summary
from utils.finance import get_monthly_summary

st.set_page_config("Admin Panel", layout="wide")

def show():
    st.title("Admin Panel")
    st.markdown(f"### {HOSPITAL_NAME} — System Administration")

    c1, c2, c3, c4 = st.columns(4)
    users = get_all_active_users()
    staff = get_staff()
    billing = get_today_billing_summary()
    monthly = get_monthly_summary()

    c1.metric("Staff Users", len(users) if users else 0)
    c2.metric("HR Records", len(staff) if staff else 0)
    c3.metric("Today Revenue", f"Rs.{billing.get('total',0):,.0f}" if billing else "0")
    c4.metric("Monthly Net", f"Rs.{monthly.get('profit',0):,.0f}" if monthly else "0")

    st.subheader("System Modules")
    utils_count = len([f for f in os.listdir("utils") if f.endswith(".py") and not f.startswith("_")])
    pages_count = len([f for f in os.listdir("pages") if f.endswith(".py") and not f.startswith("_")])
    c1, c2 = st.columns(2)
    c1.metric("Backend Modules", utils_count)
    c2.metric("Dashboard Pages", pages_count)

    st.subheader("Quick Actions")
    q1, q2, q3, q4 = st.columns(4)
    with q1:
        if st.button("Password Management", use_container_width=True):
            st.session_state.page = "Password Management"
            st.rerun()
    with q2:
        if st.button("Activity Log", use_container_width=True):
            st.session_state.page = "Activity Log"
            st.rerun()
    with q3:
        if st.button("System Monitoring", use_container_width=True):
            st.session_state.page = "System Monitoring"
            st.rerun()
    with q4:
        if st.button("System Logs", use_container_width=True):
            st.session_state.page = "System Logs"
            st.rerun()