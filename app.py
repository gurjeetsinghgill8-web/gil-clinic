"""
CardioQueue — Main Entry Point
================================
Multi-page Streamlit application for Cardiology Department workflow.
Modern UI with beautiful login, single-click staff selection, and PIN entry.

Architecture: UI (this file) → llm_harness.py (Orchestrator) → db.py (Database)
The UI NEVER talks to the database directly — all actions go through the Harness.
"""
import streamlit as st

# Must be the first Streamlit command
st.set_page_config(
    page_title=f"CardioQueue — {__import__('utils.config', fromlist=['HOSPITAL_NAME']).HOSPITAL_NAME}",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

from llm_harness import get_harness
from utils.config import APP_NAME, HOSPITAL_NAME, CLINIC_SPECIALTY, CLINIC_LOGO, ADMIN_USERNAME, ADMIN_PASS
from utils.db import get_all_active_users, verify_login
from utils.notifications import request_notification_permission_script

from datetime import datetime

# ─── Inactivity Timeout ──────────────────────────────────────────────────────
INACTIVITY_TIMEOUT_MINUTES = 30  # Auto-logout after this many idle minutes


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
    if "auth_username" not in st.session_state:
        st.session_state.auth_username = None
    if "page" not in st.session_state:
        st.session_state.page = "🏠 Home"
    if "notification_permission_requested" not in st.session_state:
        st.session_state.notification_permission_requested = False
    if "login_step" not in st.session_state:
        st.session_state.login_step = "select"  # "select" | "pin" | "admin"
    if "selected_user" not in st.session_state:
        st.session_state.selected_user = None
    if "show_admin_login" not in st.session_state:
        st.session_state.show_admin_login = False
    if "last_activity" not in st.session_state:
        st.session_state.last_activity = None


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

ROLE_PAGES = {
    "Reception": "📋 Reception",
    "ECG":  "📊 ECG",
    "Echo": "📊 Echo",
    "TMT":  "📊 TMT",
    "OPD":  "🩺 OPD",
    "Doctor": "🩺 Doctor",
    "Nurse": "👩‍⚕️ Nurse Station",
    "Manager": "📈 Manager Dashboard",
    "Admin": "👑 Admin Panel",
    "Pharmacist": "💊 Pharmacist",
}

DEPARTMENT_PAGES = {
    "ECG": "📊 ECG",
    "Echo": "📊 Echo",
    "TMT": "📊 TMT",
    "OPD": "🩺 OPD",
    "X-Ray": "🩻 X-Ray",
    "Ultrasound": "📡 Ultrasound",
    "Lab": "🧪 Lab",
    "Pharmacy": "💊 Pharmacy",
}

PUBLIC_PAGES = ["📋 Patient Status"]

STAFF_PAGES = ["📋 Patient History", "📄 Daily List", "📅 Appointments", "💳 Billing"]  # Shared by Reception, Manager, Admin

MANAGER_PAGES = ["📋 Activity Log", "📊 Reports & Analytics", "⭐ Feedback"]  # Manager + Admin only

ALL_PAGES = list(ROLE_PAGES.values()) + PUBLIC_PAGES + STAFF_PAGES + MANAGER_PAGES + ["🏠 Home"]

# Role-to-emoji mapping for staff cards
ROLE_EMOJIS = {
    "Reception": "📋",
    "ECG": "🩺",
    "Echo": "🔬",
    "TMT": "🏃",
    "OPD": "🩺",
    "X-Ray": "🩻",
    "Ultrasound": "📡",
    "Lab": "🧪",
    "Pharmacy": "💊",
    "Doctor": "👨‍⚕️",
    "Nurse": "👩‍⚕️",
    "Manager": "📈",
    "Admin": "👑",
}


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

        st.caption("v2.2 • Local-First UI • Built with ❤️")


# ═══════════════════════════════════════════════════════════════════════════════
#  NEW BEAUTIFUL LOGIN PAGE
# ═══════════════════════════════════════════════════════════════════════════════

def render_login_page():
    """
    Modern full-page login with staff card grid.
    Step 1: Select staff member from beautiful card grid
    Step 2: Enter PIN (4-6 digits)
    Also has: Patient access button + Admin login link
    """
    # ─── Center the login card using columns ───────────────────────────────
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        # ─── Login Card ────────────────────────────────────────────────────
        st.markdown(f"""
        <div class="login-card">
            <div class="login-header">
                <div class="hospital-icon">{CLINIC_LOGO}</div>
                <h1>CardioQueue</h1>
                <p>{HOSPITAL_NAME} — {CLINIC_SPECIALTY} Department</p>
                <div style="margin: 6px 0;"><span style="background-color:#00b894;color:white;padding:3px 8px;border-radius:10px;font-size:0.75rem;font-weight:bold;box-shadow:0 2px 6px rgba(0,184,148,0.25);">🚀 Upgrade v2.2 (Local-First)</span></div>
                <p style="font-size:0.8rem;color:#b2bec3;margin-top:4px;">Staff Login</p>
            </div>
        """, unsafe_allow_html=True)

        # ─── Admin Login Mode (toggled via link) ─────────────────────────────
        if st.session_state.get("show_admin_login", False):
            st.markdown("### 🔑 Admin Login")
            admin_user = st.text_input("Admin Username", key="admin_user_top")
            admin_pass = st.text_input("Admin Password", type="password", key="admin_pass_top")

            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("🔐 Login", type="primary", use_container_width=True):
                    if admin_user == ADMIN_USERNAME and admin_pass == ADMIN_PASS:
                        st.session_state.authenticated = True
                        st.session_state.auth_role = "Admin"
                        st.session_state.auth_username = "Admin (Owner)"
                        st.session_state.show_admin_login = False
                        st.rerun()
                    else:
                        st.error("❌ Invalid admin credentials.")

            with col_b:
                if st.button("← Back", use_container_width=True):
                    st.session_state.show_admin_login = False
                    st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)
            return

        # ─── Step 1: Staff Selection ───────────────────────────────────────
        if st.session_state.login_step == "select":
            st.markdown("### 👤 अपना नाम चुनें / Select Your Name")
            st.caption("Login karne ke liye apna naam click karein")

            # Get all active staff users grouped by role
            all_users = get_all_active_users()
            if not all_users:
                st.warning("⚠️ No staff accounts found. Contact Admin to create accounts.")
                st.info("💡 Admin login: नीचे Admin link पर click karein.")

                # Patient button when no staff
                if st.button("🔓 Access Patient Status", use_container_width=True, type="primary"):
                    st.session_state.authenticated = True
                    st.session_state.auth_role = "Patient"
                    st.session_state.auth_username = "Patient"
                    st.rerun()

                # Admin link
                st.markdown("""
                <div class="admin-login-link">
                    <button onclick="document.querySelector('button:has(span:text(\"🔑\"))').click()">🔑 Admin Login</button>
                </div>
                """, unsafe_allow_html=True)
                if st.button("🔑 Admin Login", key="admin_link_empty"):
                    st.session_state.show_admin_login = True
                    st.rerun()

                st.markdown("</div>", unsafe_allow_html=True)
                return

            # Group users by role for organized display
            from itertools import groupby
            all_users_sorted = sorted(all_users, key=lambda u: u["role"])
            for role, group in groupby(all_users_sorted, key=lambda u: u["role"]):
                users_list = list(group)
                emoji = ROLE_EMOJIS.get(role, "👤")
                st.markdown(f"**{emoji} {role}**")

                # Display users in rows of 4 columns
                for row_start in range(0, len(users_list), 4):
                    row_users = users_list[row_start:row_start + 4]
                    cols = st.columns(4)
                    for col_idx, user in enumerate(row_users):
                        with cols[col_idx]:
                            display_name = user.get("display_name", user["username"])
                            avatar_letter = display_name[0].upper() if display_name else "👤"
                            btn_key = f"staff_{user['username']}_{row_start}"

                            if st.button(
                                f"{avatar_letter}\n\n{display_name}\n\n{role}",
                                key=btn_key,
                                use_container_width=True,
                            ):
                                st.session_state.selected_user = user
                                st.session_state.login_step = "pin"
                                st.rerun()

            # ─── Patient Entry ──────────────────────────────────────────────
            st.markdown("---")
            patient_col1, patient_col2 = st.columns([1, 1])
            with patient_col1:
                if st.button("🔓 Patient (No Login)", use_container_width=True):
                    st.session_state.authenticated = True
                    st.session_state.auth_role = "Patient"
                    st.session_state.auth_username = "Patient"
                    st.rerun()
            with patient_col2:
                if st.button("🔑 Admin Login", key="admin_link_main", use_container_width=True):
                    st.session_state.show_admin_login = True
                    st.rerun()

        # ─── Step 2: PIN Entry ──────────────────────────────────────────────
        elif st.session_state.login_step == "pin":
            user = st.session_state.selected_user
            if not user:
                st.session_state.login_step = "select"
                st.rerun()
                return

            display_name = user.get("display_name", "User")
            username = user["username"]
            role = user["role"]
            emoji = ROLE_EMOJIS.get(role, "👤")

            # Show who is logging in
            st.markdown(f"""
            <div style="text-align:center;padding:1rem;background:rgba(102,126,234,0.06);
                        border-radius:12px;margin-bottom:1rem;">
                <div style="font-size:2.5rem;">{emoji}</div>
                <div style="font-weight:700;font-size:1.2rem;">{display_name}</div>
                <div style="color:#636e72;font-size:0.9rem;">{role}</div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("### 🔑 Enter Your PIN")
            st.caption("अपना 4-6 अंकों का PIN डालें")

            pin = st.text_input(
                "PIN",
                type="password",
                placeholder="••••",
                max_chars=6,
                key="staff_pin",
                label_visibility="collapsed",
            )

            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("🔐 Login", type="primary", use_container_width=True):
                    if not pin:
                        st.error("⚠️ Please enter your PIN.")
                    elif len(pin) < 4:
                        st.error("⚠️ PIN kam se kam 4 digits ka hona chahiye.")
                    else:
                        user_data = verify_login(username, pin)
                        if user_data:
                            st.session_state.authenticated = True
                            st.session_state.auth_role = user_data["role"]
                            st.session_state.auth_username = user_data["display_name"]
                            st.session_state.login_step = "select"
                            st.session_state.selected_user = None
                            st.rerun()
                        else:
                            st.error("❌ गलत PIN / Wrong PIN. Please try again.")

            with col_b:
                if st.button("← Change Staff", use_container_width=True):
                    st.session_state.login_step = "select"
                    st.session_state.selected_user = None
                    st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR USER INFO & LOGOUT
# ═══════════════════════════════════════════════════════════════════════════════

def logout_button():
    """Show logout button in sidebar for authenticated users."""
    with st.sidebar:
        st.divider()
        role = st.session_state.auth_role
        username = st.session_state.get("auth_username", role)
        emoji = ROLE_EMOJIS.get(role, "👤")

        st.markdown(f"""
        <div style="padding:0.5rem;background:rgba(255,255,255,0.05);border-radius:10px;
                    text-align:center;">
            <div style="font-size:2rem;">{emoji}</div>
            <div style="font-weight:600;color:white;">{username}</div>
            <div style="color:#b2bec3;font-size:0.8rem;">{role}</div>
        </div>
        """, unsafe_allow_html=True)

        # Show inactivity timer
        if st.session_state.last_activity:
            elapsed = datetime.now() - st.session_state.last_activity
            remaining = INACTIVITY_TIMEOUT_MINUTES * 60 - int(elapsed.total_seconds())
            if remaining > 0:
                mins, secs = divmod(remaining, 60)
                st.caption(f"⏱️ Auto-logout in {mins}m {secs}s")
            else:
                st.caption("⏱️ Session expired — logging out...")

        if st.button("🚪 Logout", use_container_width=True):
            _clear_session()
            st.rerun()


def _check_inactivity_logout():
    """
    Check if the session has been idle too long.
    If so, clear session and show a toast. Called from main().
    """
    if not st.session_state.authenticated:
        return

    now = datetime.now()
    last = st.session_state.last_activity

    if last is None:
        # First activity timestamp
        st.session_state.last_activity = now
        return

    elapsed = (now - last).total_seconds()
    if elapsed > INACTIVITY_TIMEOUT_MINUTES * 60:
        _clear_session()
        st.info("⏱️ Session auto-expired due to inactivity. Please log in again.")
        st.rerun()

    # Update timestamp on every page load
    st.session_state.last_activity = now


def _clear_session():
    """Clear auth-related session state (logout)."""
    st.session_state.authenticated = False
    st.session_state.auth_role = None
    st.session_state.auth_username = None
    st.session_state.login_step = "select"
    st.session_state.selected_user = None
    st.session_state.show_admin_login = False
    st.session_state.last_activity = None


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE NAVIGATOR
# ═══════════════════════════════════════════════════════════════════════════════

def page_selector():
    """Determine which page to show based on auth role and user navigation."""
    role = st.session_state.auth_role

    # Build navigation options
    # Build navigation options
    nav_options = ["🏠 Home"]

    if role == "Admin":
        nav_options.extend(list(ROLE_PAGES.values()))
        nav_options.append("📋 Patient Status")
        nav_options.append("📋 Patient History")
        nav_options.append("📋 Activity Log")
        nav_options.append("📅 Appointments")
        nav_options.append("💳 Billing")
        nav_options.append("⭐ Feedback")
        nav_options.append("🚑 Emergency")
        nav_options.append("🏥 IPD Ward")
        nav_options.append("📦 Inventory")
        nav_options.append("🧪 Lab")
        nav_options.append("💊 Pharmacy")
        nav_options.append("📅 Follow-up")
        nav_options.append("🔐 Password Management")
        nav_options.append("📋 Purchase Orders")
        nav_options.append("🏢 Vendors")
        nav_options.append("👥 HR")
        nav_options.append("💰 Payroll")
        nav_options.append("📊 Finance")
        nav_options.append("🤖 AI Triage")
        nav_options.append("🤖 AI Follow-up")
        nav_options.append("📱 WhatsApp Business")
        nav_options.append("📧 Email")
        nav_options.append("📱 SMS Manager")
        nav_options.append("🤖 AI Receptionist")
        nav_options.append("📧 Email")
        nav_options.append("📱 Push Notifications")
        nav_options.append("📱 SMS Manager")
        nav_options.append("📱 WhatsApp Business")
        nav_options.append("📊 System Monitoring")
        nav_options.append("📋 System Logs")
        nav_options.append("💾 Backup")
        nav_options.append("📋 Compliance")
        nav_options.append("🏢 Multi-Branch")
        nav_options.append("👑 Owner Dashboard")
        nav_options.append("🏥 Patient Portal")
        nav_options.append("🧪 Lab Technician")
        nav_options.append("💰 Accountant")
        nav_options.append("🧾 GST")
        nav_options.append("🥗 AI Dietician")
        nav_options.append("📄 AI Report Explainer")
        nav_options.append("📧 Email")
        nav_options.append("🔔 Push Notifications")
        nav_options.append("📞 Voice Calls")
        nav_options.append("🎥 Telemedicine")
        nav_options.append("💊 AI Prescription")
        nav_options.append("🎙️ AI Voice Agent")
        nav_options.append("💾 Backup")
        nav_options.append("🔐 RBAC")
        nav_options.append("📋 Compliance")
        nav_options.append("📱 SMS Manager")
        nav_options.append("📱 WhatsApp Business")
        nav_options.append("🔒 Encryption")
        nav_options.append("📊 System Monitoring")
        nav_options.append("📋 System Logs")
        nav_options.append("💊 Pharmacist")
        nav_options.append("🕐 Patient Timeline")
        nav_options.append("📍 Patient Tracking")
    elif role in ROLE_PAGES:
        nav_options.append(ROLE_PAGES[role])

    # Doctor can also see status + IPD
    if role == "Doctor":
        nav_options.append("📋 Patient Status")
        nav_options.append("🚑 Emergency")
        nav_options.append("🏥 IPD Ward")
        nav_options.append("📦 Inventory")
        nav_options.append("📅 Follow-up")
        nav_options.append("🤖 AI Triage")
        nav_options.append("🤖 AI Follow-up")
        nav_options.append("📱 WhatsApp Business")
        nav_options.append("📧 Email")
        nav_options.append("📱 SMS Manager")

    # Reception and Manager get additional staff pages
    if role in ("Reception", "Manager"):
        nav_options.append("📋 Patient History")
        nav_options.append("📄 Daily List")
        nav_options.append("📅 Appointments")
        nav_options.append("💳 Billing")

    # Manager gets Activity Log + Feedback + IPD + Inventory
    if role == "Manager":
        nav_options.append("📋 Activity Log")
        nav_options.append("⭐ Feedback")
        nav_options.append("🚑 Emergency")
        nav_options.append("🏥 IPD Ward")
        nav_options.append("📦 Inventory")
        nav_options.append("🧪 Lab")
        nav_options.append("💊 Pharmacy")
        nav_options.append("📅 Follow-up")
        nav_options.append("📋 Purchase Orders")
        nav_options.append("🏢 Vendors")
        nav_options.append("👥 HR")
        nav_options.append("💰 Payroll")
        nav_options.append("📊 Finance")
        nav_options.append("🤖 AI Receptionist")
        nav_options.append("📧 Email")
        nav_options.append("📱 Push Notifications")
        nav_options.append("📱 SMS Manager")
        nav_options.append("📱 WhatsApp Business")
        nav_options.append("📊 System Monitoring")
        nav_options.append("📋 System Logs")
        nav_options.append("💾 Backup")
        nav_options.append("📋 Compliance")
        nav_options.append("💊 Pharmacist")
        nav_options.append("🕐 Patient Timeline")
        nav_options.append("📍 Patient Tracking")
        nav_options.append("🏢 Multi-Branch")

        # Patient role only sees status
    if role == "Patient":
        nav_options = ["📋 Patient Status"]

    # Show navigation in sidebar
    with st.sidebar:
        st.markdown(f"## {CLINIC_LOGO} {HOSPITAL_NAME}")
        st.markdown(
            '<div style="margin-bottom: 0.5rem;"><span style="background-color:#00b894;color:white;padding:2px 8px;border-radius:10px;font-size:0.75rem;font-weight:bold;">🚀 Upgrade v2.0</span></div>',
            unsafe_allow_html=True
        )
        st.divider()
        st.markdown("### 📍 Navigation")
        selected = st.radio("Go to:", nav_options, key="nav", label_visibility="collapsed")
        return selected


# ═══════════════════════════════════════════════════════════════════════════════
#  HOME PAGE
# ═══════════════════════════════════════════════════════════════════════════════

def show_home():
    """Render the home/dashboard page with modern styling."""
    st.title(f"{CLINIC_LOGO} {APP_NAME}")
    st.markdown(f"### {HOSPITAL_NAME} — {CLINIC_SPECIALTY} Department")
    st.markdown(
        '<div style="margin-bottom: 1rem;"><span style="background-color:#00b894;color:white;padding:4px 10px;border-radius:12px;font-size:0.8rem;font-weight:bold;box-shadow:0 2px 8px rgba(0,184,148,0.3);">🚀 Upgrade v2.0 (Local-First)</span></div>',
        unsafe_allow_html=True
    )

    # ─── Welcome section with role-based greeting ──────────────────────────
    role = st.session_state.get("auth_role", "Guest")
    username = st.session_state.get("auth_username", "Guest")

    if role and role != "Guest" and role != "Patient":
        st.markdown(f"""
        <div style="background:linear-gradient(135deg,#667eea20,#764ba220);
                    padding:1rem 1.5rem;border-radius:12px;margin:0.5rem 0 1.5rem;
                    border-left:4px solid #667eea;">
            <span style="font-size:1.1rem;font-weight:600;">👋 Welcome, {username}!</span>
            <span style="color:#636e72;margin-left:1rem;">You are logged in as <strong>{role}</strong></span>
        </div>
        """, unsafe_allow_html=True)

    # ─── Quick Stats Cards ─────────────────────────────────────────────────
    try:
        harness = get_harness()
        stats = harness.get_all_dashboard_stats()

        # Compute totals
        total_waiting = sum(s.get("waiting", 0) for s in stats.values())
        total_in_progress = sum(s.get("in_progress", 0) for s in stats.values())
        total_completed = sum(s.get("completed", 0) for s in stats.values())

        st.markdown("### 📊 Today's Overview")

        cols = st.columns(4)
        metrics_data = [
            ("👥 Total Today", str(total_waiting + total_in_progress + total_completed), "patients registered"),
            ("⏳ Waiting", str(total_waiting), "awaiting service"),
            ("🟠 In Progress", str(total_in_progress), "being served"),
            ("✅ Completed", str(total_completed), "tests done today"),
        ]
        for col, (label, value, delta) in zip(cols, metrics_data):
            with col:
                st.metric(label, value, delta)
    except Exception:
        st.info("📊 Awaiting data...")

    # ─── Module Overview ────────────────────────────────────────────────────
    st.markdown("---")
    col1, col2 = st.columns([3, 2])

    with col1:
        st.markdown(f"""
        ### 👋 Welcome to CardioQueue

        A smart queue management system for {CLINIC_SPECIALTY.lower()} departments.

        **Modules:**
        - 📋 **Reception** — Register patients, print tokens, view status
        - 📊 **ECG / Echo / TMT / OPD** — Technician dashboards with live queues
        - 🩺 **Doctor** — Manage reports and delivery
        - 🔍 **Patient Status** — Self-service check for patients
        - 📈 **Manager Dashboard** — Full clinic overview

        **Key Features:**
        - ✅ Real-time queue management
        - ✅ Browser notifications on mobile
        - ✅ Token printing & QR codes
        - ✅ Zero monthly cost
        - ✅ PIN-based staff login
        - ✅ PWA support for mobile
        """)

    with col2:
        st.markdown("### 🏥 Department Stats")
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

    # Request notification permission on first load
    if not st.session_state.notification_permission_requested:
        st.markdown(request_notification_permission_script(), unsafe_allow_html=True)
        st.session_state.notification_permission_requested = True

    # ─── QR auto-load: bypass login, go straight to Patient Status ───────
    if patient_qr:
        from pages.Patient_Status import show
        show()
        return

    # ─── Inactivity auto-logout check (staff only) ────────────────────────
    _check_inactivity_logout()

    # ─── Login Flow ──────────────────────────────────────────────────────────
    if not st.session_state.authenticated:
        # Hide sidebar during login for clean look
        render_login_page()
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

    elif page == "🩻 X-Ray":
        from pages.XRay import show
        show()

    elif page == "📡 Ultrasound":
        from pages.Ultrasound import show
        show()

    elif page == "🧪 Lab":
        from pages.Lab import show
        show()

    elif page == "💊 Pharmacy":
        from pages.Pharmacy import show
        show()

    elif page == "📅 Follow-up":
        from pages.FollowUp import show
        show()

    elif page == "🚑 Emergency":
        from pages.Emergency import show
        show()

    elif page == "👩‍⚕️ Nurse Station":
        from pages.Nurse import show
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

    elif page == "📋 Patient History":
        from pages.Patient_History import show
        show()

    elif page == "📄 Daily List":
        from pages.Daily_List import show
        show()

    elif page == "📋 Activity Log":
        from pages.Activity_Log import show
        show()

    elif page == "📊 Reports & Analytics":
        from pages.Analytics import show
        show()

    elif page == "👑 Admin Panel":
        from pages.Admin import show
        show()

    elif page == "🔐 Password Management":
        from pages.Password_Management import show
        show()

    elif page == "📅 Appointments":
        from pages.Appointments import show
        show()

    elif page == "💳 Billing":
        from pages.Billing import show
        show()

    elif page == "⭐ Feedback":
        from pages.Feedback import show
        show()

    elif page == "🏥 IPD Ward":
        from pages.IPD_Ward import show
        show()

    elif page == "🏥 IPD Ward":
        from pages.IPD_Ward import show
        show()

    elif page == "📦 Inventory":
        from pages.Inventory import show
        show()

    elif page == "📋 Purchase Orders":
        from pages.Purchase import show
        show()

    elif page == "🏢 Vendors":
        from pages.Vendor import show
        show()

    elif page == "👥 HR":
        from pages.HR import show
        show()

    elif page == "💰 Payroll":
        from pages.Payroll import show
        show()

    elif page == "📊 Finance":
        from pages.Finance import show
        show()

    elif page == "🤖 AI Triage":
        from pages.AI_Triage import show
        show()

    elif page == "🤖 AI Follow-up":
        from pages.AI_FollowUp import show
        show()

    elif page == "🤖 AI Receptionist":
        from pages.AI_Receptionist import show
        show()

    elif page == "👑 Owner Dashboard":
        from pages.Owner_Dashboard import show
        show()

    elif page == "🏥 Patient Portal":
        from pages.Patient_Portal import show
        show()

    elif page == "🧪 Lab Technician":
        from pages.Lab_Technician import show
        show()

    elif page == "💰 Accountant":
        from pages.Accountant import show
        show()

    elif page == "🧾 GST":
        from pages.GST import show
        show()

    elif page == "🥗 AI Dietician":
        from pages.AI_Dietician import show
        show()

    elif page == "📄 AI Report Explainer":
        from pages.AI_Report_Explainer import show
        show()

    elif page == "📧 Email":
        from pages.Email import show
        show()

    elif page == "🔔 Push Notifications":
        from pages.PushNotifications import show
        show()

    elif page == "📞 Voice Calls":
        from pages.VoiceCall import show
        show()

    elif page == "🎥 Telemedicine":
        from pages.VideoCall import show
        show()

    elif page == "💊 AI Prescription":
        from pages.AI_Prescription import show
        show()

    elif page == "🎙️ AI Voice Agent":
        from pages.AI_VoiceAgent import show
        show()

    elif page == "💾 Backup":
        from pages.Backup import show
        show()

    elif page == "🔐 RBAC":
        from pages.RBAC import show
        show()

    elif page == "📋 Compliance":
        from pages.Compliance import show
        show()

    elif page == "📱 SMS Manager":
        from pages.SMS_Upgrade import show
        show()

    elif page == "🔒 Encryption":
        from pages.EncryptionPage import show
        show()

    elif page == "📊 System Monitoring":
        from pages.Monitoring import show
        show()

    elif page == "📋 System Logs":
        from pages.Logging import show
        show()

    elif page == "🏢 Multi-Branch":
        from pages.MultiBranch import show
        show()

    elif page == "📱 WhatsApp Business":
        from pages.WhatsAppUpgrade import show
        show()

    elif page == "💊 Pharmacist":
        from pages.Pharmacist import show
        show()

    elif page == "🕐 Patient Timeline":
        from pages.Patient_Timeline import show
        show()

    elif page == "📍 Patient Tracking":
        from pages.Patient_Tracking import show
        show()


    if __name__ == "__main__":
        main()
