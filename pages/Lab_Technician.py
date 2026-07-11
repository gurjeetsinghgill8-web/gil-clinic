"""
Lab Technician Dashboard
=========================
Central dashboard for lab technicians to manage sample collection,
processing, and result entry across all lab panels.
"""
import streamlit as st
import datetime
from utils.lab import (register_sample, update_sample_status, enter_result,
                       get_pending_samples)

st.set_page_config("Lab Technician", layout="wide")


def show():
    st.title("🧪 Lab Technician Dashboard")

    tab1, tab2, tab3 = st.tabs(["📋 Pending Samples", "➕ Register Sample", "📝 Enter Results"])

    with tab1:
        st.subheader("Samples Pending Processing")
        st.caption("Live queue of all lab samples")

        samples = get_pending_samples()
        if not samples:
            st.success("✅ No pending samples. All caught up!")
        else:
            for s in samples:
                with st.container(border=True):
                    cols = st.columns([2, 1.5, 1, 1, 1])
                    cols[0].markdown(f"**{s.get('patient_name','')}**")
                    cols[1].write(s.get("panel_name",""))
                    cols[2].write(s.get("sample_type",""))
                    cols[3].write(f"**{s.get('status','').upper()}**")
                    if s.get("status") == "collected":
                        if cols[4].button("📥 Receive", key=f"recv_{s['id']}", use_container_width=True):
                            update_sample_status(s["id"], "received")
                            st.rerun()
                    elif s.get("status") == "received":
                        if cols[4].button("🔬 Process", key=f"proc_{s['id']}", use_container_width=True):
                            update_sample_status(s["id"], "processing")
                            st.rerun()

    with tab2:
        st.subheader("Register New Sample")
        patient_name = st.text_input("Patient Name*")
        panel = st.selectbox("Lab Panel",
                            ["CBC", "LFT", "KFT", "Lipid Profile", "Cardiac Enzymes", "Urinalysis", "Other"])
        sample_type = st.selectbox("Sample Type", ["blood", "urine", "stool", "sputum", "swab", "other"])
        collected_by = st.text_input("Collected By")
        notes = st.text_area("Notes")

        if st.button("📥 Register Sample", type="primary"):
            if not patient_name:
                st.error("Patient name is required.")
            else:
                r = register_sample(patient_name, panel, sample_type, collected_by, notes)
                if r.get("success"):
                    st.success(r["message"])
                    st.rerun()
                else:
                    st.error(r.get("message"))

    with tab3:
        st.subheader("Enter Test Results")
        samples = get_pending_samples()
        processing = [s for s in samples if s.get("status") in ("received", "processing")]
        if not processing:
            st.info("No samples ready for result entry.")
        else:
            sel = st.selectbox("Select Sample",
                              [f"{s.get('patient_name','')} — {s.get('panel_name','')}" for s in processing],
                              format_func=lambda x: x)
            idx = [f"{s.get('patient_name','')} — {s.get('panel_name','')}" for s in processing].index(sel)
            sample = processing[idx]

            st.markdown(f"**Patient:** {sample.get('patient_name','')}")
            st.markdown(f"**Panel:** {sample.get('panel_name','')}")

            result_text = st.text_area("Result / Findings", height=150,
                                       placeholder="Enter test results, values, and observations...")
            remarks = st.text_input("Remarks / Notes")

            if st.button("✅ Save Result", type="primary"):
                r = enter_result(sample["id"], result_text, remarks)
                if r.get("success"):
                    update_sample_status(sample["id"], "completed")
                    st.success(r["message"])
                    st.rerun()
                else:
                    st.error(r.get("message"))
