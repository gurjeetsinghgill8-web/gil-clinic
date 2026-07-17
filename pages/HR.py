"""
HR Dashboard Page
=================
"""
import streamlit as st
from utils.hr import add_staff, get_staff, mark_attendance, apply_leave
import datetime

try:
    st.set_page_config("HR Dashboard", layout="wide")
except Exception:
    pass


def show():
    st.title("👥 HR Dashboard")

    tab1, tab2, tab3, tab4 = st.tabs(["👤 Staff", "📋 Attendance", "🏖️ Leave", "➕ Add Staff"])

    with tab1:
        st.subheader("Staff Directory")
        staff = get_staff()
        if not staff:
            st.info("No staff records yet.")
        else:
            for s in staff:
                with st.container(border=True):
                    cols = st.columns([2, 1, 1, 1, 1])
                    cols[0].markdown(f"**{s.get('name','')}**")
                    cols[1].write(s.get("role",""))
                    cols[2].write(f"📞 {s.get('phone','')}")
                    cols[3].write(f"💰 ₹{s.get('salary',0):,.0f}")
                    cols[4].write(s.get("department",""))

    with tab2:
        st.subheader("Mark Attendance")
        att_date = st.date_input("Date", datetime.date.today())

        all_staff = get_staff()
        if not all_staff:
            st.info("No staff members. Add staff first.")
        else:
            for s in all_staff:
                c1, c2, c3 = st.columns([2, 1, 1])
                c1.write(s["name"])
                new_status = c2.selectbox("Status", ["present", "absent", "late", "half-day"],
                                         key=f"att_{s['id']}", label_visibility="collapsed")
                if c3.button("✅ Save", key=f"save_att_{s['id']}"):
                    mark_attendance(s["id"], att_date.isoformat(), new_status)
                    st.rerun()

    with tab3:
        st.subheader("Apply Leave")
        st.info("Leave management: Use the form below to apply.")
        staff_list = get_staff()
        if staff_list:
            staff_names = {s['name']: s['id'] for s in staff_list}
            sel_name = st.selectbox("Staff", list(staff_names.keys()))
            leave_type = st.selectbox("Leave Type", ["sick", "casual", "annual", "maternity", "paternity", "unpaid"])
            from_date = st.date_input("From", datetime.date.today())
            to_date = st.date_input("To", datetime.date.today())
            reason = st.text_area("Reason")
            if st.button("📋 Apply Leave", type="primary"):
                r = apply_leave(staff_names[sel_name], leave_type, from_date.isoformat(), to_date.isoformat(), reason)
                if r.get("success"):
                    st.success(r["message"])
                    st.rerun()
                else:
                    st.error(r.get("message"))

    with tab4:
        st.subheader("Add New Staff")
        name = st.text_input("Full Name*")
        role = st.selectbox("Role", ["doctor", "nurse", "technician", "receptionist", "accountant", "admin", "other"])
        dept = st.text_input("Department")
        phone = st.text_input("Phone")
        email = st.text_input("Email")
        salary = st.number_input("Monthly Salary", min_value=0.0, step=1000.0)
        join_date = st.date_input("Joining Date", datetime.date.today())

        if st.button("👤 Add Staff", type="primary"):
            if not name:
                st.error("Name is required.")
            else:
                r = add_staff(name, role, dept, phone, email, salary, join_date.isoformat())
                if r.get("success"):
                    st.success(r["message"])
                    st.rerun()
                else:
                    st.error(r.get("message", "Failed to add staff"))
