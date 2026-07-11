"""
Billing & Invoices Page — Pricing, Bills, Payment Recording
=============================================================
Create bills for completed tests, record payments, view invoice history.

Access: Reception, Manager, Admin
"""
import streamlit as st
from datetime import date, datetime

from llm_harness import get_harness
from utils.config import HOSPITAL_NAME, TEST_TYPES
from utils.billing import (
    get_test_prices, update_test_price, create_bill, record_payment,
    get_bills_for_patient, get_bills_for_date, get_today_billing_summary,
    generate_invoice_html, DEFAULT_TEST_PRICES, PAYMENT_MODES
)


def show_price_catalogue():
    """View and manage test prices."""
    st.subheader("💰 Test Price Catalogue")

    prices = get_test_prices()

    if not prices:
        prices = dict(DEFAULT_TEST_PRICES)

    # Display current prices
    data = []
    for test_name in TEST_TYPES:
        price = prices.get(test_name, DEFAULT_TEST_PRICES.get(test_name, 0))
        data.append({"Test": test_name, "Price (₹)": f"₹{price:,.2f}"})

    st.table(data)

    # Price update (Admin only)
    role = st.session_state.get("auth_role", "")
    if role == "Admin":
        st.markdown("---")
        st.markdown("**Update Test Price**")
        col1, col2 = st.columns(2)
        with col1:
            test = st.selectbox("Select Test", TEST_TYPES, key="price_test")
        with col2:
            new_price = st.number_input("New Price (₹)", min_value=0.0, step=50.0,
                                        value=float(prices.get(test, 0)), key="price_val")
        if st.button("💾 Update Price", type="primary", use_container_width=True):
            if update_test_price(test, new_price):
                st.success(f"✅ Price for {test} updated to ₹{new_price:,.2f}")
                st.rerun()
            else:
                st.error("❌ Failed to update price.")


