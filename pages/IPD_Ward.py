"""
IPD Ward Management Dashboard — Bed Occupancy, Admissions, Discharges
======================================================================
Comprehensive inpatient management page for doctors and managers.

Tabs:
  1. 🛏️ Bed Occupancy Board — Visual grid of all beds with color-coded status
  2. 🏥 Admitted Patients — List of active admissions with vitals/notes actions
  3. 📝 New Admission — Admit a patient from OPD or directly
  4. 📋 Discharge — Discharge an admitted patient with summary

Access: Doctor, Manager, Admin
"""
import streamlit as st
from datetime import date, datetime, timedelta

from llm_harness import get_harness
from utils.config import HOSPITAL_NAME
from utils.ipd import (
    get_wards, get_beds_for_ward, get_ward_occupancy,
    get_active_admissions, get_available_beds,
    get_vitals_for_admission, get_notes_for_admission,
    get_discharged_patients, BED_STATUS_ICONS, BED_STATUS_LABELS,
    ADMISSION_SOURCES, DISCHARGE_TYPES, NOTE_TYPES,
)


def show_bed_occupancy():
    """Tab 1: Visual bed grid with color-coded status tiles."""
    st.subheader("🛏️ Bed Occupancy Board")

    occupancy = get_ward_occupancy()
    if not occupancy:
        st.info("🏥 No wards configured yet.")
        return

    # Summary cards
    cols = st.columns(len(occupancy))
    for col, ward in zip(cols, occupancy):
        with col:
            total = ward.get("total_beds", 0)
            available = ward.get("available", 0)
            occupied = ward.get("occupied", 0)
            pct = int((occupied / total) * 100) if total > 0 else 0
            color = "#4CAF50" if pct < 60 else "#FF9800" if pct < 85 else "#FF5722"
            st.markdown(f"""
            <div style="background:linear-gradient(135deg,{color}15,{color}08);
                        border:1px solid {color}30;border-radius:10px;padding:0.75rem;text-align:center;">
                <div style="font-size:0.8rem;color:#666;font-weight:600;">{ward.get('name', '?')}</div>
                <div style="font-size:1.5rem;font-weight:700;color:{color};">{available}/{total}</div>
                <div style="font-size:0.7rem;color:#999;">{occupied} occupied · {pct}% full</div>
            </div>
            """, unsafe_allow_html=True)

    st.divider()

    # Ward selector
    ward_options = {w["name"]: w["id"] for w in occupancy}
    selected_ward_name = st.selectbox("Select Ward", list(ward_options.keys()), index=0)
    selected_ward_id = ward_options[selected_ward_name]

    # Get beds for this ward
    beds = get_beds_for_ward(selected_ward_id)
    if not beds:
        st.info("No beds in this ward.")
        return

    # Render bed grid (4 columns)
    st.markdown("**Bed Status**")
    status_legend = "  ".join(f"{icon} {label}" for icon, label in
                              [("🟢", "Available"), ("🔴", "Occupied"), ("🟡", "Cleaning"),
                               ("🟠", "Discharge Pending"), ("⚪", "Maintenance")])
    st.caption(status_legend)

    bed_cols = st.columns(4)
    for i, bed in enumerate(beds):
        with bed_cols[i % 4]:
            status = bed.get("status", "available")
            icon = BED_STATUS_ICONS.get(status, "❓")
            label = BED_STATUS_LABELS.get(status, status)
            color_map = {
                "available": "#4CAF50", "occupied": "#FF5722",
                "cleaning": "#FF9800", "maintenance": "#9E9E9E",
                "discharge_pending": "#FF9800",
            }
            color = color_map.get(status, "#999")

            with st.container(border=True):
                st.markdown(f"""
                <div style="text-align:center;">
                    <div style="font-size:1.8rem;">{icon}</div>
                    <div style="font-weight:600;font-size:0.9rem;">{bed.get('bed_label', '?')}</div>
                    <div style="font-size:0.75rem;color:{color};font-weight:600;">{label}</div>
                </div>
                """, unsafe_allow_html=True)

                if status in ("cleaning", "discharge_pending"):
                    if st.button("✅ Mark Available", key=f"clean_{bed['id']}",
                                 use_container_width=True, type="primary"):
                        harness = get_harness()
                        if harness.update_bed_status(bed["id"], "available"):
                            st.success("Bed is now available!")
                            st.rerun()
                        else:
                            st.error("Failed to update bed.")
                elif status == "maintenance":
                    if st.button("🔧 Repair Done", key=f"repair_{bed['id']}",
                                 use_container_width=True):
                        harness = get_harness()
                        if harness.update_bed_status(bed["id"], "available"):
                            st.success("Maintenance complete!")
                            st.rerun()
                elif status == "available":
                    if st.button("🔧 Mark Maintenance", key=f"maint_{bed['id']}",
                                 use_container_width=True):
                        harness = get_harness()
                        if harness.update_bed_status(bed["id"], "maintenance"):
                            st.info("Bed marked for maintenance.")
                            st.rerun()


