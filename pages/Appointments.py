"""
Appointments Page — Schedule & Manage Patient Appointments
===========================================================
Book appointments with time slots, view daily schedule, check-in patients.

Access: Reception, Manager, Admin
"""
import streamlit as st
from datetime import date, datetime, timedelta

from llm_harness import get_harness
from utils.config import HOSPITAL_NAME, TEST_TYPES
from utils.appointments import (
    book_appointment, get_available_slots, get_appointments_for_date,
    get_appointments_for_patient, update_appointment_status,
    cancel_appointment, get_today_appointments_count,
    APPOINTMENT_STATUS_ICONS, APPOINTMENT_STATUSES
)


def show_book_appointment():
    """Booking form to schedule a new appointment."""
    harness = get_harness()

    st.subheader("📅 Book New Appointment")

    # Patient lookup
    with st.container(border=True):
        col1, col2 = st.columns([2, 1])
        with col1:
            mobile = st.text_input("Patient Mobile Number", max_chars=10,
                                   placeholder="10-digit mobile", key="apt_mobile")
        with col2:
            lookup = st.button("🔍 Lookup", type="primary", use_container_width=True, key="apt_lookup")

        patient_data = None
        patient_name = ""
        patient_id = ""

        if lookup and mobile and len(mobile) == 10 and mobile.isdigit():
            patient_data = harness.get_patient_details(mobile, by_mobile=True)
            if patient_data and patient_data.get("patient_id"):
                patient_name = patient_data.get("name", "")
                patient_id = patient_data.get("patient_id", "")
                st.success(f"✅ Found: {patient_name} ({patient_id})")
            else:
                st.error("❌ Patient not found. Please register the patient first via Reception.")
        elif lookup:
            st.warning("Please enter a valid 10-digit mobile number.")

    # Only show booking form if we have a patient
    if patient_id:
        with st.container(border=True):
            st.markdown("**Appointment Details**")

            col1, col2 = st.columns(2)
            with col1:
                test_name = st.selectbox("Department / Test", TEST_TYPES, index=0)
            with col2:
                # Date picker — allow up to 30 days in future
                min_date = date.today()
                max_date = min_date + timedelta(days=30)
                appt_date = st.date_input("Appointment Date", min_value=min_date,
                                          max_value=max_date, value=min_date)

            # Get available slots
            appt_date_str = appt_date.isoformat()
            slots = get_available_slots(test_name, appt_date_str)

            if slots:
                # Filter to available slots only
                available_slots = [s for s in slots if not s["is_full"]]

                if available_slots:
                    slot_options = [s["time"] for s in available_slots]
                    slot_labels = [
                        f"{s['time']} ({s['available']} slot{'s' if s['available']>1 else ''} left)"
                        for s in available_slots
                    ]
                    time_slot = st.selectbox(
                        "Available Time Slots",
                        options=slot_options,
                        format_func=lambda x: slot_labels[slot_options.index(x)],
                        index=0
                    )
                else:
                    st.warning("⛔ No available slots for this date. Try another date or department.")
                    time_slot = ""
            else:
                st.info("⏳ Generating time slots...")
                time_slot = ""

            notes = st.text_area("Notes (optional)", placeholder="Any special instructions...", max_chars=200)

            if st.button("📅 Book Appointment", type="primary", use_container_width=True,
                         disabled=not time_slot):
                if patient_name and mobile and test_name and time_slot:
                    result = book_appointment(
                        patient_id=patient_id,
                        patient_name=patient_name,
                        mobile=mobile,
                        test_name=test_name,
                        appt_date=appt_date_str,
                        time_slot=time_slot,
                        notes=notes.strip()
                    )
                    if result["success"]:
                        st.success(result["message"])
                        st.balloons()
                        # Clear form
                        st.session_state.apt_mobile = ""
                        st.rerun()
                    else:
                        st.error(result["message"])


