"""
Backup & Recovery Page
========================
"""
import streamlit as st
from utils.backup import create_backup, get_backup_history, get_backup_stats

try:
    st.set_page_config("Backup", layout="wide")
except Exception:
    pass


def show():
    st.title("💾 Backup & Recovery")

    tab1, tab2 = st.tabs(["🆕 Create Backup", "📋 Backup History"])

    with tab1:
        st.subheader("Create Database Backup")
        st.info("Creates a complete snapshot of the SQLite database.")

        stats = get_backup_stats()
        if stats:
            c1, c2, c3 = st.columns(3)
            c1.metric("📦 Total Backups", stats.get("total", 0))
            c2.metric("✅ Successful", stats.get("successful", 0))
            c3.metric("💾 Total Size", f"{stats.get('total_size_mb',0):.2f} MB")
            if stats.get("last_backup"):
                st.caption(f"Last backup: {stats['last_backup'][:19]}")

        if st.button("💾 Create Backup Now", type="primary"):
            with st.spinner("Creating backup..."):
                r = create_backup("manual")
                if r.get("success"):
                    st.success(f"✅ Backup created: {r.get('file','')} ({r.get('size_kb',0)} KB)")
                else:
                    st.error(r.get("message", "Backup failed"))

    with tab2:
        st.subheader("Backup History")
        history = get_backup_history()
        if not history:
            st.info("No backups created yet.")
        else:
            for h in history:
                with st.container(border=True):
                    cols = st.columns([2, 1, 1.5, 1, 1])
                    cols[0].write(f"**{h.get('backup_type','').upper()}**")
                    cols[1].write(f"{'✅' if h.get('status')=='completed' else '❌'} {h.get('status','')}")
                    size = h.get("size_bytes", 0)
                    cols[2].write(f"{size//1024} KB" if size else "-")
                    cols[3].write(h.get("file_path","").split("/")[-1] if h.get("file_path") else "-")
                    cols[4].write(h.get("created_at","")[:16] if h.get("created_at") else "")
