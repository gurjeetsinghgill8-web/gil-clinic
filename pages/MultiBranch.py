import streamlit as st
from utils.multi_branch import add_branch,get_branches
st.set_page_config('Multi-Branch',layout='wide')
def show():
    st.title('Branch Management')
    t1,t2=st.tabs(['Branches','Add Branch'])
    with t1:
        for b in get_branches():
            with st.container(border=True):
                st.write(f'**{b.get("name","")}** ({b.get("code","")})')
                st.caption(f'{b.get("address","")} | {b.get("phone","")} | {b.get("email","")}')
    with t2:
        n=st.text_input('Branch Name*'); c=st.text_input('Branch Code*')
        a=st.text_area('Address'); p=st.text_input('Phone'); e=st.text_input('Email')
        if st.button('Add Branch',type='primary') and n and c:
            r=add_branch(n,c,a,p,e)
            st.success(r['message']); st.rerun()