def show_daily_schedule():
    """View and manage today's appointments."""
    harness = get_harness()
    today = date.today().isoformat()
    today_display = date.today().strftime("%d-%b-%Y")

    st.subheader(f"📋 Schedule — {today_display}")

    # Filters
    col1, col2 = st.columns(2)
    with col1:
        dept_filter = st.selectbox("Filter by Department", ["All"] + TEST_TYPES, index=0)
    with col2:
        status_filter = st.selectbox("Filter by Status", ["All"] + APPOINTMENT_STATUSES, index=0)

    test_name = dept_filter if dept_filter != "All" else ""
    appointments = get_appointments_for_date(appt_date=today, test_name=test_name)

    if status_filter != "All":
        appointments = [a for a in appointments if a["status"] == status_filter]

    # Stats row
    total = len(appointments)
    checked_in = len([a for a in appointments if a["status"] == "checked_in"])
    completed = len([a for a in appointments if a["status"] == "completed"])
    no_show = len([a for a in appointments if a["status"] == "cancelled"])

    st.markdown(f"""
    <div style="display:flex;gap:1rem;margin-bottom:1rem;">
        <div style="flex:1;background:#667eea10;border-radius:8px;padding:0.5rem;text-align:center;">
            <div style="font-size:1.3rem;font-weight:700;">{total}</div>
            <div style="font-size:0.75rem;color:#666;">Total</div>
        </div>
        <div style="flex:1;background:#4CAF5010;border-radius:8px;padding:0.5rem;text-align:center;">
            <div style="font-size:1.3rem;font-weight:700;color:#4CAF50;">{checked_in}</div>
            <div style="font-size:0.75rem;color:#666;">Checked In</div>
        </div>
        <div style="flex:1;background:#2196F310;border-radius:8px;padding:0.5rem;text-align:center;">
            <div style="font-size:1.3rem;font-weight:700;color:#2196F3;">{completed}</div>
            <div style="font-size:0.75rem;color:#666;">Completed</div>
        </div>
        <div style="flex:1;background:#FF572210;border-radius:8px;padding:0.5rem;text-align:center;">
            <div style="font-size:1.3rem;font-weight:700;color:#FF5722;">{no_show}</div>
            <div style="font-size:0.75rem;color:#666;">Cancelled</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if not appointments:
        st.info("📅 No appointments scheduled for today.")
        return

    # Group by time slot
    from collections import OrderedDict
    grouped = OrderedDict()
    for a in appointments:
        slot = a.get("time_slot", "00:00")
        if slot not in grouped:
            grouped[slot] = []
        grouped[slot].append(a)

    for slot, apps in grouped.items():
        with st.expander(f"⏰ {slot} ({len(apps)} appointment{'s' if len(apps)>1 else ''})", expanded=True):
            for appt in apps:
                status = appt.get("status", "scheduled")
                icon = APPOINTMENT_STATUS_ICONS.get(status, "📅")
                pname = appt.get("patient_name", "Unknown")
                test = appt.get("test_name", "?")
                mobile = appt.get("mobile", "")
                notes = appt.get("notes", "")
                appt_id = appt.get("id", "")

                cols = st.columns([3, 1, 1, 1, 1])
                with cols[0]:
                    st.markdown(f"**{pname}** — {test}")
                    st.caption(f"📱 {mobile}")
                    if notes:
                        st.caption(f"📝 {notes}")
                with cols[1]:
                    st.markdown(f"**{icon} {status.title()}**")

                with cols[2]:
                    if status == "scheduled":
                        if st.button("✅ Check In", key=f"checkin_{appt_id}",
                                     type="primary", use_container_width=True):
                            if update_appointment_status(appt_id, "checked_in"):
                                st.success("Checked in!")
                                st.rerun()
                            else:
                                st.error("Failed to check in.")
                with cols[3]:
                    if status in ("scheduled", "checked_in"):
                        if st.button("❌ Cancel", key=f"cancel_{appt_id}",
                                     use_container_width=True):
                            if cancel_appointment(appt_id):
                                st.warning("Cancelled.")
                                st.rerun()
                            else:
                                st.error("Failed to cancel.")
                with cols[4]:
                    if status == "checked_in":
                        if st.button("🟠 Start", key=f"start_{appt_id}",
                                     use_container_width=True):
                            if update_appointment_status(appt_id, "in_progress"):
                                st.info("Started!")
                                st.rerun()
                st.divider()


def show():
    """Main entry point for Appointments page."""
    role = st.session_state.get("auth_role", "")

    if role not in ("Reception", "Manager", "Admin"):
        st.error("⛔ Access denied. This page is for Reception, Manager, and Admin.")
        return

    st.title("📅 Appointments")
    st.markdown(f"### {HOSPITAL_NAME}")

    # Auto-refresh
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=15000, key="refresh_appt")
    except ImportError:
        pass

    # Tabs for booking and daily view
    tab1, tab2 = st.tabs(["📅 Book Appointment", "📋 Daily Schedule"])

    with tab1:
        show_book_appointment()

    with tab2:
        show_daily_schedule()
