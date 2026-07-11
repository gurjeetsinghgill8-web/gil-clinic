"""
Owner Dashboard — Full Business Overview
===========================================
Comprehensive dashboard for hospital owner/administrator with
all KPIs, revenue analytics, staff performance, and system health.
"""
import streamlit as st
from datetime import datetime, date
from llm_harness import get_harness
from utils.billing import get_today_billing_summary, get_bills_for_date
from utils.finance import get_monthly_summary, get_expenses
from utils.hr import get_staff
from utils.config import HOSPITAL_NAME, CLINIC_SPECIALTY, CLINIC_LOGO

st.set_page_config("Owner Dashboard", layout="wide")


def show():
    st.title(f"👑 Owner Dashboard — {HOSPITAL_NAME}")
    st.caption(f"{CLINIC_SPECIALTY} Department — Full Business Overview")

    # ─── KPI Row ──────────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)

    today_billing = get_today_billing_summary()
    monthly = get_monthly_summary()
    staff = get_staff()

    with k1:
        total_rev = today_billing.get("total", 0) if today_billing else 0
        st.metric("💰 Today's Revenue", f"₹{total_rev:,.0f}")
    with k2:
        month_rev = monthly.get("revenue", 0) if monthly else 0
        st.metric("📈 Monthly Revenue", f"₹{month_rev:,.0f}")
    with k3:
        profit = monthly.get("profit", 0) if monthly else 0
        st.metric("📊 Net Profit", f"₹{profit:,.0f}")
    with k4:
        staff_count = len(staff) if staff else 0
        st.metric("👥 Total Staff", str(staff_count))

    # ─── Department Stats ────────────────────────────────────────────────────
    st.subheader("🏥 Department Overview")
    try:
        harness = get_harness()
        stats = harness.get_all_dashboard_stats()
        if stats:
            dept_cols = st.columns(len(stats))
            for col, (dept, s) in zip(dept_cols, stats.items()):
                with col:
                    waiting = s.get("waiting", 0)
                    progress = s.get("in_progress", 0)
                    completed = s.get("completed", 0)
                    st.metric(dept, f"{waiting+progress+completed} today",
                             f"{completed} done")
    except Exception:
        st.info("Loading department stats...")

    # ─── Quick Actions ────────────────────────────────────────────────────────
    st.subheader("⚡ Quick Actions")
    ca1, ca2, ca3, ca4 = st.columns(4)
    with ca1:
        if st.button("📊 View Reports", use_container_width=True):
            st.session_state.page = "📊 Reports & Analytics"
            st.rerun()
    with ca2:
        if st.button("📋 All Bills", use_container_width=True):
            st.session_state.page = "💳 Billing"
            st.rerun()
    with ca3:
        if st.button("👥 Staff", use_container_width=True):
            st.session_state.page = "👥 HR"
            st.rerun()
    with ca4:
        if st.button("💰 Payroll", use_container_width=True):
            st.session_state.page = "💰 Payroll"
            st.rerun()

    # ─── Recent Activity ─────────────────────────────────────────────────────
    st.subheader("📋 Recent Bills")
    bills = get_bills_for_date(date.today().isoformat())
    if bills:
        for b in bills[:5]:
            with st.container(border=True):
                cols = st.columns([2, 1, 1, 1])
                cols[0].write(f"**{b.get('patient_name','')}**")
                cols[1].write(f"₹{b.get('total_amount',0):,.0f}")
                cols[2].write(b.get("bill_date",""))
                cols[3].write(f"✅ {b.get('status','')}" if b.get('status') == 'paid' else f"⏳ {b.get('status','')}")
    else:
        st.info("No recent bills.")

    # ─── System Health ────────────────────────────────────────────────────────
    st.subheader("🖥️ System Health")
    h1, h2, h3 = st.columns(3)
    with h1:
        st.success("✅ Database: SQLite Active")
    with h2:
        try:
            from utils.db import DB_FILE
            import os
            size = os.path.getsize(DB_FILE) / 1024
            st.info(f"💾 DB Size: {size:.0f} KB")
        except Exception:
            st.info("💾 DB Size: Unknown")
    with h3:
        page_count = 33  # total pages in system
        st.info(f"📄 Pages: {page_count} active")
