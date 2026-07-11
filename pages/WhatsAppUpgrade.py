import streamlit as st
from utils.whatsapp_upgrade import send_template, send_text, get_whatsapp_log, get_templates

st.set_page_config("WhatsApp Business", layout="wide")

def show():
    st.title("WhatsApp Business Cloud API")
    t1, t2, t3 = st.tabs(["Send Message", "Templates", "Message Log"])
    with t1:
        mode = st.radio("Mode", ["Template", "Text"], horizontal=True)
        to = st.text_input("Phone Number*", placeholder="919876543210")
        if mode == "Template":
            tmpl = st.selectbox("Template", [x.get("name","") for x in get_templates()] if get_templates() else ["none"])
            p1 = st.text_input("Param 1 (optional)")
            if st.button("Send Template", type="primary") and to:
                r = send_template(to, tmpl, [p1] if p1 else None)
                st.success("Sent") if r.get("success") else st.error(r.get("message", "Failed"))
        else:
            msg = st.text_area("Message*")
            if st.button("Send Text", type="primary") and to and msg:
                r = send_text(to, msg)
                st.success("Sent") if r.get("success") else st.error(r.get("message", "Failed"))
    with t2:
        st.info("WhatsApp templates must be approved by Meta before use.")
        for x in get_templates():
            with st.expander(x.get("name", "")):
                st.code(x.get("body", ""))
    with t3:
        for m in get_whatsapp_log()[:30]:
            with st.container(border=True):
                st.write(f"{m.get('recipient','')} | {m.get('template_name','') or m.get('message','')[:40]} | {m.get('status','')}")