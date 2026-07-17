"""
Purchase Orders Page
====================
"""
import streamlit as st
from utils.purchase import create_po, add_po_item, update_po_status, get_pos
from utils.vendor import get_vendors
from utils.inventory import get_items, add_batch
import datetime

try:
    st.set_page_config("Purchase Orders", layout="wide")
except Exception:
    pass


def show():
    st.title("📋 Purchase Orders")

    tab1, tab2, tab3 = st.tabs(["📋 All Orders", "➕ New Order", "📦 Receive Stock"])

    with tab1:
        st.subheader("Purchase Orders")
        pos = get_pos()
        if not pos:
            st.info("No purchase orders yet.")
        else:
            for po in pos:
                with st.expander(f"{po['po_number']} — ₹{po.get('total_amount',0):,.2f} — {po.get('status','draft').upper()}"):
                    st.write(f"**Vendor:** {po.get('vendor_name','N/A')}")
                    st.write(f"**Date:** {po.get('order_date','N/A')}")
                    st.write(f"**Notes:** {po.get('notes','')}")
                    if po.get("status") == "pending":
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.button("✅ Approve", key=f"approve_{po['id']}"):
                                update_po_status(po["id"], "approved")
                                st.rerun()
                        with c2:
                            if st.button("❌ Cancel", key=f"cancel_{po['id']}"):
                                update_po_status(po["id"], "cancelled")
                                st.rerun()
                    elif po.get("status") == "approved":
                        if st.button("📦 Mark Received", key=f"recv_{po['id']}"):
                            update_po_status(po["id"], "received")
                            po_items = get_pos(po_id=po["id"])
                            if isinstance(po_items, list) and len(po_items) > 0:
                                for item in po_items:
                                    if item.get("item_id"):
                                        add_batch(item["item_id"], f"PO-{po['po_number']}",
                                                  qty=item.get("quantity", 0),
                                                  unit_rate=item.get("unit_price", 0),
                                                  mrp=item.get("unit_price", 0) * 1.2)
                            st.rerun()

    with tab2:
        st.subheader("Create Purchase Order")
        vendors = get_vendors()
        vendor_options = {v["name"]: v["id"] for v in vendors} if vendors else {}
        vendor_name = st.selectbox("Vendor", ["Select..."] + list(vendor_options.keys()))

        items_list = get_items(active_only=True)
        item_options = {i["name"]: i["id"] for i in items_list} if items_list else {}

        po_notes = st.text_area("Notes")

        if "po_items" not in st.session_state:
            st.session_state.po_items = []

        st.markdown("### Items")
        col_a, col_b, col_c = st.columns([3, 2, 2])
        with col_a:
            sel_item = st.selectbox("Item", ["Select..."] + list(item_options.keys()), key="po_item_sel")
        with col_b:
            sel_qty = st.number_input("Qty", min_value=1, value=1, key="po_qty")
        with col_c:
            sel_price = st.number_input("Unit Price", min_value=0.0, value=0.0, step=10.0, key="po_price")

        if st.button("➕ Add Item"):
            if sel_item != "Select..." and sel_qty > 0 and sel_price > 0:
                st.session_state.po_items.append({
                    "item_id": item_options[sel_item],
                    "item_name": sel_item,
                    "quantity": sel_qty,
                    "unit_price": sel_price
                })
                st.rerun()

        for i, pi in enumerate(st.session_state.po_items):
            c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
            c1.write(pi["item_name"])
            c2.write(f"x{pi['quantity']}")
            c3.write(f"₹{pi['unit_price']:,.2f}")
            c4.write(f"₹{pi['quantity']*pi['unit_price']:,.2f}")
            if c4.button("❌", key=f"del_po_{i}"):
                st.session_state.po_items.pop(i)
                st.rerun()

        total = sum(i["quantity"] * i["unit_price"] for i in st.session_state.po_items)
        st.metric("Total Amount", f"₹{total:,.2f}")

        if st.button("📋 Create Purchase Order", type="primary", disabled=(vendor_name=="Select..." or not st.session_state.po_items)):
            vendor_id = vendor_options.get(vendor_name, "")
            po = create_po(vendor_id, vendor_name, notes=po_notes)
            if po.get("success") and po.get("po_id"):
                for pi in st.session_state.po_items:
                    add_po_item(po["po_id"], pi["item_id"], pi["item_name"],
                               pi["quantity"], pi["unit_price"])
                st.session_state.po_items = []
                st.success(f"✅ {po['message']}")
                st.rerun()
            else:
                st.error(po.get("message", "Failed to create PO"))

    with tab3:
        st.subheader("Receive Stock from PO")
        st.info("Use the 'Mark Received' button in All Orders tab to receive stock and auto-create inventory batches.")
