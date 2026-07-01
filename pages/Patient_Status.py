"""
Patient Status Page — Self-Service
====================================
Patients enter their mobile number to see:
  - Status of each test (Waiting, Called, In Progress, Completed, Report Ready)
  - Estimated wait time
  - Room information

No login required — this is a public page.
"""
import streamlit as st
from datetime import datetime

from llm_harness import get_harness
from utils.config import HOSPITAL_NAME, STATUS_ICONS, STATUS_LABELS, ROOM_NAMES, AVG_TEST_TIME
from utils.queue import calculate_wait_time


def show():
    harness = get_harness()
    today = datetime.now().strftime("%d-%b-%Y %I:%M %p")

    st.title("🔍 Patient Status")
    st.caption(f"{HOSPITAL_NAME} — {today}")
    st.markdown(
        "Enter your registered mobile number to check the status of your tests."
    )

    st.divider()

    # ─── Mobile Input ────────────────────────────────────────────────────────
    mobile = st.text_input(
        "📱 Your Mobile Number",
        placeholder="Enter 10-digit mobile number",
        max_chars=10,
        key="patient_mobile",
        help="Enter the mobile number you registered with.",
    )

    col1, col2 = st.columns([1, 3])

    with col1:
        check_clicked = st.button("🔍 Check Status", type="primary",
                                  use_container_width=True)

    # ─── Display Status ──────────────────────────────────────────────────────
    if check_clicked or mobile:
        if not mobile or len(mobile) != 10 or not mobile.isdigit():
            st.warning("⚠️ Please enter a valid 10-digit mobile number.")
            return

        result = harness.get_patient_status(mobile)

        if not result["found"]:
            st.error("❌ No patient found with this mobile number.")
            st.info(
                "If you've just registered, please wait a moment and try again. "
                "Make sure the number matches what was entered at reception."
            )
            return

        patient = result["patient"]
        tests = result["tests"]

        # ─── Patient Info Card ───────────────────────────────────────────────
        with st.container(border=True):
            cols = st.columns(3)
            with cols[0]:
                st.markdown(f"### 👤 {patient['name']}")
            with cols[1]:
                st.markdown(f"**Patient ID:** `{patient['patient_id']}`")
            with cols[2]:
                st.markdown(f"**Date:** {patient.get('registration_date', '')}")

        st.divider()

        # ─── Test Status Cards ───────────────────────────────────────────────
        st.subheader("📋 Your Test Status")

        if not tests:
            st.info("📭 No tests registered yet.")
            return

        # Calculate overall max wait time
        max_wait = max((t.get("wait_time", 0) for t in tests), default=0)

        for test in tests:
            test_name = test["test_name"]
            status = test["status"]
            token = test.get("token_number", 0)
            room = ROOM_NAMES.get(test_name, f"{test_name} Room")
            wait_time = calculate_wait_time(test_name, test.get("queue_position", 0))
            pos = test.get("queue_position", 0)

            # Color border based on status
            border_color = {
                "waiting": "#FFA500",
                "called": "#2196F3",
                "in_progress": "#FF9800",
                "completed": "#4CAF50",
                "report_ready": "#9C27B0",
                "delivered": "#607D8B",
            }.get(status, "#E0E0E0")

            with st.container(border=True):
                st.markdown(
                    f"""
                    <div style="border-left: 5px solid {border_color}; padding-left: 15px;">
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                cols = st.columns([2, 1, 1, 1])

                with cols[0]:
                    st.markdown(f"### {test_name}")
                    st.caption(f"Room: {room} | Token: #{token}")

                with cols[1]:
                    status_icon = STATUS_ICONS.get(status, "❓")
                    status_label = STATUS_LABELS.get(status, status.replace("_", " ").title())
                    st.markdown(f"### {status_icon}")
                    st.markdown(f"**{status_label}**")

                with cols[2]:
                    if status in ["waiting", "called"]:
                        st.markdown(f"### ⏱️")
                        st.markdown(f"**~{wait_time} min**")
                        st.caption(f"Position: #{pos}")
                    elif status == "in_progress":
                        st.markdown(f"### 🔄")
                        st.markdown("**In Progress**")
                    elif status == "completed":
                        st.markdown(f"### ✅")
                        st.markdown("**Done**")
                    elif status == "report_ready":
                        st.markdown(f"### 📋")
                        st.markdown("**Collect at Counter**")

                with cols[3]:
                    # Progress indicator
                    status_order = ["waiting", "called", "in_progress",
                                    "completed", "report_ready", "delivered"]
                    try:
                        current_idx = status_order.index(status)
                        progress = (current_idx + 1) / len(status_order)
                        st.markdown(f"**Progress**")
                        st.progress(progress, text=f"{int(progress * 100)}%")
                    except ValueError:
                        pass

        # ─── Overall Status Summary ──────────────────────────────────────────
        st.divider()
        st.subheader("📊 Summary")

        all_completed = all(t["status"] in ["completed", "report_ready", "delivered"]
                           for t in tests)
        any_in_progress = any(t["status"] == "in_progress" for t in tests)

        if all_completed:
            st.success("🎉 All your tests are complete! Please collect reports from reception.")
        elif any_in_progress:
            st.info("🔄 Some tests are in progress. Please wait for your turn.")
        else:
            st.info(f"⏳ Estimated total wait time: **~{max_wait} minutes**")

        st.caption(
            "⚠️ Wait times are estimates only. Actual times may vary based on "
            "department workload."
        )

    # ─── Instructions ────────────────────────────────────────────────────────
    if not mobile and not check_clicked:
        with st.container(border=True):
            st.markdown("""
            ### ℹ️ How to Use

            1. Enter the **mobile number** you registered with at reception.
            2. Click **Check Status**.
            3. You'll see the live status of all your tests.

            **Status Meanings:**
            - 🟡 **Waiting** — You're in the queue
            - 🔵 **Called** — Please proceed to the test room
            - 🟠 **In Progress** — Test is being performed
            - ✅ **Completed** — Test is done
            - 📋 **Report Ready** — Your report is ready at reception

            *No login or app download needed.*
            """)
