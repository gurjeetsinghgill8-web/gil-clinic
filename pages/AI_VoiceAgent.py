"""
AI Voice Agent Page — Session Management
===========================================
"""
import streamlit as st
from utils.ai_voice_agent import (create_session, add_transcript_entry,
                                   end_session, get_sessions, AGENT_TYPES)

st.set_page_config("AI Voice Agent", layout="wide")


def show():
    st.title("🎙️ AI Voice Agent")

    tab1, tab2 = st.tabs(["🆕 New Session", "📋 Session History"])

    with tab1:
        st.subheader("Create Voice Agent Session")
        agent_type = st.selectbox("Agent Type", list(AGENT_TYPES.keys()),
                                  format_func=lambda x: AGENT_TYPES[x]["name"])
        patient_name = st.text_input("Patient Name")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🎙️ Start Session", type="primary"):
                r = create_session(agent_type, patient_name)
                if r.get("success"):
                    st.session_state.voice_session_id = r.get("session_id")
                    st.success(r["message"])
                    st.rerun()
                else:
                    st.error(r.get("message"))
        with col2:
            if st.button("⏹ End Current Session"):
                if "voice_session_id" in st.session_state:
                    end_session(st.session_state.voice_session_id)
                    del st.session_state.voice_session_id
                    st.success("Session ended")
                    st.rerun()

        if "voice_session_id" in st.session_state:
            st.divider()
            st.subheader("💬 Conversation Transcript")
            st.info("Active session — add transcript entries below")
            speaker = st.radio("Speaker", ["ai", "patient"], horizontal=True)
            text = st.text_area("Message")
            if st.button("➕ Add to Transcript"):
                r = add_transcript_entry(st.session_state.voice_session_id, speaker, text)
                if r.get("success"):
                    st.success("Added")
                    st.rerun()

    with tab2:
        st.subheader("Session History")
        sessions = get_sessions()
        if not sessions:
            st.info("No sessions recorded yet.")
        else:
            for s in sessions:
                status = s.get("status", "")
                agent_type = s.get("agent_type", "")
                agent_name = AGENT_TYPES.get(agent_type, {}).get("name", agent_type)
                with st.container(border=True):
                    cols = st.columns([2, 1.5, 1, 1, 1])
                    cols[0].write(f"**{agent_name}**")
                    cols[1].write(s.get("patient_name","") or "-")
                    cols[2].write(f"{'🟢' if status=='active' else '✅' if status=='completed' else '❓'} {status}")
                    cols[3].write(s.get("sentiment","") if s.get("sentiment") else "-")
                    cols[4].write(s.get("created_at","")[:10] if s.get("created_at") else "")
                    if s.get("needs_human"):
                        st.warning("👤 Needs human handoff")