def show_admitted_patients():
    """Tab 2: Active admissions list with vitals and notes."""
    harness = get_harness()
    st.subheader("🏥 Admitted Patients")

    # Ward filter
    ward_options = {"All Wards": ""}
    for w in get_wards():
        ward_options[w["name"]] = w["id"]
    selected_ward = st.selectbox("Filter by Ward", list(ward_options.keys()), index=0)
    ward_id = ward_options[selected_ward]

    admissions = get_active_admissions(ward_id=ward_id if ward_id else "")

    if not admissions:
        st.success("✅ No active admissions.")
        return

    for adm in admissions:
        pid = adm.get("patient_id", "")
        pname = adm.get("patient_name", "?")
        ward_name = adm.get("ward_name", "?")
        bed_label = adm.get("bed_label", "?")
        doctor = adm.get("admitting_doctor", "—")
        diagnosis = adm.get("diagnosis_primary", "—")

        # Calculate days since admission
        adm_date = adm.get("admission_date", "")
        try:
            adm_dt = datetime.strptime(adm_date, "%Y-%m-%d").date()
            days_since = (date.today() - adm_dt).days
        except Exception:
            days_since = 0

        with st.expander(f"**{pname}** — {ward_name} / {bed_label}  |  Day {days_since}  |  {diagnosis}", expanded=False):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown(f"**Patient ID:** {pid}")
                st.markdown(f"**Doctor:** {doctor}")
            with col2:
                st.markdown(f"**Admitted:** {adm_date}")
                st.markdown(f"**Source:** {adm.get('source', '?').title()}")
            with col3:
                if st.button("📋 Discharge", key=f"discharge_{adm['id']}",
                             type="primary", use_container_width=True):
                    st.session_state.discharge_admission_id = adm["id"]
                    st.session_state.discharge_patient_name = pname
                    st.rerun()

            st.divider()

            # Vitals section
            st.markdown("**Vital Signs**")
            vitals = get_vitals_for_admission(adm["id"], limit=5)
            if vitals:
                vcols = st.columns(5)
                latest = vitals[0]
                with vcols[0]:
                    st.metric("BP", f"{latest.get('bp_systolic', '—')}/{latest.get('bp_diastolic', '—')}")
                with vcols[1]:
                    st.metric("Pulse", latest.get("pulse", "—"))
                with vcols[2]:
                    st.metric("Temp", f"{latest.get('temperature', '—')}°F" if latest.get("temperature") else "—")
                with vcols[3]:
                    st.metric("SpO₂", f"{latest.get('spo2', '—')}%")
                with vcols[4]:
                    st.metric("Weight", f"{latest.get('weight', '—')} kg" if latest.get("weight") else "—")
            else:
                st.info("No vitals recorded yet.")

            # Record Vitals form
            with st.form(key=f"vitals_form_{adm['id']}"):
                vcols = st.columns(5)
                with vcols[0]:
                    bp_sys = st.number_input("BP Systolic", min_value=0, max_value=300, value=120, step=2)
                with vcols[1]:
                    bp_dia = st.number_input("BP Diastolic", min_value=0, max_value=200, value=80, step=2)
                with vcols[2]:
                    pulse = st.number_input("Pulse", min_value=0, max_value=300, value=72, step=1)
                with vcols[3]:
                    temp = st.number_input("Temp (°F)", min_value=94.0, max_value=108.0, value=98.6, step=0.1, format="%.1f")
                with vcols[4]:
                    spo2 = st.number_input("SpO₂ %", min_value=0, max_value=100, value=98, step=1)
                colw1, colw2 = st.columns([1, 4])
                with colw1:
                    weight = st.number_input("Weight (kg)", min_value=0.0, max_value=300.0, value=70.0, step=0.5)
                with colw2:
                    recorded_by = st.text_input("Recorded By", value=st.session_state.get("auth_username", ""))
                if st.form_submit_button("💾 Save Vitals", type="primary", use_container_width=True):
                    result = harness.record_ipd_vitals(
                        adm["id"], bp_sys, bp_dia, pulse, temp, spo2, weight, recorded_by
                    )
                    if result["success"]:
                        st.success(result["message"])
                        st.rerun()
                    else:
                        st.error(result["message"])

            st.divider()

            # Notes section
            st.markdown("**Clinical Notes**")
            notes = get_notes_for_admission(adm["id"], limit=10)
            if notes:
                for n in notes:
                    nt = n.get("note_type", "progress").title()
                    doc = n.get("doctor_name", "?")
                    txt = n.get("notes", "")
                    created = n.get("created_at", "")[:16]
                    st.markdown(f"📝 **[{nt}]** {doc} — {created}")
                    st.markdown(f"> {txt}")
            else:
                st.info("No notes yet.")

            # Add Note form
            with st.form(key=f"note_form_{adm['id']}"):
                ncols = st.columns([3, 1])
                with ncols[0]:
                    note_text = st.text_area("New Note", placeholder="Enter clinical note...", max_chars=1000)
                with ncols[1]:
                    note_type = st.selectbox("Type", NOTE_TYPES, index=0,
                                             format_func=lambda x: x.title())
                    doc_name = st.text_input("Doctor", value=st.session_state.get("auth_username", ""))
                if st.form_submit_button("📝 Add Note", use_container_width=True):
                    if note_text.strip():
                        result = harness.add_ipd_note(adm["id"], doc_name, note_text.strip(), note_type)
                        if result["success"]:
                            st.success(result["message"])
                            st.rerun()
                        else:
                            st.error(result["message"])

    # Discharge modal (inline)
    if st.session_state.get("discharge_admission_id"):
        st.markdown("---")
        st.subheader(f"📋 Discharge — {st.session_state.discharge_patient_name}")
        adm_id = st.session_state.discharge_admission_id

        col1, col2 = st.columns(2)
        with col1:
            disc_type = st.selectbox("Discharge Type", DISCHARGE_TYPES, index=0,
                                     format_func=lambda x: x.upper())
        with col2:
            fup_date = st.date_input("Follow-up Date (optional)", value=None, min_value=date.today())

        disc_summary = st.text_area("Discharge Summary", placeholder="Clinical summary at discharge...", height=150)

        c1, c2 = st.columns(2)
        with c1:
            if st.button("✅ Confirm Discharge", type="primary", use_container_width=True):
                result = harness.discharge_from_ipd(
                    adm_id, disc_type, disc_summary,
                    fup_date.isoformat() if fup_date else ""
                )
                if result["success"]:
                    st.success(result["message"])
                    st.session_state.discharge_admission_id = None
                    st.rerun()
                else:
                    st.error(result["message"])
        with c2:
            if st.button("❌ Cancel", use_container_width=True):
                st.session_state.discharge_admission_id = None
                st.rerun()


