"""
CardioQueue — Main Entry Point
================================
Multi-page Streamlit application for Cardiology Department workflow.

Architecture: UI (this file) → llm_harness.py (Orchestrator) → db.py (Database)
The UI NEVER talks to the database directly — all actions go through the Harness.
"""
import streamlit as st

# Must be the first Streamlit command
st.set_page_config(
    page_title="CardioQueue — GIL CLINIC",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

from llm_harness import get_harness
from utils.config import APP_NAME, HOSPITAL_NAME, ADMIN_USERNAME, ADMIN_PASS
from utils.db import authenticate_user, get_all_users, get_users_by_role
from utils.notifications import request_notification_permission_script


# ═══════════════════════════════════════════════════════════════════════════════
#  LOAD CUSTOM CSS
# ═══════════════════════════════════════════════════════════════════════════════

def load_css():
    """Load custom CSS from assets/style.css."""
    try:
        with open("assets/style.css") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass  # CSS is optional


load_css()


# ═══════════════════════════════════════════════════════════════════════════════
#  SESSION STATE INIT
# ═══════════════════════════════════════════════════════════════════════════════

def init_session():
    """Initialize all session state variables."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "auth_role" not in st.session_state:
        st.session_state.auth_role = None
    if "page" not in st.session_state:
        st.session_state.page = "🏠 Home"
    if "notification_permission_requested" not in st.session_state:
        st.session_state.notification_permission_requested = False


# ═══════════════════════════════════════════════════════════════════════════════
#  AUTHENTICATION
# ═══════════════════════════════════════════════════════════════════════════════

ROLE_PAGES = {
    "Reception": "📋 Reception",
    "ECG":  "📊 ECG",
    "Echo": "📊 Echo",
    "TMT":  "📊 TMT",
    "OPD":  "🩺 OPD",
    "Doctor": "🩺 Doctor",
    "Manager": "📈 Manager Dashboard",
    "Admin": "👑 Admin Panel",
}

ADMIN_EXTRA_PAGES = {
    "🔐 Password Management": "🔐 Password Management",
}

DEPARTMENT_PAGES = {
    "ECG": "📊 ECG",
    "Echo": "📊 Echo",
    "TMT": "📊 TMT",
    "OPD": "🩺 OPD",
}

PUBLIC_PAGES = ["📋 Patient Status"]

ALL_PAGES = list(ROLE_PAGES.values()) + PUBLIC_PAGES + ["🏠 Home"]


def render_sidebar_footer():
    """Render database mode status and downloadable operations manual in the sidebar."""
    from utils.db import USE_SUPABASE
    with st.sidebar:
        st.divider()
        if USE_SUPABASE:
            st.success("☁️ Supabase Cloud Active")
        else:
            st.warning("💾 Local SQLite Mode Active")
            st.caption("Using `cardioqueue.db` locally.")

        try:
            with open("USER_MANUAL.md", "r", encoding="utf-8") as f:
                manual_text = f.read()
            st.download_button(
                label="📖 Download User Manual",
                data=manual_text,
                file_name="CardioQueue_User_Manual.md",
                mime="text/markdown",
                use_container_width=True,
            )
        except Exception:
            pass

        st.caption("v1.1 • Built with ❤️ using Harness Engineering")


def login_sidebar():
    """Render the login sidebar. Two modes: Staff login (username+pass) and Admin login."""
    with st.sidebar:
        st.image("https://img.icons8.com/color/96/hospital.png", width=80)
        st.markdown(f"### 🏥 {APP_NAME}")
        st.caption(f"{HOSPITAL_NAME} — Cardiology Department")

        st.divider()

        # ─── Tab-style: Staff Login vs Admin Login ─────────────────────────────
        login_mode = st.radio(
            "Login as:",
            ["👥 Staff", "🔑 Admin", "👤 Patient (No Login)"],
            key="login_mode",
            horizontal=True,
            label_visibility="collapsed",
        )

        if login_mode == "👤 Patient (No Login)":
            if st.button("🔓 Access Patient Status", use_container_width=True, type="primary"):
                st.session_state.authenticated = True
                st.session_state.auth_role = "Patient"
                st.session_state.auth_username = "Patient"
                st.rerun()
            st.caption("No password needed to check your status.")
            render_sidebar_footer()
            return False

        # ─── Staff Login ───────────────────────────────────────────────────────
        if login_mode == "👥 Staff":
            staff_roles = ["Reception", "ECG", "Echo", "TMT", "OPD", "Doctor", "Manager"]
            selected_role = st.selectbox(
                "Select your role",
                staff_roles,
                key="login_staff_role",
            )

            # Get all active users for this role
            role_users = get_users_by_role(selected_role)
            if not role_users:
                st.info(f"⚠️ No {selected_role} users found.\nContact Admin to create your account.")
                render_sidebar_footer()
                return False

            usernames = {u["display_name"]: u["username"] for u in role_users}
            selected_display = st.selectbox(
                "Select your name",
                list(usernames.keys()),
                key="login_staff_name",
            )

            password = st.text_input("Password", type="password", key="login_staff_pass")

            if st.button("🔐 Login", use_container_width=True, type="primary"):
                username = usernames[selected_display]
                user = authenticate_user(username, password)
                if user:
                    st.session_state.authenticated = True
                    st.session_state.auth_role = user["role"]
                    st.session_state.auth_username = user["display_name"]
                    st.rerun()
                else:
                    st.error("❌ Incorrect password. Please try again.")
                    return False

        # ─── Admin Login ───────────────────────────────────────────────────────
        if login_mode == "🔑 Admin":
            admin_user = st.text_input("Admin Username", key="admin_user")
            admin_pass = st.text_input("Admin Password", type="password", key="admin_pass")

            if st.button("🔐 Admin Login", use_container_width=True, type="primary"):
                if admin_user == ADMIN_USERNAME and admin_pass == ADMIN_PASS:
                    st.session_state.authenticated = True
                    st.session_state.auth_role = "Admin"
                    st.session_state.auth_username = "Admin (Owner)"
                    st.rerun()
                else:
                    st.error("❌ Invalid admin credentials.")
                    return False

        render_sidebar_footer()

    return st.session_state.authenticated


def logout_button():
    """Show logout button in sidebar for authenticated users."""
    with st.sidebar:
        st.divider()
        role = st.session_state.auth_role
        username = st.session_state.get("auth_username", role)
        st.caption(f"👤 **{username}**  \n_{role}_")
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.auth_role = None
            st.session_state.auth_username = None
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE NAVIGATOR
# ═══════════════════════════════════════════════════════════════════════════════

def page_selector():
    """Determine which page to show based on auth role and user navigation."""
    role = st.session_state.auth_role

    # Build navigation options
    nav_options = ["🏠 Home"]

    if role == "Admin":
        # Admin sees ALL pages + password management
        nav_options.extend(list(ROLE_PAGES.values()))
        nav_options.append("📋 Patient Status")
        nav_options.append("🔐 Password Management")
    elif role in ROLE_PAGES:
        nav_options.append(ROLE_PAGES[role])

    # Doctor can also see status
    if role == "Doctor":
        nav_options.append("📋 Patient Status")

    # Patient role only sees status
    if role == "Patient":
        nav_options = ["📋 Patient Status"]

    # Always show patient status as public option in sidebar
    with st.sidebar:
        st.divider()
        selected = st.radio("Navigate to:", nav_options, key="nav")
        return selected

    return nav_options[0]


# ═══════════════════════════════════════════════════════════════════════════════
#  HOME PAGE
# ═══════════════════════════════════════════════════════════════════════════════

def show_home():
    """Render the home/dashboard page."""
    st.title(f"🏥 {APP_NAME}")
    st.subheader(f"{HOSPITAL_NAME} — Cardiology Department")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("""
        ### 👋 Welcome to CardioQueue

        A lightweight patient flow management system for cardiology departments.

        **Modules:**
        - 📋 **Reception** — Register patients, print tokens, view status
        - 📊 **ECG / Echo / TMT** — Technician dashboards with live queues
        - 🩺 **Doctor** — Manage reports and delivery
        - 🔍 **Patient Status** — Self-service check for patients

        **Key Features:**
        - ✅ Real-time queue management
        - ✅ Browser notifications on mobile
        - ✅ Token printing
        - ✅ Zero monthly cost
        - ✅ Live PWA status tracking
        """)

    with col2:
        st.markdown("### 📊 Today's Stats")
        try:
            harness = get_harness()
            stats = harness.get_all_dashboard_stats()
            for dept, s in stats.items():
                waiting = s.get("waiting", 0)
                completed = s.get("completed", 0)
                st.metric(f"{dept}", f"{waiting} waiting", f"{completed} done")
        except Exception:
            st.info("Awaiting data...")


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN ROUTER
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Main application entry point."""
    init_session()

    # ─── Detect ?patient=XXX from URL for QR-based auto-load ─────────────
    query_params = st.query_params
    patient_qr = query_params.get("patient", None)
    if isinstance(patient_qr, list):
        patient_qr = patient_qr[0] if patient_qr else None

    # Request notification permission on first load (Phase 1)
    if not st.session_state.notification_permission_requested:
        st.markdown(request_notification_permission_script(), unsafe_allow_html=True)
        st.session_state.notification_permission_requested = True

    # ─── QR auto-load: bypass login, go straight to Patient Status ───────
    if patient_qr:
        from pages.Patient_Status import show
        show()
        return

    # ─── Login Flow ──────────────────────────────────────────────────────────
    if not st.session_state.authenticated:
        login_sidebar()
        show_home()
        return

    # ─── Authenticated Flow ──────────────────────────────────────────────────
    logout_button()
    role = st.session_state.auth_role
    page = page_selector()
    render_sidebar_footer()

    # Route to the correct page based on selection
    if page == "🏠 Home":
        show_home()

    elif page == "📋 Reception":
        from pages.Reception import show
        show()

    elif page == "📊 ECG":
        from pages.ECG import show
        show()

    elif page == "📊 Echo":
        from pages.Echo import show
        show()

    elif page == "📊 TMT":
        from pages.TMT import show
        show()

    elif page == "🩺 OPD":
        from pages.OPD import show
        show()

    elif page == "📈 Manager Dashboard":
        from pages.Manager import show
        show()

    elif page == "🩺 Doctor":
        from pages.Doctor import show
        show()

    elif page == "📋 Patient Status":
        from pages.Patient_Status import show
        show()

    elif page == "👑 Admin Panel":
        st.info("👑 Admin Panel — You have full access to all pages via the sidebar navigation.")
        st.markdown("Use the sidebar to navigate to any department, or go to **🔐 Password Management** to manage staff accounts.")

    elif page == "🔐 Password Management":
        from pages.Password_Management import show
        show()


if __name__ == "__main__":
    main()
