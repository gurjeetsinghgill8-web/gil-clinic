"""
GST Compliance Page — Tax Invoices, Returns, HSN/SAC Mapping
===============================================================
"""
import streamlit as st
import datetime
from utils.gst import (generate_gst_invoice, get_gst_invoices, get_gst_summary,
                       get_hsn_for_test, get_gst_rate, calculate_tax)
from utils.billing import get_today_billing_summary

st.set_page_config("GST Compliance", layout="wide")


def show():
    st.title("🧾 GST Compliance Module")

    tab1, tab2, tab3 = st.tabs(["📊 GST Summary", "📋 GST Invoices", "ℹ️ HSN / SAC Codes"])

    with tab1:
        st.subheader("GST Period Summary")
        col1, col2 = st.columns(2)
        with col1:
            sel_month = st.selectbox("Month", range(1,13), index=datetime.date.today().month-1)
        with col2:
            sel_year = st.number_input("Year", min_value=2024, max_value=2030,
                                       value=datetime.date.today().year)

        summary = get_gst_summary(sel_month, sel_year)

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("🧾 Invoices", summary.get("invoice_count", 0))
        m2.metric("💰 Taxable", f"₹{summary.get('total_taxable',0):,.2f}")
        m3.metric("🟢 CGST", f"₹{summary.get('total_cgst',0):,.2f}")
        m4.metric("🟠 SGST", f"₹{summary.get('total_sgst',0):,.2f}")
        m5.metric("📊 Total Tax", f"₹{summary.get('total_tax',0):,.2f}")

        st.info("GST on medical services: Consultation=Exempt | Diagnostics=5% | Pharmacy=12%")

        if st.button("🧾 Generate Sample GST Invoice", type="primary"):
            from utils.billing import get_today_billing_summary
            today = get_today_billing_summary()
            sample_amount = today.get("total", 5000) or 5000
            r = generate_gst_invoice("SAMPLE", "Demo Patient", sample_amount, "ECG")
            if r.get("success"):
                st.success(f"✅ Sample Invoice: {r['invoice_number']}")
                st.json(r)
            else:
                st.error(r.get("message", "Failed"))

    with tab2:
        st.subheader("GST Invoices")
        invoices = get_gst_invoices()
        if not invoices:
            st.info("No GST invoices generated yet. Invoices are auto-generated on billing.")
        else:
            for inv in invoices[:25]:
                with st.container(border=True):
                    cols = st.columns([2, 1, 1, 1, 1])
                    cols[0].write(f"**{inv.get('invoice_number','')}**")
                    cols[1].write(inv.get("patient_name",""))
                    cols[2].write(f"₹{inv.get('total_amount',0):,.2f}")
                    cols[3].write(f"CGST: ₹{inv.get('cgst',0):,.2f}")
                    cols[4].write(f"SGST: ₹{inv.get('sgst',0):,.2f}")

    with tab3:
        st.subheader("HSN / SAC Code Reference")
        st.markdown("""
        | Service | HSN/SAC Code | GST Rate |
        |---------|-------------|----------|
        | 🩺 OPD Consultation | 998311 | Exempt (0%) |
        | 🏥 IPD Services | 998311 | Exempt (0%) |
        | 💓 ECG | 998611 | 5% (2.5% CGST + 2.5% SGST) |
        | 🫀 Echo | 998611 | 5% |
        | 🏃 TMT | 998611 | 5% |
        | 🩻 X-Ray | 998612 | 5% |
        | 📡 Ultrasound | 998612 | 5% |
        | 🧪 Lab / Pathology | 998613 | 5% |
        | 💊 Pharmacy - Medicines | 300490 | 12% |
        | 💊 Pharmacy - Other | Various | 18% |
        """)

        st.divider()
        st.caption("Medical services under healthcare are GST-exempt. Diagnostic services attract 5% GST (2.5% CGST + 2.5% SGST). Pharmacy items attract 12% GST.")