def show_new_admission():
    """Tab 3: Admit a new patient."""
    harness = get_harness()
    st.subheader("📝 New IPD Admission")

    with st.container(border=True):
        st.markdown("**Patient Details**")
        col1, col2 = st.columns([2, 1])
        with col1:
            mobile = st.text_input("Patient Mobile Number", max_chars=10,
                                   placeholder="10-digit mobile", key="ipd_mobile")
        with col2:
            lookup = st.button("🔍 Lookup", type="primary", use_container_width=True, key="ipd_lookup")

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
                st.error("❌ Patient not found. Register via Reception first.")
        elif lookup:
            st.warning("Enter a valid 10-digit mobile.")

    if patient_id:
        with st.container(border=True):
            st.markdown("**Admission Details**")

            col1, col2 = st.columns(2)
            with col1:
                source = st.selectbox("Admission Source", ADMISSION_SOURCES, index=0,
                                      format_func=lambda x: x.title())
                admitting_doctor = st.text_input("Admitting Doctor",
                                                  value=st.session_state.get("auth_username", ""))
            with col2:
                diagnosis_primary = st.text_area("Primary Diagnosis", placeholder="Primary diagnosis...", height=80)
                diagnosis_secondary = st.text_area("Secondary Diagnosis (optional)", placeholder="Secondary diagnosis...", height=80)

            # Bed selection
            st.markdown("**Bed Assignment**")
            available_beds = get_available_beds()
            if available_beds:
                bed_options = {}
                for b in available_beds:
                    label = f"{b.get('ward_name', '?')} — {b.get('bed_label', '?')}"
                    bed_options[label] = b["id"]
                selected_bed_label = st.selectbox("Select Bed", list(bed_options.keys()), index=0)
                selected_bed_id = bed_options[selected_bed_label]
            else:
                st.warning("⛔ No beds available!")
                selected_bed_id = ""
                selected_bed_label = ""

            notes = st.text_area("Additional Notes (optional)", placeholder="Any admission notes...", max_chars=500)

            if st.button("🏥 Admit Patient", type="primary", use_container_width=True,
                         disabled=not selected_bed_id):
                result = harness.admit_to_ipd(
                    patient_id=patient_id,
                    patient_name=patient_name,
                    mobile=mobile,
                    source=source,
                    admitting_doctor=admitting_doctor,
                    diagnosis_primary=diagnosis_primary,
                    diagnosis_secondary=diagnosis_secondary,
                    bed_id=selected_bed_id,
                    notes=notes.strip()
                )
                if result["success"]:
                    st.success(result["message"])
                    st.balloons()
                    st.session_state.ipd_mobile = ""
                    st.rerun()
                else:
                    st.error(result["message"])


