"""ABDM configuration reader — env vars se (`.env`).

Real NHA sandbox ke liye ye values chahiye (NHA developer portal se):
    ABDM_ENABLED=true
    ABDM_SANDBOX_URL=https://abdm-sandbox.abdm.gov.in
    ABDM_CLIENT_ID=<...>
    ABDM_CLIENT_SECRET=<...>
    ABDM_HIP_ID=<health information provider id>
    ABDM_HIU_ID=<health information user id>
    ABDM_FACILITY_ID=<HFR facility id>

Jab tak ye set nahi hote, `configured=False` — sirf local FHIR mapping + local
consent/ABHA/transaction records kaam karte hain (bina crash ke).
"""

from __future__ import annotations

import os


def abdm_config() -> dict:
    """Return the current ABDM configuration (secrets masked)."""
    client_secret = os.getenv("ABDM_CLIENT_SECRET", "")
    return {
        "enabled": os.getenv("ABDM_ENABLED", "false").strip().lower() in ("true", "1", "yes"),
        "configured": bool(os.getenv("ABDM_CLIENT_ID", "").strip() and client_secret),
        "sandbox_url": os.getenv("ABDM_SANDBOX_URL", "https://abdm-sandbox.abdm.gov.in").rstrip("/"),
        "client_id": os.getenv("ABDM_CLIENT_ID", "").strip(),
        "client_secret_set": bool(client_secret),
        "hip_id": os.getenv("ABDM_HIP_ID", "").strip(),
        "hiu_id": os.getenv("ABDM_HIU_ID", "").strip(),
        "facility_id": os.getenv("ABDM_FACILITY_ID", "").strip(),
    }
