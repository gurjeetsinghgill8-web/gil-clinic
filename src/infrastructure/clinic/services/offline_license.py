"""Offline License Cache — local license validation for doctor's machine.

When running locally (not on Railway), the system:
1. Validates license against central server on first login
2. Caches license locally for 7 days
3. Works offline during the cache period
4. Requires re-validation after cache expires
5. Gracefully degrades to read-only mode if license is expired
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
LICENSE_SERVER_URL = os.getenv(
    "LICENSE_SERVER_URL", "https://cardioqueue-production.up.railway.app"
)
CACHE_FILE = Path(os.getenv("LICENSE_CACHE_FILE", "./clinic_data/license_cache.json"))
CACHE_VALIDITY_DAYS = 7
GRACE_PERIOD_DAYS = 3  # Read-only mode for 3 days after expiry


class LicenseStatus:
    ACTIVE = "active"
    EXPIRING = "expiring"  # within 7 days
    EXPIRED = "expired"
    GRACE = "grace"  # expired but within grace period
    UNKNOWN = "unknown"


class OfflineLicenseManager:
    """Manages offline license validation and caching."""

    def __init__(self):
        self._cache: dict | None = None

    def _load_cache(self) -> dict | None:
        """Load cached license from local file."""
        try:
            if CACHE_FILE.exists():
                data = json.loads(CACHE_FILE.read_text())
                logger.debug("License cache loaded from %s", CACHE_FILE)
                return data
        except Exception as e:
            logger.warning("Failed to load license cache: %s", e)
        return None

    def _save_cache(self, data: dict) -> None:
        """Save license data to local cache file."""
        try:
            CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            CACHE_FILE.write_text(json.dumps(data, indent=2))
            logger.info("License cache saved to %s", CACHE_FILE)
        except Exception as e:
            logger.error("Failed to save license cache: %s", e)

    async def validate_with_server(self, clinic_code: str) -> dict:
        """Validate license against central server.

        Args:
            clinic_code: Clinic code (e.g., "CLINIC-001").

        Returns:
            dict with license status and expiry info.
        """
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{LICENSE_SERVER_URL}/api/license/check/{clinic_code}"
                )
                if response.status_code == 200:
                    data = response.json()
                    data["cached_at"] = datetime.now(timezone.utc).isoformat()
                    self._save_cache(data)
                    return data
                else:
                    logger.warning(
                        "License server returned %d", response.status_code
                    )
        except Exception as e:
            logger.warning("Cannot reach license server: %s", e)

        # Fall back to cache
        return self._load_cache() or {"status": LicenseStatus.UNKNOWN}

    def check_local(self) -> dict:
        """Check locally cached license status.

        Returns:
            dict with status and details.
        """
        cache = self._load_cache()
        if not cache:
            return {
                "status": LicenseStatus.UNKNOWN,
                "message": "No license found. Contact admin.",
                "is_valid": False,
            }

        cached_at = cache.get("cached_at", "")
        expiry_str = cache.get("license_expiry_date", "")

        try:
            # Check cache freshness
            if cached_at:
                cache_date = datetime.fromisoformat(cached_at)
                cache_age = datetime.now(timezone.utc) - cache_date
                if cache_age > timedelta(days=CACHE_VALIDITY_DAYS):
                    return {
                        "status": LicenseStatus.UNKNOWN,
                        "message": "License cache expired. Internet required for re-validation.",
                        "is_valid": False,
                    }

            # Check license expiry
            if expiry_str:
                expiry = date.fromisoformat(expiry_str[:10])
                today = date.today()
                days_left = (expiry - today).days

                if days_left < 0:
                    # Expired
                    if abs(days_left) <= GRACE_PERIOD_DAYS:
                        return {
                            "status": LicenseStatus.GRACE,
                            "message": f"License expired {abs(days_left)} days ago. Read-only mode.",
                            "is_valid": True,  # Allow read-only
                            "days_left": days_left,
                            "readonly": True,
                        }
                    return {
                        "status": LicenseStatus.EXPIRED,
                        "message": f"License expired. Contact admin.",
                        "is_valid": False,
                        "days_left": days_left,
                    }
                elif days_left <= 7:
                    return {
                        "status": LicenseStatus.EXPIRING,
                        "message": f"License expires in {days_left} days.",
                        "is_valid": True,
                        "days_left": days_left,
                    }
                else:
                    return {
                        "status": LicenseStatus.ACTIVE,
                        "message": f"License active. {days_left} days remaining.",
                        "is_valid": True,
                        "days_left": days_left,
                    }
        except (ValueError, TypeError) as e:
            logger.error("License date parse error: %s", e)

        return {
            "status": LicenseStatus.ACTIVE,
            "message": "License active.",
            "is_valid": True,
        }


# Singleton instance
license_manager = OfflineLicenseManager()