def show_create_bill():
    """Create a new bill from patient's completed tests."""
    harness = get_harness()

    st.subheader("🧾 Create New Bill")

    with st.container(border=True):
        mobile = st.text_input("Patient Mobile Number", max_chars=10,
                               placeholder="10-digit mobile", key="bill_mobile")
        col1, col2 = st.columns([1, 2])
        with col1:
            lookup = st.button("🔍 Lookup", type="primary", use_container_width=True)

        patient_data = None
        patient_name = ""
        patient_id = ""

        if lookup and mobile and len(mobile) == 10 and mobile.isdigit():
            patient_data = harness.get_patient_details(mobile, by_mobile=True)
            if patient_data and patient_data.get("patient_id"):
                patient_name = patient_data.get("name", "")
                patient_id = patient_data.get("patient_id", "")
                st.success(f"✅ Found: {patient_name} ({patient_id})")
            else:
                st.error("❌ Patient not found.")
        elif lookup:
            st.warning("Please enter a valid 10-digit mobile.")

    if patient_id:
        # Get completed tests
        tests = harness.get_tests_by_mobile(mobile)
        completed_tests = [t for t in tests if t.get("status") in ("completed", "report_ready", "delivered")]

        if not completed_tests:
            st.info("🕐 No completed tests found for this patient. Complete tests first.")
            return

        prices = get_test_prices()
        if not prices:
            prices = dict(DEFAULT_TEST_PRICES)

        with st.container(border=True):
            st.markdown("**Select Tests to Bill**")

            test_options = []
            total = 0
            for t in completed_tests:
                tname = t.get("test_name", "?")
                price = prices.get(tname, 0)
                test_options.append({
                    "id": t["id"],
                    "test_name": tname,
                    "price": price,
                    "status": t.get("status", ""),
                    "selected": True
                })
                total += price

            # Display tests
            selected_tests = []
            for t in test_options:
                cols = st.columns([3, 1, 1])
                with cols[0]:
                    checked = st.checkbox(f"{t['test_name']}", value=True,
                                          key=f"bill_sel_{t['id']}")
                with cols[1]:
                    st.markdown(f"₹{t['price']:,.2f}")
                with cols[2]:
                    st.caption(t['status'].replace('_', ' ').title())
                if checked:
                    selected_tests.append(t)

            if not selected_tests:
                st.warning("Please select at least one test.")
                return

            subtotal = sum(t["price"] for t in selected_tests)

            # ─── Medicine Dispense from Inventory ────────────────────────────────
            st.divider()
            st.subheader("💊 Add Medicines")
            try:
                from utils.inventory import get_items, get_batches, get_total_stock, UNITS
                inv_items = get_items(active_only=True)
                if inv_items:
                    inv_options = {}
                    for i in inv_items:
                        stock = get_total_stock(i["id"])
                        if stock > 0:
                            inv_options[f"{i['name']} (Stock: {stock:.0f} {i.get('unit', 'tab')})"] = i["id"]

                    if inv_options:
                        col_m1, col_m2, col_m3 = st.columns([3, 1, 1.5])
                        with col_m1:
                            sel_med = st.selectbox("Select Medicine", ["—"] + list(inv_options.keys()), key="bill_med")
                        with col_m2:
                            med_qty = st.number_input("Qty", min_value=1, value=1, key="bill_med_qty")
                        with col_m3:
                            med_price = st.number_input("Price/unit (₹)", min_value=0.0, value=10.0, step=5.0, key="bill_med_price")
                            if st.button("➕ Add to Bill", key="bill_add_med", use_container_width=True):
                                st.session_state.setdefault("bill_medicines", [])
                                st.session_state.bill_medicines.append({
                                    "item_id": inv_options.get(sel_med, ""),
                                    "name": sel_med.split(" (")[0],
                                    "qty": med_qty,
                                    "price": med_price,
                                    "total": med_qty * med_price,
                                })
                                st.rerun()

                    # Show added medicines
                    added = st.session_state.get("bill_medicines", [])
                    if added:
                        st.markdown("**Added Medicines:**")
                        for i, med in enumerate(added):
                            cols_m = st.columns([3, 1, 1, 0.5])
                            with cols_m[0]:
                                st.markdown(med["name"])
                            with cols_m[1]:
                                st.caption(f"Qty: {med['qty']}")
                            with cols_m[2]:
                                st.markdown(f"₹{med['total']:,.2f}")
                            with cols_m[3]:
                                if st.button("❌", key=f"rm_med_{i}"):
                                    st.session_state.bill_medicines.pop(i)
                                    st.rerun()
                        med_total = sum(m["total"] for m in added)
                        st.markdown(f"**Medicine Total: ₹{med_total:,.2f}**")
            except ImportError:
                pass
            # ─── End Medicine Section ────────────────────────────────────────────

            col1, col2 = st.columns(2)
            with col1:
                medicine_total = sum(m["total"] for m in st.session_state.get("bill_medicines", []))
                grand_total = subtotal + medicine_total
                discount = st.number_input("Discount (₹)", min_value=0.0,
                                           max_value=float(grand_total), step=10.0, value=0.0)
            with col2:
                final = grand_total - discount
                st.markdown(f"**Test Total: ₹{subtotal:,.2f}**")
                if medicine_total > 0:
                    st.markdown(f"**Medicine Total: ₹{medicine_total:,.2f}**")
                st.markdown(f"### Final Amount: ₹{final:,.2f}")

            notes = st.text_area("Notes (optional)", placeholder="Payment notes...", max_chars=200)

            if st.button("🧾 Generate Bill", type="primary", use_container_width=True):
                # Auto-dispense medicines from inventory if any
                meds = st.session_state.get("bill_medicines", [])
                for m in meds:
                    if m.get("item_id"):
                        try:
                            from utils.inventory import dispense_item
                            dispense_item(
                                item_id=m["item_id"],
                                quantity=m["qty"],
                                reference_type="dispense",
                                reference_id=f"BILL-{patient_id[:8]}",
                                created_by=st.session_state.get("auth_name", "Billing"),
                                notes=f"Dispensed for {patient_name}"
                            )
                        except Exception as e:
                            st.warning(f"Could not dispense {m['name']}: {e}")

                result = create_bill(
                    patient_id=patient_id,
                    patient_name=patient_name,
                    mobile=mobile,
                    tests=selected_tests,
                    discount=discount,
                    notes=notes.strip()
                )
                if result["success"]:
                    st.success(result["message"])
                    st.balloons()
                    st.session_state.last_bill = result.get("bill")
                    st.session_state.pop("bill_medicines", None)
                    st.rerun()
                else:
                    st.error(result["message"])


