"""
Finance Dashboard — P&L, Expenses, Revenue
===========================================
"""
import streamlit as st
from utils.finance import add_expense, get_expenses, get_monthly_summary, EXPENSE_CATEGORIES
from utils.billing import get_today_billing_summary
import datetime

st.set_page_config("Finance", layout="wide")


def show():
    st.title("📊 Finance Dashboard")

    tab1, tab2, tab3 = st.tabs(["📈 P&L Summary", "💰 Add Expense", "📋 Expense Log"])

    with tab1:
        st.subheader("Profit & Loss Summary")

        col_m, col_y = st.columns(2)
        with col_m:
            sel_month = st.selectbox("Month", range(1,13),
                                    index=datetime.date.today().month-1,
                                    format_func=lambda m: datetime.date(2000,m,1).strftime("%B"))
        with col_y:
            sel_year = st.number_input("Year", min_value=2020, max_value=2030,
                                       value=datetime.date.today().year)

        summary = get_monthly_summary(sel_month, sel_year)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("💰 Revenue", f"₹{summary['revenue']:,.2f}")
        m2.metric("💸 Expenses", f"₹{summary['expenses']:,.2f}")
        m3.metric("📈 Net Profit", f"₹{summary['profit']:,.2f}",
                  delta=f"{((summary['profit']/summary['revenue'])*100 if summary['revenue'] else 0):.1f}% margin")

        st.caption(f"Period: {datetime.date(sel_year, sel_month, 1).strftime('%B %Y')}")

        today_vals = get_today_billing_summary()
        if today_vals:
            st.subheader("Today's Revenue")
            c1, c2 = st.columns(2)
            c1.metric("Today's Bills", f"₹{today_vals.get('total',0):,.2f}")
            c2.metric("Pending", f"₹{today_vals.get('pending',0):,.2f}")

    with tab2:
        st.subheader("Record Expense")
        category = st.selectbox("Category*", EXPENSE_CATEGORIES)
        description = st.text_input("Description*")
        amount = st.number_input("Amount (₹)*", min_value=1.0, step=100.0)
        expense_date = st.date_input("Date", datetime.date.today())
        paid_to = st.text_input("Paid To")
        payment_mode = st.selectbox("Payment Mode", ["cash", "bank transfer", "card", "UPI", "cheque", "other"])
        notes = st.text_area("Notes")

        if st.button("💸 Record Expense", type="primary"):
            if not description or amount <= 0:
                st.error("Description and amount are required.")
            else:
                r = add_expense(category, description, amount,
                               expense_date.isoformat(), paid_to, payment_mode, notes)
                if r.get("success"):
                    st.success(r["message"])
                    st.rerun()
                else:
                    st.error(r.get("message", "Failed to record expense"))

    with tab3:
        st.subheader("Expense Log")
        month_e = st.selectbox("Filter Month", range(1,13),
                               index=datetime.date.today().month-1, key="exp_month")
        year_e = st.number_input("Year", min_value=2020, max_value=2030,
                                 value=datetime.date.today().year, key="exp_year")

        expenses = get_expenses(month_e, year_e)
        if not expenses:
            st.info("No expenses recorded for this period.")
        else:
            total_exp = sum(e.get("amount",0) for e in expenses)
            st.metric("Total Expenses", f"₹{total_exp:,.2f}")

            for e in expenses:
                with st.container(border=True):
                    cols = st.columns([1.5, 2, 1, 1, 1])
                    cols[0].write(f"**{e.get('category','')}**")
                    cols[1].write(e.get("description",""))
                    cols[2].write(f"₹{e.get('amount',0):,.2f}")
                    cols[3].write(e.get("expense_date",""))
                    cols[4].write(e.get("payment_mode",""))
                    if e.get("notes"):
                        st.caption(f"📝 {e['notes']}")
