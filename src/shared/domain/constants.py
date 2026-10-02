"""Shared constants used across all engines.

Single source of truth for domain-wide values.
"""

from __future__ import annotations

# =============================================================================
# Time Constants (seconds)
# =============================================================================
SECOND = 1
MINUTE = 60
HOUR = 60 * MINUTE
DAY = 24 * HOUR
WEEK = 7 * DAY

# =============================================================================
# Pagination
# =============================================================================
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# =============================================================================
# Auth
# =============================================================================
PIN_MIN_LENGTH = 4
PIN_MAX_LENGTH = 6
OTP_LENGTH = 6
OTP_EXPIRY_SECONDS = 5 * MINUTE
OTP_MAX_ATTEMPTS = 5
PIN_MAX_ATTEMPTS = 5
ACCOUNT_LOCKOUT_MINUTES = 30
SESSION_INACTIVITY_TIMEOUT_MINUTES = 15
MAX_SESSIONS_PER_USER = 5
ACCESS_TOKEN_EXPIRY_HOURS = 24
REFRESH_TOKEN_EXPIRY_DAYS = 7
BCRYPT_COST = 12

# =============================================================================
# Rate Limits
# =============================================================================
OTP_REQUEST_LIMIT = 3  # per 10 minutes
OTP_RESEND_COOLDOWN = 30  # seconds
AUTH_ENDPOINT_RATE_LIMIT = 10  # per minute per IP

# =============================================================================
# Roles
# =============================================================================
ROLE_HIERARCHY = {
    "ADMIN": 100,
    "MANAGER": 80,
    "DOCTOR": 60,
    "NURSE": 50,
    "RECEPTIONIST": 40,
    "TECHNICIAN": 40,
    "PHARMACIST": 40,
    "LAB_TECH": 40,
    "RADIOLOGIST": 40,
}

# =============================================================================
# Default Seed User PINs (development only)
# =============================================================================
DEFAULT_ADMIN_PASSWORD = "gurjas@123"
DEFAULT_STAFF_PIN = "1234"
