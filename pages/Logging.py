import streamlit as st
from utils.logging import get_logs
st.set_page_config('System Logs',layout='wide')
def show():
    st.title('System Logs')
    level=st.selectbox('Filter',['','info','warning','error','debug'])
    logs=get_logs(level)
    if not logs:
        st.info('No logs yet.')
    else:
        for l in logs[:50]:
            icon={'info':'ℹ️','warning':'⚠️','error':'❌','debug':'🔍'}.get(l.get('level',''),'ℹ️')
            with st.container(border=True):
                st.write(f'{icon} [{l.get("level","").upper()}] {l.get("module","")}: {l.get("message","")}')
                st.caption(l.get('created_at','')[:19])
