"""
Inventory / Pharmacy Dashboard — Stock Management, Batch Tracking, Dispensing
================================================================================
Comprehensive inventory management page for managers and pharmacists.

Tabs:
  1. 📦 Stock Overview — Search/view all items, low-stock alerts, expiry alerts
  2. 📥 Add Stock — Add new items and batch inventory (purchase receipt)
  3. 📋 Stock Movements — Filterable movement log
  4. 📊 Batch Report — Expiry tracking and batch details
  5. 📝 Stock Audit — Create and manage audit sessions

Access: Manager, Admin, Pharmacist
"""
import streamlit as st
from datetime import date, datetime, timedelta

from llm_harness import get_harness
from utils.config import HOSPITAL_NAME
from utils.inventory import (
    get_categories, get_items, get_batches, get_movements,
    get_low_stock_items, get_expiring_batches,
    get_audits, get_audit_items, get_inventory_summary,
    CATEGORY_TYPES, UNITS, MOVEMENT_TYPES, AUDIT_TYPES,
)


def show():
    harness = get_harness()
    now = datetime.now()
    today = now.strftime("%d-%b-%Y %I:%M %p")

    st.title("📦 Inventory / Pharmacy")
    st.markdown(f"### {HOSPITAL_NAME}")
    st.caption(f"🗓️ {today}")

    # Auto-refresh every 10 seconds
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=10000, key="refresh_inv")
    except ImportError:
        pass

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📦 Stock Overview", "📥 Add Stock", "📋 Movements",
        "📊 Batch Report", "📝 Stock Audit"
    ])

    with tab1:
        show_stock_overview(harness)
    with tab2:
        show_add_stock(harness)
    with tab3:
        show_movements(harness)
    with tab4:
        show_batch_report(harness)
    with tab5:
        show_stock_audit(harness)


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB 1: STOCK OVERVIEW
# ═══════════════════════════════════════════════════════════════════════════════

def show_stock_overview(harness):
    """Tab 1: Stock overview with search, category filter, and alerts."""
    st.subheader("📦 Stock Overview")

    # ─── Summary cards ────────────────────────────────────────────────────────
    summary = get_inventory_summary()
    if summary:
        mc1, mc2, mc3, mc4, mc5 = st.columns(5)
        with mc1:
            st.metric("Total Items", summary.get("total_items", 0))
        with mc2:
            st.metric("Total Batches", summary.get("total_batches", 0))
        with mc3:
            val = summary.get("total_stock_value", 0)
            st.metric("Stock Value", f"₹{val:,.0f}")
        with mc4:
            low = summary.get("low_stock_count", 0)
            st.metric("⚠️ Low Stock", low, delta_color="inverse")
        with mc5:
            exp = summary.get("expiring_30_days", 0)
            st.metric("⏳ Expiring ≤30d", exp, delta_color="inverse")

    st.divider()

    # ─── Filters ──────────────────────────────────────────────────────────────
    col_f1, col_f2, col_f3 = st.columns([2, 2, 1])
    with col_f1:
        search = st.text_input("🔍 Search by name / generic name / SKU", key="inv_search")
    with col_f2:
        cats = get_categories()
        cat_options = {c["name"]: c["id"] for c in cats}
        cat_options["All Categories"] = ""
        sel_cat = st.selectbox("Category", list(cat_options.keys()), key="inv_cat")
        cat_id = cat_options[sel_cat]
    with col_f3:
        show_all = st.checkbox("Show inactive", key="inv_show_all")

    # ─── Item table ───────────────────────────────────────────────────────────
    items = get_items(
        category_id=cat_id,
        search=search,
        active_only=not show_all
    )

    if not items:
        st.info("📭 No inventory items found. Add stock in the 'Add Stock' tab.")
        return

    # Build a stock map
    batches = get_batches()
    stock_map = {}
    for b in batches:
        iid = b.get("item_id", "")
        stock_map[iid] = stock_map.get(iid, 0) + b.get("quantity", 0)

    st.markdown(f"**{len(items)} item(s)**")
    for item in items:
        iid = item["id"]
        total_qty = stock_map.get(iid, 0)
        reorder = item.get("reorder_level", 10)
        is_low = total_qty <= reorder

        with st.container():
            cols = st.columns([3, 2, 1.5, 1.5, 1])
            with cols[0]:
                name = item.get("name", "?")
                generic = item.get("generic_name", "")
                label = f"**{name}**"
                if generic:
                    label += f"  ·  *{generic}*"
                st.markdown(label)
                st.caption(f"SKU: {item.get('sku_code', '—')}  |  {item.get('category_name', '?')}")
            with cols[1]:
                unit = item.get("unit", "tab")
                st.markdown(f"**Stock:** {total_qty:.0f} {unit}")
                if is_low and total_qty > 0:
                    st.markdown(f"<span style='color:#FF9800;'>⚠️ Below reorder ({reorder:.0f})</span>",
                                unsafe_allow_html=True)
                elif total_qty == 0:
                    st.markdown("<span style='color:#FF5722;'>❌ Out of Stock</span>",
                                unsafe_allow_html=True)
            with cols[2]:
                st.caption(f"Reorder: {item.get('reorder_qty', 50):.0f} {unit}")
            with cols[3]:
                batch_count = sum(1 for b in batches if b.get("item_id") == iid)
                st.markdown(f"📦 {batch_count} batch(es)")
            with cols[4]:
                # Quick dispense button
                if total_qty > 0:
                    if st.button("💊 Dispense", key=f"disp_{iid}", use_container_width=True):
                        st.session_state.inv_dispense_item_id = iid
                        st.session_state.inv_dispense_item_name = name
                        st.rerun()
        st.divider()

    # ─── Low stock alerts section ─────────────────────────────────────────────
    st.subheader("⚠️ Low Stock Alerts")
    low_items = get_low_stock_items()
    if low_items:
        for li in low_items:
            st.warning(
                f"**{li.get('name', '?')}** — Stock: {li.get('total_stock', 0):.0f} "
                f"(Reorder at: {li.get('reorder_level', 10):.0f})  ·  "
                f"Suggested order: {li.get('reorder_qty', 50):.0f} units"
            )
    else:
        st.success("✅ No low stock items.")

    # ─── Expiry alerts ────────────────────────────────────────────────────────
    st.subheader("⏳ Expiring Soon (≤30 days)")
    expiring = get_expiring_batches(30)
    if expiring:
        for eb in expiring:
            st.warning(
                f"**{eb.get('item_name', '?')}** — Batch: {eb.get('batch_no', '?')}  ·  "
                f"Expires: {eb.get('expiry_date', '?')}  ·  "
                f"Qty: {eb.get('quantity', 0):.0f} {eb.get('unit', '')}"
            )
    else:
        st.success("✅ No items expiring within 30 days.")

    # ─── Dispense modal ──────────────────────────────────────────────────────
    if st.session_state.get("inv_dispense_item_id"):
        show_dispense_modal(harness)


