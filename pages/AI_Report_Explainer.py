"""
AI Report Explainer Page — Medical Report to Simple Language
==============================================================
"""
import streamlit as st
from utils.ai_report_explainer import explain_report, explain_test_value, REFERENCE_RANGES

st.set_page_config("AI Report Explainer", layout="wide")


def show():
    st.title("📄 AI Report Explainer")
    st.caption("Convert lab reports into simple, patient-friendly language")

    tab1, tab2 = st.tabs(["🔍 Explain Report", "📋 Reference Ranges"])

    with tab1:
        st.subheader("Enter Test Results")

        col1, col2 = st.columns(2)
        with col1:
            patient_name = st.text_input("Patient Name*")
            gender = st.selectbox("Gender", ["male", "female"])
        with col2:
            report_type = st.selectbox("Report Type",
                                      ["CBC", "LFT", "KFT", "Lipid Profile", "Thyroid", "Blood Sugar", "Custom"])
            num_tests = st.number_input("Number of tests", min_value=1, max_value=15, value=3)

        test_values = []
        st.markdown("### Enter Test Values")
        for i in range(int(num_tests)):
            cols = st.columns([3, 2, 1])
            with cols[0]:
                test_name = st.text_input(f"Test {i+1} Name", key=f"tn_{i}")
            with cols[1]:
                test_value = st.number_input(f"Value {i+1}", min_value=0.0, step=0.1, key=f"tv_{i}")
            with cols[2]:
                test_unit = st.text_input(f"Unit {i+1}", key=f"tu_{i}", placeholder="mg/dL")
            if test_name:
                test_values.append({"name": test_name, "value": test_value, "unit": test_unit})

        if st.button("📄 Explain Report", type="primary") and patient_name and test_values:
            result = explain_report(patient_name, report_type, test_values, gender=gender)
            if result.get("success"):
                report = result["report"]
                st.success(report.get("summary", ""))

                for r in report.get("results", []):
                    status = r.get("status", "")
                    icon = r.get("icon", "📊")
                    with st.container(border=True):
                        st.markdown(f"### {icon} {r.get('test','')}")
                        st.markdown(r.get("explanation", ""))
                        if status != "normal":
                            st.warning(f"💡 {r.get('simple_explanation','')}")
                        else:
                            st.info(f"ℹ️ {r.get('simple_explanation','')}")

                if report.get("flagged"):
                    st.divider()
                    st.subheader("⚠️ Abnormal Results Summary")
                    for f in report["flagged"]:
                        st.warning(f"{f['icon']} **{f['test']}**: {f['value']} {f['unit']} ({f['range']} {f['unit']}) — {f['flag']}")
            else:
                st.error("Failed to generate explanation")

    with tab2:
        st.subheader("Normal Reference Ranges")
        for test, ref in sorted(REFERENCE_RANGES.items()):
            unit = ref.get("unit", "")
            if "range" in ref:
                rng = f"{ref['range'][0]} - {ref['range'][1]} {unit}"
            else:
                male_r = f"{ref['male'][0]}-{ref['male'][1]}"
                female_r = f"{ref['female'][0]}-{ref['female'][1]}"
                rng = f"♂️ {male_r} / ♀️ {female_r} {unit}"
            with st.container(border=True):
                st.markdown(f"**{test}** — *{rng}*")
