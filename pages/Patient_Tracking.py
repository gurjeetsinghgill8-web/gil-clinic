"""
Patient Tracking — Department Flow Monitor
"""
import streamlit as st
from llm_harness import get_harness

try:
    st.set_page_config("Patient Tracking", layout="wide")
except Exception:
    pass

def show():
    st.title("Patient Tracking")
    st.caption("Live view of patient flow across departments")
    
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=10000, key="tracking_refresh")
    except: pass
    
    harness = get_harness()
    queue = harness.get_reception_queue()
    
    if not queue:
        st.info("No patients in queue")
        return
    
    dept_order = ["Reception", "ECG", "Echo", "TMT", "OPD", "Doctor", "Pharmacy", "Billing"]
    
    for test in queue[:20]:
        p = test.get("patients", {})
        name = p.get("name", "?")
        test_name = test.get("test_name", "")
        status = test.get("status", "registered")
        
        cols = st.columns(len(dept_order) + 1)
        cols[0].write(f"**{name}**")
        
        current_dept_idx = -1
        for i, dept in enumerate(dept_order):
            if dept.lower() in test_name.lower() or (dept == "Reception" and status == "registered"):
                current_dept_idx = i
                break
        
        for i, dept in enumerate(dept_order):
            if i < current_dept_idx:
                cols[i+1].markdown("✅")
            elif i == current_dept_idx:
                cols[i+1].markdown("🟠")
            else:
                cols[i+1].markdown("⏺")
        
        status_icons = {"registered": "📝", "waiting": "⏳", "called": "🔔", "in_progress": "🟠", "completed": "✅", "report_ready": "📄"}
        st.caption(f"Status: {status_icons.get(status, '❓')} {status}")
        st.divider()