def show_billing_desk():
    """View today's bills and record payments."""
    today = date.today()
    today_display = today.strftime("%d-%b-%Y")

    st.subheader(f"💳 Billing Desk — {today_display}")

    # Today's summary
    summary = get_today_billing_summary()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Bills", summary.get("total_bills", 0))
    with col2:
        st.metric("Total Amount", f"₹{summary.get('total_amount', 0):,.0f}")
    with col3:
        st.metric("Paid", f"₹{summary.get('paid_amount', 0):,.0f}",
                  f"{summary.get('paid_count', 0)} bills")
    with col4:
        st.metric("Pending", f"₹{summary.get('pending_amount', 0):,.0f}",
                  f"{summary.get('pending_count', 0)} bills")

    st.divider()

    # Filter by date or mobile
    tab1, tab2 = st.tabs(["📋 Today's Bills", "🔍 Search Patient"])

    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            view_date = st.date_input("Date", value=today, max_value=today)
        with col2:
            status_filter = st.selectbox("Status", ["All", "pending", "paid", "cancelled"], index=0)

        bills = get_bills_for_date(
            bill_date=view_date.isoformat(),
            status=status_filter if status_filter != "All" else ""
        )

        if not bills:
            st.info("📭 No bills for this date.")
        else:
            for bill in bills:
                inv = bill.get("invoice_number", "N/A")
                pname = bill.get("patient_name", "?")
                final = bill.get("final_amount", 0)
                paid = bill.get("amount_paid", 0)
                status = bill.get("status", "pending")
                bill_id = bill.get("id", "")

                status_color = {"paid": "#4CAF50", "pending": "#FF9800", "cancelled": "#FF5722"}
                color = status_color.get(status, "#999")

                with st.container(border=True):
                    cols = st.columns([2, 1, 1, 1, 1])
                    with cols[0]:
                        st.markdown(f"**{pname}** — #{inv}")
                    with cols[1]:
                        st.markdown(f"₹{final:,.2f}")
                    with cols[2]:
                        st.markdown(f"<span style='color:{color};font-weight:600;'>{status.upper()}</span>",
                                    unsafe_allow_html=True)
                    with cols[3]:
                        if status == "pending":
                            if st.button("💳 Pay", key=f"pay_{bill_id}",
                                         type="primary", use_container_width=True):
                                st.session_state.pay_bill_id = bill_id
                                st.session_state.pay_patient = pname
                                st.session_state.pay_amount = final
                                st.session_state.pay_remaining = final - paid
                                st.rerun()
                    with cols[4]:
                        if bill.get("invoice_number"):
                            bill_html = generate_invoice_html(bill, clinic_name=HOSPITAL_NAME)
                            st.download_button(
                                "🖨️ Invoice",
                                data=bill_html,
                                file_name=f"Invoice_{inv}.html",
                                mime="text/html",
                                use_container_width=True,
                                key=f"dl_{bill_id}"
                            )

    with tab2:
        search_mobile = st.text_input("Enter Mobile Number", max_chars=10,
                                      placeholder="10-digit mobile", key="bill_search")
        if search_mobile and len(search_mobile) == 10:
            patient_bills = get_bills_for_patient(search_mobile)
            if patient_bills:
                for bill in patient_bills:
                    inv = bill.get("invoice_number", "N/A")
                    pname = bill.get("patient_name", "?")
                    final = bill.get("final_amount", 0)
                    status = bill.get("status", "pending")
                    created = bill.get("created_at", "")[:10]
                    st.markdown(f"- **{pname}** — #{inv} — ₹{final:,.2f} — {status.title()} — {created}")
            else:
                st.info("No bills found for this patient.")

    # Payment modal (inline)
    if st.session_state.get("pay_bill_id"):
        st.markdown("---")
        bill_id = st.session_state.pay_bill_id
        patient_name = st.session_state.get("pay_patient", "")
        total_amt = st.session_state.get("pay_amount", 0)
        remaining = st.session_state.get("pay_remaining", total_amt)

        st.subheader(f"💳 Record Payment — {patient_name}")
        st.markdown(f"**Total: ₹{total_amt:,.2f}** | **Remaining: ₹{remaining:,.2f}**")

        col1, col2 = st.columns(2)
        with col1:
            pay_amount = st.number_input("Amount", min_value=1.0,
                                         max_value=float(remaining), step=10.0,
                                         value=float(remaining), key="pay_amount_input")
        with col2:
            pay_mode = st.selectbox("Payment Mode", PAYMENT_MODES, index=0, key="pay_mode")

        ref_no = st.text_input("Reference/Transaction No. (optional)", key="pay_ref",
                               placeholder="UPI ref / cheque no / card last 4")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Confirm Payment", type="primary", use_container_width=True):
                result = record_payment(bill_id, pay_amount, pay_mode, ref_no.strip())
                if result["success"]:
                    st.success(result["message"])
                    st.session_state.pay_bill_id = None
                    st.rerun()
                else:
                    st.error(result["message"])
        with col2:
            if st.button("❌ Cancel", use_container_width=True):
                st.session_state.pay_bill_id = None
                st.rerun()


def show():
    """Main entry point for Billing page."""
    role = st.session_state.get("auth_role", "")

    if role not in ("Reception", "Manager", "Admin"):
        st.error("⛔ Access denied. This page is for Reception, Manager, and Admin.")
        return

    st.title("💳 Billing & Invoices")
    st.markdown(f"### {HOSPITAL_NAME}")

    # Init payment session state
    if "pay_bill_id" not in st.session_state:
        st.session_state.pay_bill_id = None

    tabs = st.tabs(["💳 Billing Desk", "🧾 New Bill", "💰 Price Catalogue"])

    with tabs[0]:
        show_billing_desk()

    with tabs[1]:
        show_create_bill()

    with tabs[2]:
        show_price_catalogue()
