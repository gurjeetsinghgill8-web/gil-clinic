import streamlit as st
from utils.sms_upgrade import create_template,get_templates,send_sms_v2,get_sms_log_v2
st.set_page_config('SMS Manager',layout='wide')
def show():
    st.title('SMS Manager')
    t1,t2,t3=st.tabs(['Send SMS','Templates','Delivery Log'])
    with t1:
        r=st.text_input('Phone*'); m=st.text_area('Message*')
        t=st.selectbox('Template',['']+[x.get('name','') for x in get_templates()])
        if st.button('Send',type='primary') and r and m:
            res=send_sms_v2(r,m,t)
            st.success('Sent') if res.get('success') else st.error(res.get('message'))
    with t2:
        n=st.text_input('Template Name*'); b=st.text_area('Body*')
        l=st.selectbox('Language',['en','hi','gu'])
        if st.button('Create',type='primary') and n and b:
            res=create_template(n,b,l)
            st.success(res['message']); st.rerun()
        for x in get_templates():
            with st.expander(x.get('name','')):
                st.code(x.get('body',''))
    with t3:
        for e in get_sms_log_v2()[:30]:
            with st.container(border=True):
                st.write(f'{e.get("recipient","")} - {e.get("message","")[:40]} - {e.get("status","")}')
