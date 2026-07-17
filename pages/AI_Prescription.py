"""
AI Prescription Assistant Page
================================
"""
import streamlit as st
from utils.ai_prescription import (search_medicines, check_interaction,
                                    suggest_medicines, generate_prescription,
                                    get_prescriptions, MEDICINE_DB)

try:
    st.set_page_config("AI Prescription", layout="wide")
except Exception:
    pass


def show():
    st.title("💊 AI Prescription Assistant")

    tab1, tab2, tab3 = st.tabs(["🆕 New Prescription", "🔍 Medicine Search", "📋 History"])

    with tab1:
        st.subheader("Generate Prescription")
        col1, col2 = st.columns(2)
        with col1:
            patient_name = st.text_input("Patient Name*")
        with col2:
            diagnosis = st.text_area("Diagnosis", placeholder="e.g. Hypertension with high cholesterol",
                                    height=70)

        st.markdown("**Select Medicines**")
        all_meds = list(MEDICINE_DB.keys())
        selected_meds = st.multiselect("Medicines", all_meds)

        if diagnosis:
            suggested = suggest_medicines(diagnosis)
            if suggested:
                st.info(f"💡 Suggested: {', '.join(suggested)}")

        notes = st.text_area("Notes / Instructions")

        if st.button("💊 Generate Prescription", type="primary"):
            if not patient_name or not selected_meds:
                st.error("Patient name and at least one medicine required.")
            else:
                result = generate_prescription(patient_name, diagnosis, selected_meds, notes)
                if result.get("success"):
                    st.success(result["message"])
                    if result.get("warnings"):
                        for w in result["warnings"]:
                            st.warning(w["message"])
                    if result.get("suggested"):
                        extra = [m for m in result["suggested"] if m not in selected_meds]
                        if extra:
                            st.info(f"💡 Also consider: {', '.join(extra)}")
                    st.balloons()
                else:
                    st.error(result.get("message"))

    with tab2:
        st.subheader("Search Medicines")
        query = st.text_input("Search by name or category")
        if query:
            results = search_medicines(query)
            if results:
                for r in results:
                    with st.container(border=True):
                        st.markdown(f"**{r['name']}** — *{r['category']}*")
                        st.write(f"💊 Dosage: {r['dosage']}")
                        if r.get("interactions"):
                            st.caption(f"⚠️ Interactions: {', '.join(r['interactions'])}")
            else:
                st.info("No medicines found.")

    with tab3:
        st.subheader("Prescription History")
        prescriptions = get_prescriptions()
        if not prescriptions:
            st.info("No prescriptions generated yet.")
        else:
            for p in prescriptions[:20]:
                with st.container(border=True):
                    cols = st.columns([2, 1.5, 2, 1])
                    cols[0].write(f"**{p.get('patient_name','')}**")
                    meds = json.loads(p.get("medicines","[]")) if isinstance(p.get("medicines"), str) else p.get("medicines", [])
                    cols[1].write(", ".join(meds[:3]))
                    cols[2].write(p.get("diagnosis","")[:50])
                    cols[3].write(p.get("created_at","")[:10] if p.get("created_at") else "")
                    warnings = json.loads(p.get("warnings","[]")) if isinstance(p.get("warnings"), str) else p.get("warnings", [])
                    if warnings:
                        st.caption(f"⚠️ {len(warnings)} interaction warning(s)")
