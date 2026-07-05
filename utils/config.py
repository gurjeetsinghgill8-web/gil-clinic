"""
Configuration module for CardioQueue.
Centralizes all constants, environment variables, and settings.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ─── Supabase ────────────────────────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://your-project-id.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "your-supabase-anon-key")

# ─── App Info ────────────────────────────────────────────────────────────────
APP_NAME = os.getenv("APP_NAME", "CardioQueue")
HOSPITAL_NAME = os.getenv("HOSPITAL_NAME", "GIL CLINIC")
CLINIC_SPECIALTY = os.getenv("CLINIC_SPECIALTY", "Cardiology")  # e.g. Dental, Radiology
CLINIC_LOGO = os.getenv("CLINIC_LOGO", "🏥")  # Emoji for branding

# ─── Staff Mobile Numbers (for WhatsApp alerts) ──────────────────────────────
DOCTOR_MOBILE = os.getenv("DOCTOR_MOBILE", "")
BABLU_MOBILE = os.getenv("BABLU_MOBILE", "")

# ─── Admin Credentials (for the new Admin role) ──────────────────────────────
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "gurjas@123")

# ─── Test Types ──────────────────────────────────────────────────────────────
TEST_TYPES = ["ECG", "Echo", "TMT", "Holter", "ABPM", "OPD"]

# ─── Status Flow ─────────────────────────────────────────────────────────────
# The lifecycle of a test status
TEST_STATUS_FLOW = [
    "waiting",
    "called",
    "in_progress",
    "completed",
    "report_ready",
    "delivered",
]

# ─── Average Test Durations (minutes) ────────────────────────────────────────
AVG_TEST_TIME = {
    "ECG":   int(os.getenv("AVG_ECG_TIME", "10")),
    "Echo":  int(os.getenv("AVG_ECHO_TIME", "20")),
    "TMT":   int(os.getenv("AVG_TMT_TIME", "30")),
    "Holter": int(os.getenv("AVG_HOLTER_TIME", "15")),
    "ABPM":  int(os.getenv("AVG_ABPM_TIME", "15")),
    "OPD":   int(os.getenv("AVG_OPD_TIME", "10")),
}

# ─── Room Names ──────────────────────────────────────────────────────────────
ROOM_NAMES = {
    "ECG":   "ECG Room 1",
    "Echo":  "Echo Room 1",
    "TMT":   "TMT Room 1",
    "Holter": "Holter Room",
    "ABPM":  "ABPM Room",
    "OPD":   "OPD Room",
}

# ─── Patient ID Prefix ──────────────────────────────────────────────────────
PATIENT_ID_PREFIX = "CQ"

# ─── PWA / QR Code Settings ────────────────────────────────────────────────────
# Base URL for QR codes — update to your Streamlit Cloud URL when deployed
BASE_URL = os.getenv("BASE_URL", "http://localhost:8501")

# ─── Status Display Helpers ──────────────────────────────────────────────────
STATUS_ICONS = {
    "waiting":       "🟡",
    "called":        "🔵",
    "in_progress":   "🟠",
    "completed":     "✅",
    "report_ready":  "📋",
    "delivered":     "📄",
}

STATUS_LABELS = {
    "waiting":       "Waiting",
    "called":        "Called",
    "in_progress":   "In Progress",
    "completed":     "Completed",
    "report_ready":  "Report Ready",
    "delivered":     "Delivered",
}