def show_dispense_modal(harness):
    """Inline dispense dialog."""
    iid = st.session_state.inv_dispense_item_id
    iname = st.session_state.inv_dispense_item_name
    st.divider()
    st.subheader(f"💊 Dispense: {iname}")

    total = harness.get_total_stock(iid)
    st.caption(f"Available stock: {total:.0f}")

    col_d1, col_d2, col_d3 = st.columns(3)
    with col_d1:
        qty = st.number_input("Quantity", min_value=1, max_value=int(max(total, 1)),
                              value=min(10, int(max(total, 1))), key="inv_disp_qty")
    with col_d2:
        ref_type = st.selectbox("Reference", ["dispense", "return", "audit", "expiry"], key="inv_disp_ref")
    with col_d3:
        notes = st.text_input("Notes (optional)", key="inv_disp_notes")

    col_b1, col_b2 = st.columns(2)
    with col_b1:
        if st.button("✅ Confirm Dispense", key="inv_disp_confirm", use_container_width=True):
            result = harness.dispense_item(iid, qty, ref_type, created_by=st.session_state.get("auth_name", ""), notes=notes)
            if result.get("success"):
                st.success(result["message"])
                st.session_state.inv_dispense_item_id = None
                st.rerun()
            else:
                st.error(result["message"])
    with col_b2:
        if st.button("❌ Cancel", key="inv_disp_cancel", use_container_width=True):
            st.session_state.inv_dispense_item_id = None
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB 2: ADD STOCK
# ═══════════════════════════════════════════════════════════════════════════════

def show_add_stock(harness):
    """Tab 2: Add new items and add stock batches."""
    tab_add_item, tab_add_batch = st.tabs(["➕ New Item", "📥 Add Stock (Purchase Receipt)"])

    with tab_add_item:
        show_new_item_form(harness)

    with tab_add_batch:
        show_add_batch_form(harness)


