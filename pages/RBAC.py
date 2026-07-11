"""
RBAC Management Page — Role Permission Matrix
===============================================
"""
import streamlit as st
from utils.rbac import (get_all_roles, get_role_permissions, check_permission,
                        ROLES, RESOURCES, PERMISSIONS)

st.set_page_config("RBAC Manager", layout="wide")


def show():
    st.title("🔐 Role-Based Access Control")

    tab1, tab2 = st.tabs(["📋 Permission Matrix", "🔍 Check Permission"])

    with tab1:
        st.subheader("Role Permission Matrix")
        st.caption("System-defined roles with resource-level permissions")

        roles = get_all_roles()
        if not roles:
            st.info("No roles defined yet.")
        else:
            for role in roles:
                name = role.get("role_name", "")
                hierarchy = {r: i for i, r in enumerate(ROLES)}.get(name, 99)
                perms = role.get("permission_matrix", {})
                with st.expander(f"{'👑' if hierarchy<3 else '👤'} {name.title()} (Level {hierarchy})"):
                    for resource in RESOURCES:
                        rperms = perms.get(resource, [])
                        if rperms:
                            st.markdown(f"**{resource.title()}**: {' · '.join([f'✅ {p}' for p in rperms])}")
                        else:
                            st.markdown(f"**{resource.title()}**: ❌ No access")

    with tab2:
        st.subheader("Check Permission")
        role = st.selectbox("Role", ROLES)
        resource = st.selectbox("Resource", RESOURCES)
        permission = st.selectbox("Permission", PERMISSIONS)
        if st.button("🔍 Check"):
            result = check_permission(role, resource, permission)
            if result:
                st.success(f"✅ {role} CAN {permission} on {resource}")
            else:
                st.error(f"❌ {role} CANNOT {permission} on {resource}")
