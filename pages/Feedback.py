"""
Patient Feedback Page
======================
Collect and display patient feedback with star ratings and category selection.

Two modes:
  1. Patient-facing form: link from status page after test completion
  2. Staff dashboard: view all feedback with filters and acknowledgment

Access: Manager, Admin (staff view)
        Patients via link (submit only)
"""
import streamlit as st
from datetime import datetime

from llm_harness import get_harness
from utils.config import HOSPITAL_NAME, TEST_TYPES
from utils.feedback import (
    submit_feedback, get_all_feedback, get_feedback_stats,
    acknowledge_feedback, FEEDBACK_CATEGORIES
)


def show_staff_dashboard():
    """Manager/Admin view — feedback analytics and management."""
    harness = get_harness()
    now = datetime.now()
    today = now.strftime("%d-%b-%Y %I:%M %p")

    st.title("⭐ Patient Feedback")
    st.markdown(f"### {HOSPITAL_NAME}")
    st.caption(f"🗓️ {today}")

    # ─── Auto-refresh ──────────────────────────────────────────────────────────
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=15000, key="refresh_feedback")
    except ImportError:
        pass

    # ─── Filters ───────────────────────────────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    with col1:
        dept_filter = st.selectbox("Department", ["All"] + TEST_TYPES, index=0)
    with col2:
        rating_filter = st.selectbox("Min Rating", [0, 1, 2, 3, 4, 5], index=0,
                                     format_func=lambda x: "All" if x == 0 else f"{x} ★")
    with col3:
        st.markdown("### ")
        refresh = st.button("🔄 Refresh", use_container_width=True)
        if refresh:
            st.rerun()

    dept = dept_filter if dept_filter != "All" else ""
    min_rating = rating_filter

    # ─── Stats Cards ───────────────────────────────────────────────────────────
    stats = get_feedback_stats()
    if stats:
        st.markdown("### 📊 Satisfaction Overview")
        cols = st.columns(len(stats))
        for col, stat in zip(cols, stats):
            with col:
                avg = stat.get("avg_rating", 0)
                total = stat.get("total_count", 0)
                color = "#4CAF50" if avg >= 4 else "#FF9800" if avg >= 3 else "#FF5722"
                st.markdown(f"""
                <div style="background:linear-gradient(135deg,{color}15,{color}08);
                            border:1px solid {color}30;border-radius:10px;padding:0.75rem;text-align:center;">
                    <div style="font-size:1.6rem;font-weight:700;color:{color};">{avg:.1f}</div>
                    <div style="font-size:0.8rem;color:#666;">{stat.get('dept_name', '?')}</div>
                    <div style="font-size:0.7rem;color:#999;">{total} reviews</div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("📊 No feedback data yet for today.")

    st.divider()

    # ─── Feedback List ─────────────────────────────────────────────────────────
    st.subheader("📝 Recent Feedback")

    feedback_list = get_all_feedback(limit=50, dept=dept, min_rating=min_rating)

    if not feedback_list:
        st.success("✅ No feedback entries matching your filters.")
        return

    for fb in feedback_list:
        rating = fb.get("rating", 0)
        stars = "⭐" * rating + "☆" * (5 - rating)
        patient_name = fb.get("patient_name", "Unknown")
        dept_name = fb.get("test_name", "—")
        category = fb.get("category", "general")
        cat_label = next((c[1] for c in FEEDBACK_CATEGORIES if c[0] == category), category)
        comments = fb.get("comments", "")
        acknowledged = fb.get("acknowledged", 0)
        created = fb.get("created_at", "")
        fb_id = fb.get("id", "")

        # Format timestamp
        try:
            dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            time_str = dt.strftime("%d-%b %I:%M %p")
        except Exception:
            time_str = created

        with st.container(border=True):
            cols = st.columns([3, 1, 1])
            with cols[0]:
                st.markdown(f"**{patient_name}** — {cat_label} ({dept_name})")
                st.markdown(f"{stars}")
                if comments:
                    st.markdown(f"*“{comments}”*")
            with cols[1]:
                st.caption(time_str)
                if acknowledged:
                    st.success("✅ Seen")
                else:
                    st.warning("⏳ New")
            with cols[2]:
                if not acknowledged:
                    if st.button("✅ Acknowledge", key=f"ack_{fb_id}", use_container_width=True):
                        if acknowledge_feedback(fb_id):
                            st.success("Marked as seen!")
                            st.rerun()
                        else:
                            st.error("Failed to acknowledge.")


def show_patient_form(patient_id: str, test_id: str, test_name: str):
    """
    Patient-facing feedback form.
    This is shown as an embedded section in Patient_Status.py after test completion.
    """
    st.markdown("---")
    st.subheader("⭐ How was your experience?")
    st.caption(f"Help us improve! Rate your {test_name} experience.")

    with st.form(key="feedback_form"):
        # Star rating
        rating = st.select_slider(
            "Rating",
            options=[1, 2, 3, 4, 5],
            value=5,
            format_func=lambda x: "⭐" * x + "☆" * (5 - x),
            help="Rate your experience from 1 (poor) to 5 (excellent)"
        )

        # Category
        cat_options = [c[0] for c in FEEDBACK_CATEGORIES]
        cat_labels = [c[1] for c in FEEDBACK_CATEGORIES]
        category_idx = st.selectbox(
            "What aspect would you like to rate?",
            options=list(range(len(cat_options))),
            format_func=lambda i: cat_labels[i],
            index=0
        )

        comments = st.text_area(
            "Any additional comments? (optional)",
            placeholder="Share your experience...",
            max_chars=500
        )

        submitted = st.form_submit_button("📤 Submit Feedback", type="primary", use_container_width=True)
        if submitted:
            result = submit_feedback(
                patient_id=patient_id,
                test_id=test_id,
                rating=rating,
                category=cat_options[category_idx],
                comments=comments.strip()
            )
            if result["success"]:
                st.success(result["message"])
                st.session_state.feedback_submitted = True
            else:
                st.error(result["message"])
                return False
            return True

    return False


def show():
    """Main entry point — routes between staff dashboard and patient form."""
    role = st.session_state.get("auth_role", "")

    # If there's a patient feedback context from URL params or session
    query_params = st.query_params
    fb_patient = query_params.get("fb_patient", None)
    fb_test_id = query_params.get("fb_test_id", None)
    fb_test_name = query_params.get("fb_test_name", None)

    if isinstance(fb_patient, list):
        fb_patient = fb_patient[0] if fb_patient else None
    if isinstance(fb_test_id, list):
        fb_test_id = fb_test_id[0] if fb_test_id else None
    if isinstance(fb_test_name, list):
        fb_test_name = fb_test_name[0] if fb_test_name else None

    # Check for patient feedback context (from status page)
    if fb_patient and fb_test_id and fb_test_name:
        # Patient role or any role accessing feedback form
        show_patient_form(fb_patient, fb_test_id, fb_test_name)
        return

    # Also check for session-based feedback context (set by Patient_Status page)
    if st.session_state.get("feedback_patient_id") and st.session_state.get("feedback_test_id"):
        if not st.session_state.get("feedback_submitted"):
            show_patient_form(
                patient_id=st.session_state.feedback_patient_id,
                test_id=st.session_state.feedback_test_id,
                test_name=st.session_state.get("feedback_test_name", "Test")
            )
            return

    # Staff dashboard for Manager/Admin
    if role in ("Manager", "Admin"):
        show_staff_dashboard()
    else:
        st.info("⭐ Feedback dashboard is available for Manager and Admin roles.")
        st.markdown("Patients can submit feedback from their **Patient Status** page after test completion.")
