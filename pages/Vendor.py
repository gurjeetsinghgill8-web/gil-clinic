"""
Vendor Management Page
======================
"""
import streamlit as st
from utils.vendor import create_vendor, get_vendors

st.set_page_config("Vendors", layout="wide")


def show():
    st.title("🏢 Vendor Management")

    tab1, tab2 = st.tabs(["📋 All Vendors", "➕ Add Vendor"])

    with tab1:
        st.subheader("Registered Vendors")
        vendors = get_vendors()
        if not vendors:
            st.info("No vendors registered yet.")
        else:
            for v in vendors:
                with st.container(border=True):
                    cols = st.columns([2, 1, 1, 1, 1])
                    cols[0].markdown(f"**{v.get('name','')}**")
                    cols[1].write(f"📞 {v.get('contact','')}")
                    cols[2].write(f"⭐ {v.get('rating','-')}/5")
                    cols[3].write(v.get("gst",""))
                    cols[4].write(v.get("category",""))

    with tab2:
        st.subheader("Add New Vendor")
        name = st.text_input("Vendor Name*")
        contact = st.text_input("Contact Person")
        phone = st.text_input("Phone")
        email = st.text_input("Email")
        gst = st.text_input("GST Number")
        category = st.selectbox("Category", ["", "pharmaceuticals", "equipment", "consumables", "supplies", "other"])
        address = st.text_area("Address")
        rating = st.slider("Rating", 1, 5, 3)

        if st.button("💾 Register Vendor", type="primary"):
            if not name:
                st.error("Vendor name is required.")
            else:
                r = create_vendor(name, contact, phone, email, gst, category, address, rating)
                if r.get("success"):
                    st.success(r["message"])
                    st.rerun()
                else:
                    st.error(r.get("message", "Failed to register vendor"))
