"""
Pharmacist Dashboard
"""
import streamlit as st
from utils.inventory import get_items, get_low_stock_items, get_expiring_batches

st.set_page_config("Pharmacist", layout="wide")

def show():
    st.title("Pharmacist Portal")
    t1, t2, t3 = st.tabs(["Overview", "Quick Links", "Alerts"])
    
    with t1:
        items = get_items(active_only=True)
        low = get_low_stock_items()
        expiring = get_expiring_batches(30)
        c1,c2,c3 = st.columns(3)
        c1.metric("Total Medicines", len(items) if items else 0)
        c2.metric("Low Stock Alerts", len(low) if low else 0)
        c3.metric("Expiring Soon", len(expiring) if expiring else 0)
    
    with t2:
        st.subheader("Quick Access")
        c1,c2,c3,c4 = st.columns(4)
        with c1:
            if st.button("Pharmacy", use_container_width=True):
                st.session_state.page = "Pharmacy"; st.rerun()
        with c2:
            if st.button("Inventory", use_container_width=True):
                st.session_state.page = "Inventory"; st.rerun()
        with c3:
            if st.button("Purchase Orders", use_container_width=True):
                st.session_state.page = "Purchase Orders"; st.rerun()
        with c4:
            if st.button("Vendors", use_container_width=True):
                st.session_state.page = "Vendors"; st.rerun()
    
    with t3:
        if low:
            st.warning("Low Stock Items")
            for item in low:
                st.write(f"- {item.get('name','')}: {item.get('total_qty',0)} remaining")
        if expiring:
            st.warning("Expiring Batches")
            for b in expiring:
                st.write(f"- Batch {b.get('batch_no','')} expires {b.get('expiry_date','')}")
        if not low and not expiring:
            st.success("No alerts")
