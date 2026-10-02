"""Patient infrastructure config/settings."""

from __future__ import annotations


PATIENT_QR_EXPIRY_HOURS: int = 72  # QR codes valid for 72 hours
PATIENT_INACTIVITY_DAYS: int = 90  # Mark patient inactive after 90 days
MAX_DEVICES_PER_PATIENT: int = 10  # Max registered devices per patient
PATIENT_ID_PREFIX: str = "CQ"  # Prefix for human-readable patient IDs
