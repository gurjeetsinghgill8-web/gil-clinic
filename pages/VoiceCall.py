"""
Voice Call Page — Call Log, Initiate Calls
=============================================
"""
import streamlit as st
from utils.voice_call import initiate_call, update_call_status, get_call_log

st.set_page_config("Voice Calls", layout="wide")


def show():
    st.title("📞 Voice Call Center")

    tab1, tab2 = st.tabs(["📞 Initiate Call", "📋 Call Log"])

    with tab1:
        st.subheader("Initiate a Call")
        to_number = st.text_input("Phone Number*", placeholder="+919876543210")
        call_type = st.selectbox("Call Type", ["notification", "appointment_reminder",
                                                "follow_up", "missed_call_alert", "other"])
        notes = st.text_area("Notes (optional)")
        if st.button("📞 Call Now", type="primary"):
            if not to_number:
                st.error("Phone number is required.")
            else:
                r = initiate_call(to_number, call_type=call_type, notes=notes)
                if r.get("success"):
                    st.success(r["message"])
                    st.balloons()
                else:
                    st.error(r.get("message", "Call failed"))

    with tab2:
        st.subheader("Call History")
        calls = get_call_log()
        if not calls:
            st.info("No calls recorded yet.")
        else:
            for c in calls[:30]:
                status = c.get("status", "")
                status_icon = {"initiated": "🆕", "ringing": "🔔", "completed": "✅",
                               "failed": "❌", "missed": "📵"}.get(status, "❓")
                with st.container(border=True):
                    cols = st.columns([2, 1.5, 1, 1, 1])
                    cols[0].write(f"📞 {c.get('to_number','')}")
                    cols[1].write(f"{status_icon} {status.upper()}")
                    cols[2].write(f"⏱ {c.get('duration',0)}s")
                    cols[3].write(c.get("call_type",""))
                    cols[4].write(c.get("created_at","")[:16] if c.get("created_at") else "")
