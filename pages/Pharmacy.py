"""
Pharmacy / Dispensary Dashboard — Medicine Dispensing, Stock View
"""
import streamlit as st
from datetime import datetime

from llm_harness import get_harness
from utils.config import HOSPITAL_NAME
from utils.inventory import (
    get_items, get_batches, get_low_stock_items, get_expiring_batches,
    get_inventory_summary, dispense_item, get_total_stock,
)


def show():
    harness = get_harness()
    now = datetime.now().strftime("%d-%b-%Y %I:%M %p")

    st.title("💊 Pharmacy / Dispensary")
    st.markdown(f"### {HOSPITAL_NAME}")
    st.caption(f"🗓️ {now}")

    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=10000, key="refresh_pharm")
    except ImportError:
        pass

    tab1, tab2, tab3 = st.tabs(["💊 Dispense Medicine", "📦 Stock View", "⚠️ Alerts"])

    with tab1:
        show_dispense(harness)
    with tab2:
        show_stock()
    with tab3:
        show_alerts()


def show_dispense(harness):
    st.subheader("💊 Dispense Medicine")

    # Auto-load from Doctor prescribe session
    rx_patient = st.session_state.get("rx_patient_name", "")
    if rx_patient:
        st.info(f"👤 Prescription for: **{rx_patient}**")
        if st.button("Clear", key="clear_rx"):
            st.session_state.rx_patient_name = ""
            st.rerun()

    items = get_items(active_only=True)
    if not items:
        st.info("📭 No medicines in inventory. Add stock first.")
        return

    item_opts = {f"{i['name']} ({i.get('sku_code', '')})": i["id"] for i in items}
    col1, col2, col3 = st.columns(3)
    with col1:
        sel = st.selectbox("Medicine", list(item_opts.keys()), key="pharm_sel")
    with col2:
        qty = st.number_input("Quantity", min_value=1, value=1, key="pharm_qty")
    with col3:
        patient = st.text_input("Patient Name/ID", placeholder="Optional", key="pharm_patient")

    if st.button("💊 Dispense", type="primary", use_container_width=True):
        iid = item_opts[sel]
        stock = get_total_stock(iid)
        if qty > stock:
            st.error(f"❌ Insufficient stock. Available: {stock:.0f}")
        else:
            result = dispense_item(
                iid, qty, "dispense", created_by=st.session_state.get("auth_name", ""),
                notes=f"Dispensed to {patient or 'Walk-in'}"
            )
            if result["success"]:
                st.success(result["message"])
                st.rerun()
            else:
                st.error(result["message"])


def show_stock():
    st.subheader("📦 Stock View")

    items = get_items(active_only=True)
    if not items:
        st.info("📭 No items.")
        return

    for item in items:
        iid = item["id"]
        total = get_total_stock(iid)
        reorder = item.get("reorder_level", 10)
        with st.container(border=True):
            cols = st.columns([3, 1, 2])
            with cols[0]:
                st.markdown(f"**{item['name']}**")
                st.caption(f"{item.get('generic_name', '')} | {item.get('sku_code', '')}")
            with cols[1]:
                st.markdown(f"**{total:.0f}** {item.get('unit', '')}")
                if total <= reorder:
                    st.markdown(f"<span style='color:#FF9800;'>⚠️ Reorder at {reorder:.0f}</span>",
                                unsafe_allow_html=True)
            with cols[2]:
                batches = get_batches(item_id=iid)
                st.caption(f"{len(batches)} batch(es)")
                if batches:
                    nearest = min(b.get("expiry_date") or "9999" for b in batches)
                    st.caption(f"Nearest expiry: {nearest[:10]}")


def show_alerts():
    st.subheader("⚠️ Alerts")

    st.markdown("**Low Stock Items**")
    low = get_low_stock_items()
    if low:
        for li in low:
            st.warning(f"{li['name']} — Stock: {li.get('total_stock', 0):.0f} / Reorder: {li.get('reorder_level', 10):.0f}")
    else:
        st.success("✅ No low stock items.")

    st.divider()
    st.markdown("**Expiring in 30 days**")
    exp = get_expiring_batches(30)
    if exp:
        for e in exp:
            st.warning(f"{e.get('item_name', '?')} — Batch: {e.get('batch_no', '')} — Exp: {e.get('expiry_date', '')[:10]} — Qty: {e.get('quantity', 0):.0f}")
    else:
        st.success("✅ No items expiring soon.")