def show_new_item_form(harness):
    """Form to create a new inventory item."""
    st.subheader("➕ New Inventory Item")

    cats = get_categories()
    cat_map = {c["name"]: c["id"] for c in cats}

    with st.form("new_item_form"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Item Name *", placeholder="e.g., Aspirin 75mg")
            generic = st.text_input("Generic Name", placeholder="e.g., Acetylsalicylic Acid")
            manufacturer = st.text_input("Manufacturer", placeholder="e.g., Cipla")
        with col2:
            category = st.selectbox("Category *", list(cat_map.keys()))
            unit = st.selectbox("Unit", UNITS, index=0)
            sku = st.text_input("SKU Code (auto if empty)", placeholder="Leave blank for auto")

        col3, col4 = st.columns(2)
        with col3:
            reorder_level = st.number_input("Reorder Level", min_value=0.0, value=10.0, step=5.0)
        with col4:
            reorder_qty = st.number_input("Reorder Qty", min_value=0.0, value=50.0, step=10.0)

        hsn = st.text_input("HSN Code (optional)", placeholder="e.g., 30049099")

        submitted = st.form_submit_button("✅ Add Item", use_container_width=True)
        if submitted:
            if not name:
                st.error("Item name is required.")
            else:
                result = harness.create_item(
                    name=name, category_id=cat_map[category], unit=unit,
                    generic_name=generic, manufacturer=manufacturer,
                    reorder_level=reorder_level, reorder_qty=reorder_qty,
                    sku_code=sku, hsn_code=hsn
                )
                if result.get("success"):
                    st.success(f"{result['message']} (SKU: {result.get('sku', '')})")
                else:
                    st.error(result["message"])


def show_add_batch_form(harness):
    """Form to add stock to an existing item (purchase receipt)."""
    st.subheader("📥 Add Stock Batch")

    items = get_items(active_only=True)
    if not items:
        st.info("📭 No items yet. Create an item first.")
        return

    item_map = {f"{i['name']} ({i.get('sku_code', '')})": i["id"] for i in items}

    with st.form("add_batch_form"):
        col1, col2 = st.columns(2)
        with col1:
            sel_item = st.selectbox("Item *", list(item_map.keys()))
            batch_no = st.text_input("Batch No *", placeholder="e.g., BATCH-001")
            quantity = st.number_input("Quantity *", min_value=1.0, value=100.0, step=10.0)
        with col2:
            unit_rate = st.number_input("Unit Rate (₹) *", min_value=0.0, value=10.0, step=1.0)
            mrp = st.number_input("MRP (₹)", min_value=0.0, value=15.0, step=1.0)

        col3, col4 = st.columns(2)
        with col3:
            mfg_date = st.date_input("Manufacturing Date", value=None)
            expiry_date = st.date_input("Expiry Date", value=None)
        with col4:
            supplier_id = st.text_input("Supplier (optional)", placeholder="Supplier name/ID")
            grn_ref = st.text_input("GRN Reference", placeholder="Goods Receipt Note #")

        submitted = st.form_submit_button("✅ Add Stock", use_container_width=True)
        if submitted:
            if not batch_no:
                st.error("Batch number is required.")
            else:
                result = harness.add_batch(
                    item_id=item_map[sel_item], batch_no=batch_no,
                    quantity=quantity, unit_rate=unit_rate, mrp=mrp,
                    mfg_date=mfg_date.isoformat() if mfg_date else "",
                    expiry_date=expiry_date.isoformat() if expiry_date else "",
                    supplier_id=supplier_id, grn_ref=grn_ref,
                    created_by=st.session_state.get("auth_name", "")
                )
                if result.get("success"):
                    st.success(result["message"])
                else:
                    st.error(result["message"])


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB 3: STOCK MOVEMENTS
# ═══════════════════════════════════════════════════════════════════════════════

def show_movements(harness):
    """Tab 3: Filterable stock movement log."""
    st.subheader("📋 Stock Movements")

    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        mt = st.selectbox("Movement Type", ["All"] + MOVEMENT_TYPES, key="mov_type")
    with col_f2:
        days = st.selectbox("Time Range", [7, 14, 30, 60, 90], index=2, key="mov_days")
    with col_f3:
        search_item = st.text_input("🔍 Filter by item name", key="mov_search")

    movements = get_movements(movement_type=mt if mt != "All" else "", days=days)

    if search_item:
        s = search_item.lower()
        movements = [m for m in movements if s in m.get("item_name", "").lower()]

    if not movements:
        st.info("📭 No movements in this period.")
        return

    st.markdown(f"**{len(movements)} movement(s)** in the last {days} days")
    for mv in movements:
        with st.container():
            cols = st.columns([2, 1.5, 1, 1.5, 2])
            ts = mv.get("created_at", "")[:19].replace("T", " ")
            with cols[0]:
                st.markdown(f"**{mv.get('item_name', '?')}**")
                st.caption(ts)
            with cols[1]:
                mtype = mv.get("movement_type", "")
                icon = {"in": "📥", "out": "💊", "transfer": "🔄", "adjustment": "⚖️"}.get(mtype, "📌")
                st.markdown(f"{icon} **{mtype.upper()}**")
            with cols[2]:
                qty = mv.get("quantity", 0)
                direction = "+" if mv.get("movement_type") == "in" else "-"
                st.markdown(f"**{direction}{qty:.0f}** {mv.get('unit', '')}")
            with cols[3]:
                ref = mv.get("reference_type", "")
                ref_id = mv.get("reference_id", "")
                label = f"{ref} · {ref_id[:12]}" if ref_id else ref
                st.caption(label)
            with cols[4]:
                st.caption(f"Batch: {mv.get('batch_no', '—')}")
        st.divider()


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB 4: BATCH REPORT
# ═══════════════════════════════════════════════════════════════════════════════

def show_batch_report(harness):
    """Tab 4: Batch tracking with expiry alerts."""
    st.subheader("📊 Batch Report")

    col_e1, col_e2, col_e3 = st.columns(3)
    with col_e1:
        days_filter = st.selectbox("Expiry Lookahead", [30, 60, 90, 0], index=0,
                                   format_func=lambda x: f"{x} days" if x else "All", key="exp_days")
    with col_e2:
        item_filter = st.text_input("🔍 Filter by item", key="exp_item")
    with col_e3:
        low_only = st.checkbox("Low stock only", key="exp_low")

    batches = get_batches(
        low_stock_only=low_only,
        expiring_within_days=days_filter if days_filter > 0 else 0
    )

    if item_filter:
        s = item_filter.lower()
        batches = [b for b in batches if s in b.get("item_name", "").lower()]

    if not batches:
        st.info("📭 No batches match these filters.")
        return

    st.markdown(f"**{len(batches)} batch(es)**")
    for b in batches:
        with st.container():
            cols = st.columns([2.5, 1.5, 1.5, 1.5, 1.5, 0.5])
            with cols[0]:
                st.markdown(f"**{b.get('item_name', '?')}**")
                st.caption(f"SKU: {b.get('sku_code', '—')}")
            with cols[1]:
                st.markdown(f"📦 {b.get('batch_no', '—')}")
            with cols[2]:
                qty = b.get("quantity", 0)
                unit = b.get("unit", "")
                st.markdown(f"**{qty:.0f}** {unit}")
            with cols[3]:
                st.caption(f"Rate: ₹{b.get('unit_rate', 0):.2f}")
            with cols[4]:
                expiry = b.get("expiry_date", "—")
                if expiry and expiry != "—":
                    try:
                        ed = datetime.strptime(expiry[:10], "%Y-%m-%d").date()
                        days_left = (ed - date.today()).days
                        if days_left < 0:
                            st.markdown(f"<span style='color:#FF5722;'>❌ Expired {abs(days_left)}d ago</span>",
                                        unsafe_allow_html=True)
                        elif days_left <= 30:
                            st.markdown(f"<span style='color:#FF9800;'>⏳ {days_left}d left</span>",
                                        unsafe_allow_html=True)
                        else:
                            st.markdown(f"✅ {days_left}d left")
                    except ValueError:
                        st.caption(expiry[:10])
                else:
                    st.caption("—")
            with cols[5]:
                pass  # spacer
        st.divider()


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB 5: STOCK AUDIT
# ═══════════════════════════════════════════════════════════════════════════════

def show_stock_audit(harness):
    """Tab 5: Stock audit management."""
    st.subheader("📝 Stock Audit")

    tab_new_audit, tab_view_audits = st.tabs(["🆕 New Audit", "📋 Past Audits"])

    with tab_new_audit:
        show_new_audit(harness)

    with tab_view_audits:
        show_past_audits(harness)


def show_new_audit(harness):
    """Create a new audit and record counts."""
    st.subheader("🆕 New Audit Session")

    with st.form("new_audit_form"):
        col1, col2 = st.columns(2)
        with col1:
            audit_type = st.selectbox("Audit Type", AUDIT_TYPES)
        with col2:
            audit_notes = st.text_area("Notes (optional)", height=80)

        submitted = st.form_submit_button("🚀 Start Audit", use_container_width=True)
        if submitted:
            result = harness.create_audit(
                audit_type=audit_type, notes=audit_notes,
                created_by=st.session_state.get("auth_name", "")
            )
            if result.get("success"):
                st.success(result["message"])
                st.session_state.inv_active_audit_id = result["audit_id"]
                st.rerun()
            else:
                st.error(result["message"])

    # ─── Active audit recording ────────────────────────────────────────────────
    active_audit_id = st.session_state.get("inv_active_audit_id")
    if active_audit_id:
        st.divider()
        st.subheader("📝 Record Audit Counts")
        st.caption(f"Audit: {active_audit_id[:8]}...")

        items = get_items(active_only=True)
        if not items:
            st.info("No items to audit.")
            return

        batches = get_batches()
        for item in items:
            iid = item["id"]
            item_batches = [b for b in batches if b.get("item_id") == iid]
            total_expected = sum(b.get("quantity", 0) for b in item_batches)

            with st.expander(f"**{item['name']}** — Expected: {total_expected:.0f} {item.get('unit', '')}"):
                for b in item_batches:
                    bid = b["id"]
                    expected = b.get("quantity", 0)
                    col_a1, col_a2, col_a3 = st.columns([2, 1, 2])
                    with col_a1:
                        st.markdown(f"Batch: {b.get('batch_no', '—')}  ·  Exp: {b.get('expiry_date', '—')[:10]}")
                    with col_a2:
                        st.markdown(f"Expected: **{expected:.0f}**")
                    with col_a3:
                        actual_key = f"audit_{bid}_actual"
                        actual = st.number_input(
                            "Actual count", value=float(expected),
                            min_value=0.0, key=actual_key, label_visibility="collapsed"
                        )
                        if abs(actual - expected) > 0.01:
                            st.markdown(f"<span style='color:#FF9800;'>Variance: {actual - expected:+.0f}</span>",
                                        unsafe_allow_html=True)

                # Record all batches for this item
                if st.button(f"✅ Record {item['name']}", key=f"rec_audit_{iid}", use_container_width=True):
                    all_ok = True
                    for b in item_batches:
                        bid = b["id"]
                        expected = b.get("quantity", 0)
                        actual = st.session_state.get(f"audit_{bid}_actual", expected)
                        result = harness.record_audit_item(
                            active_audit_id, iid, bid, expected, actual
                        )
                        if not result.get("success"):
                            all_ok = False
                            st.error(f"Batch {b.get('batch_no', '')}: {result['message']}")
                    if all_ok:
                        st.success(f"✅ {item['name']} — all batches recorded.")

        # Close audit
        st.divider()
        if st.button("✅ Complete & Close Audit", key="close_audit", use_container_width=True, type="primary"):
            result = harness.complete_audit(active_audit_id)
            if result.get("success"):
                st.success(result["message"])
                st.session_state.inv_active_audit_id = None
                st.rerun()
            else:
                st.error(result["message"])


def show_past_audits(harness):
    """View past audit sessions with details."""
    st.subheader("📋 Past Audits")

    audits = get_audits(limit=50)
    if not audits:
        st.info("📭 No audit sessions yet.")
        return

    for a in audits:
        status_icon = "✅" if a.get("status") == "completed" else "🔄"
        with st.expander(f"{status_icon} {a.get('audit_type', '?').title()} — {a.get('audit_date', '?')}"):
            cols = st.columns(3)
            with cols[0]:
                st.markdown(f"**Type:** {a.get('audit_type', '?').title()}")
            with cols[1]:
                st.markdown(f"**Status:** {a.get('status', '?').title()}")
            with cols[2]:
                st.markdown(f"**By:** {a.get('created_by', '—')}")
            if a.get("notes"):
                st.caption(f"Notes: {a['notes']}")

            # Show audit items
            items = get_audit_items(a["id"])
            if items:
                st.markdown("**Counts:**")
                for ai in items:
                    v = ai.get("variance", 0)
                    var_color = "#4CAF50" if abs(v) < 0.01 else "#FF9800" if v != 0 else "#666"
                    st.markdown(
                        f"- {ai.get('item_name', '?')} (Batch: {ai.get('batch_no', '—')}): "
                        f"Expected {ai.get('expected_qty', 0):.0f} → Actual {ai.get('actual_qty', 0):.0f} "
                        f"| <span style='color:{var_color};'>{v:+.0f}</span>"
                        f"{' ✅' if ai.get('resolved') else ' ❌'}",
                        unsafe_allow_html=True
                    )
