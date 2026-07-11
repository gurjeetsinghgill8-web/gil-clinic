import streamlit as st
from utils.encryption import encrypt_text,decrypt_text
st.set_page_config('Encryption',layout='wide')
def show():
    st.title('Encryption Tool')
    st.caption('AES-256-GCM encryption for sensitive patient data')
    col1,col2=st.columns(2)
    with col1:
        st.subheader('Encrypt')
        plain=st.text_area('Plain text',key='enc_in')
        if st.button('Encrypt',type='primary') and plain:
            st.code(encrypt_text(plain))
    with col2:
        st.subheader('Decrypt')
        cipher=st.text_area('Cipher text',key='dec_in')
        if st.button('Decrypt',type='primary') and cipher:
            st.code(decrypt_text(cipher))
    st.info('PII fields (name, mobile, email, address, Aadhaar) are encrypted automatically in the database.')
