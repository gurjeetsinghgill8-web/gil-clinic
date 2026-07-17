"""
Push Notification Dashboard
=============================
"""
import streamlit as st
from utils.push_notifications import (register_device, send_push_notification,
                                       broadcast_notification, get_notification_log,
                                       NOTIFICATION_CATEGORIES)

try:
    st.set_page_config("Push Notifications", layout="wide")
except Exception:
    pass


def show():
    st.title("🔔 Push Notifications")

    tab1, tab2, tab3 = st.tabs(["📨 Send", "📡 Devices", "📋 Log"])

    with tab1:
        st.subheader("Send Notification")
        mode = st.radio("Mode", ["Single Device", "Broadcast"], horizontal=True)

        if mode == "Single Device":
            device_token = st.text_input("Device Token")
        title = st.text_input("Title*")
        body = st.text_area("Message Body*")
        category = st.selectbox("Category", list(NOTIFICATION_CATEGORIES.keys()))
        data_key = st.text_input("Data Key (optional)")
        data_val = st.text_input("Data Value (optional)")

        if st.button("🔔 Send", type="primary"):
            if not title or not body:
                st.error("Title and body are required.")
            else:
                data = {data_key: data_val} if data_key and data_val else None
                if mode == "Single Device" and device_token:
                    r = send_push_notification(device_token, title, body, category, data)
                else:
                    r = broadcast_notification(title, body, category, data)
                if r.get("success"):
                    st.success(f"✅ Sent to {r.get('sent',1)} device(s)")
                else:
                    st.error(r.get("message", "Failed"))

    with tab2:
        st.subheader("Register Test Device")
        test_token = st.text_input("Device Token", key="reg_token",
                                   placeholder="browser-fcm-token-xxx")
        platform = st.selectbox("Platform", ["web", "android", "ios"])
        if st.button("📡 Register Device"):
            r = register_device(test_token, platform)
            if r.get("success"):
                st.success("✅ Device registered")
            else:
                st.error(r.get("message"))

    with tab3:
        st.subheader("Notification Log")
        log = get_notification_log()
        if not log:
            st.info("No notifications sent yet.")
        else:
            for n in log[:30]:
                with st.container(border=True):
                    icon = NOTIFICATION_CATEGORIES.get(n.get("category","general"), {}).get("icon","ℹ️")
                    cols = st.columns([3, 2, 1, 1])
                    cols[0].write(f"{icon} **{n.get('title','')}**")
                    cols[1].write(n.get("body","")[:60])
                    cols[2].write(f"**{n.get('status','').upper()}**")
                    cols[3].write(n.get("created_at","")[:10] if n.get("created_at") else "")
