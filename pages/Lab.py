"""
Lab / Pathology Dashboard — Sample Management, Test Results
"""
import streamlit as st
from datetime import datetime

from llm_harness import get_harness
from utils.config import HOSPITAL_NAME
from utils.lab import (
    get_panels, register_sample, get_pending_samples,
    enter_result, get_results_for_sample, update_sample_status,
    SAMPLE_TYPES, SAMPLE_STATUSES,
)


def show():
    harness = get_harness()
    now = datetime.now().strftime("%d-%b-%Y %I:%M %p")

    st.title("🧪 Lab / Pathology")
    st.markdown(f"### {HOSPITAL_NAME}")
    st.caption(f"🗓️ {now}")

    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=10000, key="refresh_lab")
    except ImportError:
        pass

    tab1, tab2, tab3 = st.tabs(["🧪 Pending Samples", "📝 Register Sample", "📊 Enter Results"])

    with tab1:
        st.subheader("🧪 Pending Samples")
        samples = get_pending_samples()
        if not samples:
            st.success("✅ No pending samples.")
        else:
            for s in samples:
                with st.container(border=True):
                    cols = st.columns([2, 1.5, 1.5, 1, 1])
                    with cols[0]:
                        st.markdown(f"**{s.get('patient_name', '?')}**")
                        st.caption(f"ID: {s.get('patient_id', '')[:12]}...")
                    with cols[1]:
                        st.caption(f"Sample: {s.get('sample_type', '?')}")
                    with cols[2]:
                        st.caption(f"Status: {s.get('status', '?')}")
                    with cols[3]:
                        new_status = st.selectbox(
                            "Update", ["—"] + SAMPLE_STATUSES,
                            key=f"stat_{s['id']}", label_visibility="collapsed"
                        )
                        if new_status != "—":
                            update_sample_status(s["id"], new_status)
                            st.rerun()
                    with cols[4]:
                        st.button("🔍 View", key=f"view_{s['id']}")

    with tab2:
        st.subheader("📝 Register Lab Sample")
        mobile = st.text_input("Patient Mobile", max_chars=10, key="lab_mobile")
        if st.button("🔍 Lookup", key="lab_lookup"):
            patient = harness.get_patient_details(mobile, by_mobile=True)
            if patient:
                st.session_state.lab_patient = patient
                st.success(f"✅ {patient.get('name', '')}")
            else:
                st.error("Patient not found.")

        if st.session_state.get("lab_patient"):
            p = st.session_state.lab_patient
            with st.form("lab_sample_form"):
                st.markdown(f"**Patient:** {p.get('name', '')} | {p.get('patient_id', '')}")
                sample_type = st.selectbox("Sample Type", SAMPLE_TYPES)
                notes = st.text_area("Notes")
                if st.form_submit_button("✅ Register Sample", use_container_width=True):
                    result = register_sample(
                        test_id="", patient_id=p.get("patient_id", ""),
                        sample_type=sample_type, notes=notes
                    )
                    if result["success"]:
                        st.success(result["message"])
                        st.session_state.lab_patient = None
                        st.rerun()
                    else:
                        st.error(result["message"])

    with tab3:
        st.subheader("📊 Enter Test Results")
        sid = st.text_input("Sample ID", placeholder="Paste sample ID", key="sid_input")
        if sid and st.button("Load Sample", key="load_sample"):
            results = get_results_for_sample(sid)
            st.session_state.lab_results = results
            st.session_state.lab_sid = sid

        if st.session_state.get("lab_results") is not None:
            st.markdown("**Existing Results:**")
            for r in st.session_state.lab_results:
                flag = r.get("flag", "")
                flag_color = "#FF5722" if flag == "H" else "#2196F3" if flag == "L" else "#4CAF50"
                st.markdown(f"- **{r['test_name']}**: {r['value']} {r.get('unit', '')} "
                            f"<span style='color:{flag_color};'>({r.get('normal_range', '')})</span>",
                            unsafe_allow_html=True)

            st.divider()
            with st.form("lab_result_form"):
                test_name = st.text_input("Test Name", placeholder="e.g., Hemoglobin")
                value = st.text_input("Value", placeholder="e.g., 14.2")
                unit = st.text_input("Unit", placeholder="g/dL")
                normal_range = st.text_input("Normal Range", placeholder="13.0-17.0")
                flag = st.selectbox("Flag", ["", "N", "H", "L"], format_func=lambda x: {"": "Normal", "N": "Normal", "H": "High", "L": "Low"}.get(x, x))
                if st.form_submit_button("✅ Enter Result", use_container_width=True):
                    result = enter_result(sid, test_name, value, unit, normal_range, flag,
                                         entered_by=st.session_state.get("auth_name", ""))
                    if result["success"]:
                        st.success(result["message"])
                        st.session_state.lab_results = None
                        st.rerun()
                    else:
                        st.error(result["message"])
