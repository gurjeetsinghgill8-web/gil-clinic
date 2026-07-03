"""
Password Management — Admin-only page for managing staff user accounts
======================================================================
Admin can:
  - View all users
  - Create new users (with custom username + password)
  - Reset passwords for existing users
  - Delete users (soft-deactivate)

Access: Admin role only
"""
import streamlit as st
from datetime import datetime

from utils.db import (
    create_user, get_all_users, get_user_by_username,
    update_user_password, delete_user, get_users_by_role
)


# ─── Main Page ────────────────────────────────────────────────────────────────

def show():
    st.title("🔐 Password Management")
    st.subheader("Admin — Manage Staff User Accounts")
    
    # Verify admin
    if st.session_state.auth_role != "Admin":
        st.error("⛔ Access denied. Admin only.")
        return
    
    # ─── Tabs for different operations ─────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs([
        "👥 All Users",
        "➕ Create User",
        "🔄 Reset Password",
        "❌ Delete User",
    ])
    
    # ─── Tab 1: All Users ──────────────────────────────────────────────────────
    with tab1:
        st.markdown("### 👥 All Staff Users")
        users = get_all_users()
        
        if not users:
            st.info("No users found. Create your first staff account below.")
        else:
            # Show as a table
            cols = st.columns([1, 2, 1.5, 1.5, 0.8])
            cols[0].markdown("**#**")
            cols[1].markdown("**Name**")
            cols[2].markdown("**Username**")
            cols[3].markdown("**Role**")
            cols[4].markdown("**Active**")
            st.divider()
            
            for i, u in enumerate(users, 1):
                cols = st.columns([1, 2, 1.5, 1.5, 0.8])
                cols[0].markdown(f"{i}")
                cols[1].markdown(f"{u.get('display_name', '—')}")
                cols[2].markdown(f"`{u['username']}`")
                cols[3].markdown(f"**{u['role']}**")
                active = u.get("active", 1)
                cols[4].markdown("✅" if active else "❌")
        
        st.divider()
        st.caption(f"Total: {len(users)} user(s)  |  Admin login: `.env` credentials")
    
    # ─── Tab 2: Create User ────────────────────────────────────────────────────
    with tab2:
        st.markdown("### ➔ Create New Staff User")
        st.markdown("**अपने हिसाब से username और password बनाएं** — आपको याद रहेगा और staff को भी आसानी होगी।")

        role_options = ["Reception", "ECG", "Echo", "TMT", "OPD", "Doctor", "Manager"]
        new_role = st.selectbox("Select Role", role_options, key="new_user_role")
        new_name = st.text_input(
            "Staff Member's Full Name",
            placeholder="e.g. Rajesh Kumar",
            key="new_user_name",
        )
        new_username = st.text_input(
            "👤 Choose Username",
            placeholder="e.g. rajesh, ecg_raj, reception1",
            key="new_username",
            help="Staff is username se login karega. Kuch simple rakhein."
        )
        new_password = st.text_input(
            "🔑 Choose Password",
            type="password",
            placeholder="e.g. rajesh123, ecg@2024",
            key="new_password",
            help="Simple rakhein jo staff ko yad rahe. Min 4 characters."
        )

        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Create User", type="primary", use_container_width=True):
                errors = []
                if not new_name or new_name.strip() == "":
                    errors.append("⚠️ Name daalna zaroori hai.")
                if not new_username or new_username.strip() == "":
                    errors.append("⚠️ Username daalna zaroori hai.")
                if not new_password or len(new_password.strip()) < 4:
                    errors.append("⚠️ Password kam se kam 4 characters ka daalein.")
                
                if errors:
                    for e in errors:
                        st.error(e)
                else:
                    # Check if username already exists
                    existing = get_user_by_username(new_username.strip().lower())
                    if existing:
                        st.error(f"❌ Username `{new_username.strip().lower()}` already exists! Koi aur username rakhein.")
                    else:
                        display_name = new_name.strip().title()
                        username = new_username.strip().lower()
                        password = new_password.strip()
                        
                        result = create_user(username, display_name, new_role, password)
                        if result:
                            st.success(f"✅ User created successfully!")
                            
                            # Show credentials in a highlighted box
                            st.markdown("""
                            <div style="
                                background: linear-gradient(135deg, #667eea, #764ba2);
                                color: white; padding: 20px; border-radius: 12px;
                                margin: 15px 0; text-align: center;
                            ">
                            """, unsafe_allow_html=True)
                            
                            st.markdown(f"### 🎉 New Staff Account")
                            st.markdown(f"**Name:** {display_name}")
                            st.markdown(f"**Role:** {new_role}")
                            st.markdown(f"**Username:** `{username}`")
                            st.markdown(f"**Password:** `{password}`")
                            
                            st.markdown("""
                            <p style="font-size: 0.85rem; opacity: 0.8; margin-top: 10px;">
                            ✅ Staff member ko ye username aur password dein. Woh <b>Staff</b> login mode me apna role select karke login karega.
                            </p>
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            st.error("❌ Failed to create user. Check database connection.")

        with col2:
            st.info("💡 **Tips:**\n\n- Username simple rakhein: `raj`, `sona`, `ecg1`\n- Password aisa rakhein jo staff ko yad rahe: `raj123`, `sona@2024`\n- Baad me bhi password reset kar sakte hain")
    
    # ─── Tab 3: Reset Password ─────────────────────────────────────────────────
    with tab3:
        st.markdown("### 🔄 Reset User Password")
        st.markdown("**नया password खुद लिखकर दें** — जो staff को आसानी से याद रह सके।")

        users = [u for u in get_all_users() if u.get("active", 1)]
        if not users:
            st.info("No active users to reset.")
        else:
            user_options = {f"{u['display_name']} ({u['role']}) — {u['username']}": u['username'] for u in users}
            selected_label = st.selectbox("Select User", list(user_options.keys()), key="reset_user")
            selected_username = user_options[selected_label]

            new_password_manual = st.text_input(
                "🔑 Enter New Password",
                type="password",
                placeholder="e.g. raj123, sona@2024",
                key="reset_new_pass",
                help="4+ characters. Simple rakhein jo staff ko yad rahe."
            )

            if st.button("🔄 Reset Password", type="primary", use_container_width=True):
                if not new_password_manual or len(new_password_manual.strip()) < 4:
                    st.error("⚠️ Password kam se kam 4 characters ka daalein.")
                else:
                    if update_user_password(selected_username, new_password_manual.strip()):
                        user_data = get_user_by_username(selected_username)

                        st.success(f"✅ Password reset successfully!")

                        st.markdown("""
                        <div style="
                            background: linear-gradient(135deg, #f093fb, #f5576c);
                            color: white; padding: 20px; border-radius: 12px;
                            margin: 15px 0; text-align: center;
                        ">
                        """, unsafe_allow_html=True)

                        st.markdown(f"### 🔄 Password Updated")
                        st.markdown(f"**User:** {user_data['display_name']} ({user_data['role']})")
                        st.markdown(f"**Username:** `{selected_username}`")
                        st.markdown(f"**New Password:** `{new_password_manual.strip()}`")

                        st.markdown("""
                        <p style="font-size: 0.85rem; opacity: 0.8; margin-top: 10px;">
                        ✅ Staff member ko naya password de dein.
                        </p>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.error("❌ Failed to reset password.")
    
    # ─── Tab 4: Delete User ────────────────────────────────────────────────────
    with tab4:
        st.markdown("### ❌ Deactivate User")
        st.warning("⚠️ This will **deactivate** the user account. They will no longer be able to log in.")
        st.caption("The account is not permanently deleted — it can be re-activated by the admin.")
        
        users = [u for u in get_all_users() if u.get("active", 1)]
        if not users:
            st.info("No active users to deactivate.")
        else:
            user_options = {f"{u['display_name']} ({u['role']}) — {u['username']}": u['username'] for u in users}
            selected_label = st.selectbox("Select User to Deactivate", list(user_options.keys()), key="delete_user")
            selected_username = user_options[selected_label]
            
            confirm = st.checkbox("✅ I confirm I want to deactivate this user", key="delete_confirm")
            
            if st.button("❌ Deactivate User", type="secondary", use_container_width=True, disabled=not confirm):
                if delete_user(selected_username):
                    st.success(f"✅ User `{selected_username}` has been deactivated.")
                    st.info("They can no longer log in. Contact admin to re-activate.")
                else:
                    st.error("❌ Failed to deactivate user.")
    
    # ─── Footer Info ───────────────────────────────────────────────────────────
    st.divider()
    st.markdown("### 🔑 Your Admin Access")
    st.markdown("""
    Your admin credentials are set in the `.env` file (`ADMIN_USERNAME` / `ADMIN_PASS`).
    
    **Security Notes:**
    - Staff members see ONLY their own dashboard
    - Passwords are stored in the local database (`cardioqueue.db`)
    - The password is shown only ONCE when created or reset
    - Always share passwords securely with staff members
    """)