def show_discharge_history():
    """Tab 4: Recently discharged patients."""
    st.subheader("📋 Discharge History")

    ward_options = {"All Wards": ""}
    for w in get_wards():
        ward_options[w["name"]] = w["id"]
    selected_ward = st.selectbox("Filter by Ward", list(ward_options.keys()), index=0, key="disc_ward")
    ward_id = ward_options[selected_ward]

    discharged = get_discharged_patients(limit=50, ward_id=ward_id if ward_id else "")

    if not discharged:
        st.info("📋 No discharged patients found.")
        return

    for d in discharged:
        pname = d.get("patient_name", "?")
        ward_name = d.get("ward_name", "?")
        bed_label = d.get("bed_label", "?")
        disc_type = d.get("discharge_type", "?").upper()
        disc_date = d.get("discharge_date", "")[:10] if d.get("discharge_date") else "?"
        diagnosis = d.get("diagnosis_primary", "—")

        type_colors = {"NORMAL": "#4CAF50", "LAMA": "#FF9800", "ABSCOND": "#FF5722",
                       "REFERRED": "#2196F3", "EXPIRED": "#9E9E9E"}
        color = type_colors.get(disc_type, "#999")

        with st.container(border=True):
            cols = st.columns([2, 1, 1, 1])
            with cols[0]:
                st.markdown(f"**{pname}** — {diagnosis}")
            with cols[1]:
                st.markdown(f"{ward_name} / {bed_label}")
            with cols[2]:
                st.markdown(disc_date)
            with cols[3]:
                st.markdown(f"<span style='color:{color};font-weight:600;'>{disc_type}</span>",
                            unsafe_allow_html=True)


def show():
    """Main entry point for IPD Ward page."""
    role = st.session_state.get("auth_role", "")

    if role not in ("Doctor", "Manager", "Admin"):
        st.error("⛔ Access denied. This page is for Doctor, Manager, and Admin.")
        return

    st.title("🏥 IPD Ward Management")
    st.markdown(f"### {HOSPITAL_NAME} — Inpatient Department")

    # Auto-refresh
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=15000, key="refresh_ipd")
    except ImportError:
        pass

    # Init discharge session state
    if "discharge_admission_id" not in st.session_state:
        st.session_state.discharge_admission_id = None

    tabs = st.tabs(["🛏️ Bed Occupancy", "🏥 Admitted Patients", "📝 New Admission", "📋 Discharge History"])

    with tabs[0]:
        show_bed_occupancy()

    with tabs[1]:
        show_admitted_patients()

    with tabs[2]:
        show_new_admission()

    with tabs[3]:
        show_discharge_history()
