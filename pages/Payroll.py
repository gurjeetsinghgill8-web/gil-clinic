"""
Payroll Processing Page
=======================
"""
import streamlit as st
from utils.payroll import process_payroll, get_payroll_history
from utils.hr import get_staff
import datetime

try:
    st.set_page_config("Payroll", layout="wide")
except Exception:
    pass


def show():
    st.title("💰 Payroll Processing")

    tab1, tab2 = st.tabs(["📋 Payroll History", "➕ Process Payroll"])

    with tab1:
        st.subheader("Payroll Records")
        records = get_payroll_history()
        if not records:
            st.info("No payroll records yet.")
        else:
            for r in records:
                with st.container(border=True):
                    cols = st.columns([2, 1, 1, 1, 1])
                    cols[0].write(f"**{r.get('staff_name','')}**")
                    cols[1].write(r.get("month",""))
                    cols[2].write(f"₹{r.get('basic_pay',0):,.0f}")
                    cols[3].write(f"💰 ₹{r.get('net_pay',0):,.0f}")
                    cols[4].write(f"✅ {r.get('status','paid')}" if r.get('status') == 'paid' else f"⏳ {r.get('status','pending')}")

    with tab2:
        st.subheader("Process Monthly Payroll")
        staff_list = get_staff()
        if not staff_list:
            st.info("No staff members. Add staff in HR page first.")
        else:
            month = st.selectbox("Month", ["January","February","March","April","May","June",
                                           "July","August","September","October","November","December"],
                                index=datetime.date.today().month - 1)
            year = st.number_input("Year", min_value=2020, max_value=2030, value=datetime.date.today().year)

            for s in staff_list:
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
                    c1.write(f"**{s['name']}** ({s.get('role','')})")
                    basic = c2.number_input("Basic Pay", value=float(s.get("salary",0)), key=f"basic_{s['id']}")
                    deductions = c3.number_input("Deductions", value=0.0, key=f"ded_{s['id']}")
                    net = basic - deductions
                    c4.metric("Net Pay", f"₹{net:,.0f}")

                    if st.button(f"💰 Process {s['name']}", key=f"pay_{s['id']}"):
                        r = process_payroll(s["id"], s["name"], month, year, basic, deductions, net)
                        if r.get("success"):
                            st.success(r["message"])
                            st.rerun()
                        else:
                            st.error(r.get("message", "Failed to process payroll"))
