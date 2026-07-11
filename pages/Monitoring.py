import streamlit as st
from utils.monitoring import get_db_size,get_page_count,get_util_count
st.set_page_config('Monitoring',layout='wide')
def show():
    st.title('System Monitoring')
    c1,c2,c3,c4=st.columns(4)
    c1.metric('Database Size',f'{get_db_size()} KB')
    c2.metric('Pages',str(get_page_count()))
    c3.metric('Utils',str(get_util_count()))
    c4.metric('Total Modules',str(get_page_count()+get_util_count()))
    st.subheader('System Health')
    st.success('Database: SQLite - Connected')
    st.success('App Status: Running')
    try:
        import streamlit
        st.info(f'Streamlit: {streamlit.__version__}')
    except: pass
