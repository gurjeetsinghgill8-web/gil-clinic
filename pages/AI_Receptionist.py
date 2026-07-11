"""
AI Receptionist — Smart Greeting & FAQ Assistant
"""
import streamlit as st
from datetime import datetime

from utils.config import HOSPITAL_NAME
from utils.ai_receptionist import process_query, get_reception_log


def show():
    now = datetime.now().strftime("%d-%b-%Y %I:%M %p")

    st.title("🤖 AI Receptionist")
    st.markdown(f"### {HOSPITAL_NAME}")
    st.caption(f"🗓️ {now}")

    tab1, tab2 = st.tabs(["💬 Chat", "📋 Query Log"])

    with tab1:
        show_chat()
    with tab2:
        show_log()


def show_chat():
    st.subheader("💬 AI Receptionist Chat")

    if "ai_chat" not in st.session_state:
        st.session_state.ai_chat = []

    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Your Name", placeholder="Optional", key="ai_r_name")
    with col2:
        mobile = st.text_input("Mobile", max_chars=10, placeholder="Optional", key="ai_r_mobile")

    for msg in st.session_state.ai_chat:
        role = msg["role"]
        with st.chat_message("user" if role == "user" else "assistant"):
            st.markdown(msg["content"])

    query = st.chat_input("Ask me anything... (e.g., 'Clinic timings?', 'Book appointment?')")
    if query:
        st.session_state.ai_chat.append({"role": "user", "content": query})
        with st.chat_message("user"):
            st.markdown(query)

        result = process_query(name, mobile, query)
        response = result["response"]
        st.session_state.ai_chat.append({"role": "assistant", "content": response})
        with st.chat_message("assistant"):
            st.markdown(response)

        if result["intent"] == "emergency":
            st.error("🚑 **EMERGENCY** — Please call 108 immediately!")
            st.balloons()


def show_log():
    st.subheader("📋 Query Log")
    log = get_reception_log()
    if not log:
        st.info("No queries yet.")
        return

    for entry in log:
        with st.container(border=True):
            cols = st.columns([2, 1, 3])
            with cols[0]:
                st.markdown(f"**{entry.get('patient_name', '?')}**")
                st.caption(entry.get('created_at', '')[:19])
            with cols[1]:
                st.caption(f"Intent: {entry.get('intent', '')}")
            with cols[2]:
                st.markdown(f"Q: {entry.get('query', '')}")
                st.caption(f"A: {entry.get('response', '')}")
