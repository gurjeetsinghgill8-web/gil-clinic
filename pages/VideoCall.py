"""
Video Call / Telemedicine Page
================================
"""
import streamlit as st
from utils.video_call import create_room, start_room, end_room, get_rooms

st.set_page_config("Telemedicine", layout="wide")


def show():
    st.title("🎥 Telemedicine / Video Call")

    tab1, tab2 = st.tabs(["🆕 New Room", "📋 Room History"])

    with tab1:
        st.subheader("Create Video Consultation Room")
        patient_name = st.text_input("Patient Name*")
        doctor_name = st.text_input("Doctor Name")
        with st.container(border=True):
            st.markdown("**Room Info**")
            st.info("After creating the room, share the room name with the patient to join.")
            if st.button("🎥 Create Room", type="primary"):
                if not patient_name:
                    st.error("Patient name is required.")
                else:
                    r = create_room(patient_name, doctor_name)
                    if r.get("success"):
                        st.success(r["message"])
                        st.code(f"Room: {r.get('room_name','')}")
                        st.info("📱 Share this room name with the patient")
                        st.markdown("""
                        **Joining Instructions:**
                        1. Open the link in a browser
                        2. Enter the room name
                        3. Allow camera/mic permissions
                        4. Wait for the doctor to join
                        """)
                    else:
                        st.error(r.get("message"))

    with tab2:
        st.subheader("Consultation History")
        rooms = get_rooms()
        if not rooms:
            st.info("No consultations yet.")
        else:
            for r in rooms:
                status = r.get("status", "")
                status_icon = {"scheduled": "📅", "active": "🟢", "completed": "✅"}.get(status, "❓")
                with st.container(border=True):
                    cols = st.columns([2, 1.5, 1, 1.5, 1])
                    cols[0].write(f"🎥 {r.get('room_name','')}")
                    cols[1].write(f"{status_icon} {status.upper()}")
                    cols[2].write(r.get("patient_id","")[:8] if r.get("patient_id") else "-")
                    cols[3].write(r.get("created_at","")[:10] if r.get("created_at") else "")
                    if status == "scheduled":
                        if cols[4].button("▶️ Start", key=f"start_{r['id']}"):
                            start_room(r["room_name"])
                            st.rerun()
                    elif status == "active":
                        if cols[4].button("⏹ End", key=f"end_{r['id']}"):
                            end_room(r["room_name"])
                            st.rerun()
