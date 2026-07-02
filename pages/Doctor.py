"""
Doctor Dashboard — Report Management
======================================
The doctor sees pending reports (tests completed, awaiting report approval),
marks them as "Report Ready", and then marks as "Delivered" when handed over.

All actions go through llm_harness.py — no direct DB calls.
"""
import streamlit as st
from datetime import datetime

from llm_harness import get_harness
from utils.config import HOSPITAL_NAME, STATUS_ICONS, STATUS_LABELS


def show():
    harness = get_harness()
    today = datetime.now().strftime("%d-%b-%Y %I:%M %p")

    st.title("🩺 Doctor Dashboard")
    st.caption(f"{HOSPITAL_NAME} — {today}")

    # Auto-refresh every 10 seconds
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=10000, key="refresh_doctor")
    except ImportError:
        pass

    # Get dashboard data
    dashboard = harness.get_doctor_dashboard()
    pending = dashboard["pending_reports"]
    reports_ready = dashboard["reports_ready"]

    # ─── Section 1: Pending Reports (completed, awaiting doctor approval) ────
    st.subheader("📋 Pending Reports")

    if pending:
        for test in pending:
            p = test.get("patients", {})
            p_name = p.get("name", "Unknown")
            p_mobile = p.get("mobile", "")
            test_name = test.get("test_name", "")
            token = test.get("token_number", 0)
            completed_at = test.get("completed_at", "")

            with st.container(border=True):
                cols = st.columns([2, 1, 1, 1])

                with cols[0]:
                    st.markdown(f"**{p_name}** — {test_name} (Token #{token})")
                    st.caption(f"Mobile: {p_mobile}")

                with cols[1]:
                    if completed_at:
                        try:
                            ct = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
                            elapsed = (datetime.utcnow() - ct.replace(tzinfo=None)).seconds // 60
                            st.markdown(f"✅ Completed {elapsed} min ago")
                        except Exception:
                            st.markdown("✅ Completed")

                with cols[2]:
                    if st.button("📋 Report Ready", key=f"ready_{test['id']}",
                                 type="primary", use_container_width=True):
                        result = harness.mark_report_ready(
                            test["id"], p_name, test_name,
                            p_mobile, test.get("patient_id", "")
                        )
                        if result["success"]:
                            st.success(result["message"])
                            if result.get("notification"):
                                script = harness.get_notification_script(
                                    "📋 Report Ready", result["notification"],
                                    urgent=True
                                )
                                st.markdown(script, unsafe_allow_html=True)
                            st.rerun()
                        else:
                            st.error(result["message"])

                with cols[3]:
                    st.markdown(f"🏥 {test_name}")
    else:
        st.info("✅ No pending reports. All completed tests have been processed.")

    st.divider()

    # ─── Section 2: Reports Ready (awaiting delivery) ────────────────────────
    st.subheader("📄 Reports Ready for Delivery")

    if reports_ready:
        for test in reports_ready:
            p = test.get("patients", {})
            p_name = p.get("name", "Unknown")
            p_mobile = p.get("mobile", "")
            test_name = test.get("test_name", "")
            token = test.get("token_number", 0)
            ready_at = test.get("report_ready_at", "")

            with st.container(border=True):
                cols = st.columns([2, 1, 1, 1])

                with cols[0]:
                    st.markdown(f"**{p_name}** — {test_name} (Token #{token})")
                    st.caption(f"Mobile: {p_mobile}")

                with cols[1]:
                    if ready_at:
                        try:
                            rt = datetime.fromisoformat(ready_at.replace("Z", "+00:00"))
                            elapsed = (datetime.utcnow() - rt.replace(tzinfo=None)).seconds // 60
                            st.markdown(f"📋 Ready {elapsed} min ago")
                        except Exception:
                            st.markdown("📋 Report Ready")

                with cols[2]:
                    if st.button("📄 Delivered", key=f"deliver_{test['id']}",
                                 type="primary", use_container_width=True):
                        result = harness.deliver_report(test["id"])
                        if result["success"]:
                            st.success(result["message"])
                            st.rerun()
                        else:
                            st.error(result["message"])

                with cols[3]:
                    st.markdown(f"🏥 {test_name}")
    else:
        st.info("📭 No reports awaiting delivery.")

    # ─── Sidebar Stats ───────────────────────────────────────────────────────
    with st.sidebar:
        st.divider()
        st.markdown("### 📊 Summary")
        st.metric("Pending Reports", len(pending))
        st.metric("Ready for Delivery", len(reports_ready))
        st.metric("Total Awaiting Action", len(pending) + len(reports_ready))

        st.divider()
        st.caption("💡 **Tip:** Mark reports as 'Ready' as soon as you review them.")
