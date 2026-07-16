"""Clinic settings provider — reads/writes clinic_settings.json.

Provides a singleton-like accessor for ClinicSettings.
- If JSON file exists → reads from file
- If JSON file missing → uses environment variables → uses hardcoded defaults
- Admin API writes to JSON file (overrides env/defaults)

File location: cardioqueue_data/clinic_settings.json
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from src.domain.clinic.value_objects.clinic_settings import ClinicSettings

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATA_DIR = os.getenv("GHOS_JSON_DATA_DIR", "cardioqueue_data")
SETTINGS_FILE = os.path.join(DATA_DIR, "clinic_settings.json")

# ---------------------------------------------------------------------------
# Env-based defaults (override via .env / environment)
# ---------------------------------------------------------------------------

_ENV_NAME = os.getenv("GHOS_CLINIC_NAME", "")
_ENV_SPECIALTY = os.getenv("GHOS_CLINIC_SPECIALTY", "")
_ENV_LOGO = os.getenv("GHOS_CLINIC_LOGO", "")
_ENV_PHONE = os.getenv("GHOS_CLINIC_PHONE", "")
_ENV_ADDRESS = os.getenv("GHOS_CLINIC_ADDRESS", "")
_ENV_DOCTOR = os.getenv("GHOS_CLINIC_DOCTOR", "")


def _env_overrides() -> dict[str, str]:
    """Collect non-empty env overrides.

    Returns:
        Dict of setting fields that have env values.
    """
    overrides = {}
    if _ENV_NAME:
        overrides["name"] = _ENV_NAME
    if _ENV_SPECIALTY:
        overrides["specialty"] = _ENV_SPECIALTY
    if _ENV_LOGO:
        overrides["logo_emoji"] = _ENV_LOGO
    if _ENV_PHONE:
        overrides["phone"] = _ENV_PHONE
    if _ENV_ADDRESS:
        overrides["address"] = _ENV_ADDRESS
    if _ENV_DOCTOR:
        overrides["doctor_name"] = _ENV_DOCTOR
    return overrides


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------


def _load_from_file() -> dict[str, str] | None:
    """Load settings from JSON file.

    Returns:
        Dict of settings if file exists, None otherwise.
    """
    path = Path(SETTINGS_FILE)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _save_to_file(data: dict[str, str]) -> None:
    """Save settings to JSON file atomically.

    Args:
        data: Settings dict to persist.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    # Write to temp, then rename for atomicity
    tmp = SETTINGS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, SETTINGS_FILE)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_settings_cache: ClinicSettings | None = None


def get_clinic_settings() -> ClinicSettings:
    """Get the current clinic settings.

    Priority:
    1. JSON file (admin API writes here)
    2. Environment variables
    3. Hardcoded defaults

    Returns:
        Current ClinicSettings instance.
    """
    global _settings_cache

    # Start with hardcoded defaults
    settings = ClinicSettings.defaults()

    # Apply env overrides
    env_vals = _env_overrides()
    if env_vals:
        settings = settings.merge(env_vals)

    # Apply file overrides (highest priority)
    file_vals = _load_from_file()
    if file_vals:
        settings = settings.merge(file_vals)

    _settings_cache = settings
    return settings


def update_clinic_settings(overrides: dict[str, str]) -> ClinicSettings:
    """Update clinic settings and persist to JSON file.

    Only the provided fields are updated; others keep their current values.

    Args:
        overrides: Partial dict of settings to update.

    Returns:
        The new ClinicSettings after applying overrides.
    """
    current = get_clinic_settings()
    updated = current.merge(overrides)
    _save_to_file(updated.to_dict())

    global _settings_cache
    _settings_cache = updated
    return updated


def reset_clinic_settings() -> ClinicSettings:
    """Reset clinic settings to defaults (deletes the JSON file).

    Returns:
        Default ClinicSettings.
    """
    path = Path(SETTINGS_FILE)
    if path.exists():
        path.unlink()
    global _settings_cache
    _settings_cache = None
    return get_clinic_settings()


def settings_to_dict() -> dict[str, str]:
    """Get current settings as a flat dict.

    Returns:
        Dict with all setting fields.
    """
    return get_clinic_settings().to_dict()
