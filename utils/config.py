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

# ─── Staff Auth (Phase 1 — simple password-based) ───────────────────────────
STAFF_PASSWORDS = {
    "Reception": os.getenv("RECEPTION_PASS", "recep123"),
    "ECG":       os.getenv("ECG_PASS", "ecg123"),
    "Echo":      os.getenv("ECHO_PASS", "echo123"),
    "TMT":       os.getenv("TMT_PASS", "tmt123"),
    "Doctor":    os.getenv("DOCTOR_PASS", "doc123"),
}

# ─── Test Types ──────────────────────────────────────────────────────────────
TEST_TYPES = ["ECG", "Echo", "TMT", "Holter", "ABPM"]

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
}

# ─── Room Names ──────────────────────────────────────────────────────────────
ROOM_NAMES = {
    "ECG":   "ECG Room 1",
    "Echo":  "Echo Room 1",
    "TMT":   "TMT Room 1",
    "Holter": "Holter Room",
    "ABPM":  "ABPM Room",
}

# ─── Patient ID Prefix ──────────────────────────────────────────────────────
PATIENT_ID_PREFIX = "CQ"

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
