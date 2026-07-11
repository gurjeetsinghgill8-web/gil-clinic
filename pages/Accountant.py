"""
Accountant Dashboard
=====================
Finance and accounting dashboard for managing bills, expenses,
revenue tracking, and financial reports.
"""
import streamlit as st
from datetime import datetime, date
from utils.billing import get_bills_for_date, get_today_billing_summary
from utils.finance import add_expense, get_expenses, get_monthly_summary, EXPENSE_CATEGORIES

st.set_page_config("Accountant", layout="wide")


def show():
    st.title("💰 Accountant Dashboard")

    tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "💳 Bills", "💸 Expenses", "📈 Reports"])

    with tab1:
        st.subheader("Today's Financial Overview")
        today_stats = get_today_billing_summary()
        if today_stats:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("💰 Total Billed", f"₹{today_stats.get('total',0):,.2f}")
            c2.metric("✅ Collected", f"₹{today_stats.get('collected',0):,.2f}")
            c3.metric("⏳ Pending", f"₹{today_stats.get('pending',0):,.2f}")
            c4.metric("📄 Bills", str(today_stats.get('count',0)))

        monthly = get_monthly_summary()
        if monthly:
            st.metric("📈 Monthly Net", f"₹{monthly.get('profit',0):,.2f}",
                     delta=f"Revenue: ₹{monthly.get('revenue',0):,.0f} / Expenses: ₹{monthly.get('expenses',0):,.0f}")

    with tab2:
        st.subheader("Recent Bills")
        bills = get_bills_for_date(date.today().isoformat())
        if bills:
            for b in bills[:20]:
                with st.container(border=True):
                    cols = st.columns([2, 1, 1, 1, 1])
                    cols[0].write(f"**{b.get('patient_name','')}**")
                    cols[1].write(f"Invoice: {b.get('invoice_number','')}")
                    cols[2].write(f"₹{b.get('total_amount',0):,.2f}")
                    cols[3].write(b.get("bill_date",""))
                    status = b.get("status","")
                    cols[4].write(f"✅ {status}" if status == "paid" else f"⏳ {status}")

    with tab3:
        st.subheader("Record Expense")
        category = st.selectbox("Category", EXPENSE_CATEGORIES)
        description = st.text_input("Description*")
        amount = st.number_input("Amount (₹)*", min_value=1.0, step=100.0)
        exp_date = st.date_input("Date", date.today())
        paid_to = st.text_input("Paid To")
        pmode = st.selectbox("Payment Mode", ["cash", "bank transfer", "card", "UPI", "cheque"])
        notes = st.text_area("Notes")

        if st.button("💸 Record Expense", type="primary"):
            if not description or amount <= 0:
                st.error("Description and amount required.")
            else:
                r = add_expense(category, description, amount,
                               exp_date.isoformat(), paid_to, pmode, notes)
                if r.get("success"):
                    st.success(r["message"])
                    st.rerun()
                else:
                    st.error(r.get("message"))

        st.divider()
        st.subheader("Recent Expenses")
        expenses = get_expenses()
        if expenses:
            for e in expenses[:10]:
                with st.container(border=True):
                    cols = st.columns([1.5, 2, 1, 1])
                    cols[0].write(f"**{e.get('category','')}**")
                    cols[1].write(e.get("description",""))
                    cols[2].write(f"₹{e.get('amount',0):,.2f}")
                    cols[3].write(e.get("expense_date",""))

    with tab4:
        st.subheader("Financial Reports")
        rpt_month = st.selectbox("Month", range(1,13), index=date.today().month-1)
        rpt_year = st.number_input("Year", min_value=2024, max_value=2030, value=date.today().year)
        summary = get_monthly_summary(rpt_month, rpt_year)
        if summary:
            c1, c2, c3 = st.columns(3)
            c1.metric("Revenue", f"₹{summary.get('revenue',0):,.2f}")
            c2.metric("Expenses", f"₹{summary.get('expenses',0):,.2f}")
            c3.metric("Net Profit", f"₹{summary.get('profit',0):,.2f}",
                     delta=f"{((summary.get('profit',0)/summary.get('revenue',1))*100):.1f}% margin")
