"""
Patient Visit History — Past Visits Lookup
============================================
Search by mobile number to see a patient's complete visit history
across all dates. Each visit shows tests, statuses, and timestamps.

Access: Reception, Manager, Admin roles.
Architecture: UI → llm_harness.py → db.py (via Harness Engineering).
"""
import streamlit as st
from datetime import datetime

from llm_harness import get_harness
from utils.config import TEST_TYPES, STATUS_ICONS, STATUS_LABELS, HOSPITAL_NAME


def show():
    harness = get_harness()
    now = datetime.now()
    today = now.strftime("%d-%b-%Y %I:%M %p")

    st.title("📋 Patient Visit History")
    st.markdown(f"### {HOSPITAL_NAME}")
    st.caption(f"🗓️ {today}")

    st.markdown(
        "मोबाइल नंबर डालें और मरीज़ के पिछले सभी विज़िट देखें — "
        "Enter a mobile number to see all past visits."
    )

    # ─── Mobile Input ──────────────────────────────────────────────────────────
    mobile = st.text_input(
        "📱 Mobile Number",
        placeholder="10-digit mobile number — auto-searches on 10 digits",
        max_chars=10,
        key="history_mobile",
    )

    if not mobile or len(mobile) != 10 or not mobile.isdigit():
        if mobile:
            st.info("⏳ कृपया 10 अंक पूरे करें / Please complete 10 digits")
        else:
            st.info("🔍 ऊपर मोबाइल नंबर डालें / Enter a mobile number above")
        return

    # ─── Fetch Visit History ──────────────────────────────────────────────────
    with st.spinner("🔍 Searching all visits..."):
        visits = harness.get_patient_visit_history(mobile)

    if not visits:
        st.warning("⚠️ इस नंबर पर कोई इतिहास नहीं मिला / No visit history found for this number")
        st.markdown(
            "यह मरीज़ पहली बार आया है या नंबर गलत है। "
            "This patient may be visiting for the first time, or the number is incorrect."
        )
        return

    # ─── Summary Header ───────────────────────────────────────────────────────
    total_visits = len(visits)
    patient_name = visits[0]["visit"].get("name", "Unknown")
    total_tests = sum(len(v["tests"]) for v in visits)

    st.success(f"👤 **{patient_name}** — {total_visits} visit(s), {total_tests} total test(s)")
    st.divider()

    # ─── Render Each Visit ────────────────────────────────────────────────────
    for idx, v in enumerate(visits):
        visit = v["visit"]
        tests = v["tests"]
        date_str = v["date_str"]

        name = visit.get("name", "Unknown")
        age = visit.get("age", "—")
        gender = visit.get("gender", "—")
        pid = visit.get("patient_id", "")
        reg_date = visit.get("registration_date", "")

        with st.container(border=True):
            # Visit header
            completed_count = sum(1 for t in tests if t["status"] in ("completed", "report_ready", "delivered"))
            col_h1, col_h2 = st.columns([3, 1])
            with col_h1:
                st.markdown(
                    f"### 🗓️ Visit #{total_visits - idx} — {date_str}"
                )
                st.markdown(
                    f"👤 {name} ({age}/{gender}) &nbsp;|&nbsp; 🆔 `{pid}`"
                )
            with col_h2:
                st.markdown(
                    f"<div style='text-align:right;font-size:0.9rem;"
                    f"background:linear-gradient(135deg,#667eea,#764ba2);"
                    f"color:white;padding:6px 14px;border-radius:20px;"
                    f"font-weight:600;display:inline-block;float:right;'>"
                    f"✅ {completed_count}/{len(tests)} done"
                    f"</div>",
                    unsafe_allow_html=True,
                )

            if not tests:
                st.caption("No tests were booked for this visit.")
                continue

            # Test table
            st.markdown("---")
            test_cols = st.columns([1.5, 2.5, 1.5, 1.5, 2])
            headers = ["Test", "Token #", "Room", "Status", "Timestamp"]
            for ci, h in enumerate(headers):
                test_cols[ci].markdown(
                    f"<span style='font-size:0.75rem;text-transform:uppercase;"
                    f"color:#888;font-weight:600;'>{h}</span>",
                    unsafe_allow_html=True,
                )

            for t in tests:
                tname = t.get("test_name", "?")
                token = t.get("token_number", "?")
                room = t.get("room", "—")
                status = t.get("status", "waiting")
                icon = STATUS_ICONS.get(status, "❓")
                label = STATUS_LABELS.get(status, status)

                # Find the most recent meaningful timestamp
                ts = (
                    t.get("delivered_at") or
                    t.get("report_ready_at") or
                    t.get("completed_at") or
                    t.get("started_at") or
                    t.get("called_at") or
                    t.get("created_at") or
                    ""
                )
                if ts:
                    try:
                        ts_dt = datetime.fromisoformat(ts)
                        ts_display = ts_dt.strftime("%I:%M %p").lstrip("0")
                    except Exception:
                        ts_display = "—"
                else:
                    ts_display = "—"

                cols = st.columns([1.5, 2.5, 1.5, 1.5, 2])
                cols[0].markdown(f"**{tname}**")
                cols[1].markdown(f"`#{token:03d}`" if isinstance(token, int) else f"`#{token}`")
                cols[2].markdown(f"<span style='font-size:0.85rem;'>{room}</span>", unsafe_allow_html=True)
                cols[3].markdown(f"{icon} {label}")
                cols[4].markdown(f"<span style='font-size:0.85rem;color:#666;'>{ts_display}</span>", unsafe_allow_html=True)

                # Show doctor notes if present
                notes = t.get("doctor_notes", "").strip()
                if notes:
                    st.markdown(
                        f"<div style='background:rgba(102,126,234,0.06);border-left:3px solid #667eea;"
                        f"padding:4px 12px;margin:0 0 6px 0;border-radius:4px;font-size:0.85rem;'>"
                        f"📝 <strong>Dr:</strong> {notes}</div>",
                        unsafe_allow_html=True,
                    )

            # Registration timestamp
            if reg_date:
                st.caption(f"📅 Registered: {reg_date}")

    # ─── Footer ───────────────────────────────────────────────────────────────
    st.divider()
    st.caption(f"🔍 Showing {total_visits} visit(s) for 📱 {mobile}")
