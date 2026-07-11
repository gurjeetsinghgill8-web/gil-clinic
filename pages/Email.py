"""
Email Dashboard — Send Emails, View Log
==========================================
"""
import streamlit as st
from utils.email import send_email, get_email_log

st.set_page_config("Email Dashboard", layout="wide")


def show():
    st.title("📧 Email Dashboard")

    tab1, tab2 = st.tabs(["📨 Send Email", "📋 Email Log"])

    with tab1:
        st.subheader("Send Email")
        recipient = st.text_input("Recipient Email*")
        subject = st.text_input("Subject*")
        body = st.text_area("Message Body (HTML supported)*", height=200,
                            placeholder="<h2>Hello</h2><p>Your report is ready...</p>")
        col1, col2 = st.columns(2)
        with col1:
            is_html = st.checkbox("HTML Format", True)
        with col2:
            attachment = st.file_uploader("Attachment (optional)")

        if st.button("📨 Send Email", type="primary"):
            if not recipient or not subject or not body:
                st.error("Recipient, subject, and body are required.")
            else:
                r = send_email(recipient, subject, body_html=body if is_html else "",
                               body_text=body if not is_html else "")
                if r.get("success"):
                    st.success(r["message"])
                else:
                    st.error(r.get("message", "Failed to send"))

    with tab2:
        st.subheader("Email Log")
        log = get_email_log()
        if not log:
            st.info("No emails sent yet.")
        else:
            for e in log:
                with st.container(border=True):
                    cols = st.columns([2, 2, 1, 1])
                    cols[0].write(f"**To:** {e.get('recipient','')}")
                    cols[1].write(f"**Subject:** {e.get('subject','')}")
                    cols[2].write(f"**{e.get('status','').upper()}**")
                    cols[3].write(e.get("sent_at","")[:10] if e.get("sent_at") else "")
                    if e.get("error"):
                        st.caption(f"❌ Error: {e['error']}")
