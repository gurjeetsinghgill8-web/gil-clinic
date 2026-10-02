"""
Patient portal tokens + phone verification helpers (Smart OPD).

Do tarah ke link hote hain (dono me **token hi secret** hai):
  * Portal link  : `/my/<token>`  — patient apni readings bharta hai (write)
  * Share link   : `/s/<token>`   — koi bhi doctor sirf **padhta** hai (read-only, 7 din)

Token DB me **random** (`secrets.token_urlsafe`) store hota hai — signed payload
nahi — taaki doctor/patient use **band (revoke)** kar sake aur naya bana sake.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import os
import secrets
import re
from typing import Optional

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

SECRET_KEY = os.getenv("SECRET_KEY", "gil-clinic-secret-2024-change-in-prod")

#: Patient ke phone-verify session cookie ka signer (12 ghante)
_patient_signer = URLSafeTimedSerializer(SECRET_KEY, salt="patient-portal-session-v1")
PATIENT_SESSION_COOKIE_PREFIX = "patient_session_"
PATIENT_SESSION_MAX_AGE = 60 * 60 * 12

#: Share link kitne din chalta hai (patient ko UI me dikhta hai)
SHARE_DAYS_DEFAULT = 7
#: Portal link kitne din tak valid (0 = koi expiry nahi, doctor revoke kare)
PORTAL_DAYS_DEFAULT = 90


def new_token(nbytes: int = 24) -> str:
    """URL-safe random token (~192-bit). Ye hi patient/doctor ke link me jata hai."""
    return secrets.token_urlsafe(nbytes)


def token_fingerprint(token: str) -> str:
    """Logs ke liye chhota fingerprint — **poora token kabhi log nahi** karte."""
    return hashlib.sha256(str(token or "").encode()).hexdigest()[:12]


def make_patient_session(token: str) -> str:
    return _patient_signer.dumps({"t": str(token), "ts": _dt.datetime.now(_dt.timezone.utc).isoformat()})


def read_patient_session(value: Optional[str], token: str) -> bool:
    """Cookie valid hai aur isi token ka hai?"""
    if not value:
        return False
    try:
        data = _patient_signer.loads(value, max_age=PATIENT_SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return False
    return str(data.get("t") or "") == str(token or "")


# ─────────────────────────────────────────────────────────────────────────────
# Phone helpers (verification + masking)
# ─────────────────────────────────────────────────────────────────────────────
def digits_only(phone: Optional[str]) -> str:
    return re.sub(r"\D", "", str(phone or ""))


def normalize_phone(phone: Optional[str]) -> str:
    """10-digit mobile (India) — aage ka 91 / 0 hata kar."""
    d = digits_only(phone)
    if len(d) > 10:
        d = d[-10:]
    return d


def phone_last4(phone: Optional[str]) -> str:
    d = normalize_phone(phone)
    return d[-4:] if len(d) >= 4 else ""


def phone_hash(phone: Optional[str]) -> str:
    """Same scheme jo patient registration me use hota hai: sha256(phone)."""
    return hashlib.sha256(str(phone or "").encode()).hexdigest()


def phone_matches(entered: Optional[str], stored_phone: Optional[str], stored_hash: Optional[str] = None) -> bool:
    """Patient ne jo number dala wo clinic me darj number se match karta hai?

    Teen tarah se check karte hain (jitna data maujood ho):
      1. digits (last 10) comparison — sabse bharosemand
      2. sha256(digits) vs stored phone_hash
      3. sha256(raw entered) vs stored phone_hash (purana data jaisa hai waisa)
    """
    ent = normalize_phone(entered)
    if len(ent) < 10:
        return False
    stored = normalize_phone(stored_phone)
    if len(stored) >= 10 and stored == ent:
        return True
    if stored_hash:
        if phone_hash(ent) == stored_hash:
            return True
        if phone_hash(str(entered or "")) == stored_hash:
            return True
        if phone_hash(digits_only(entered)) == stored_hash:
            return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Expiry helpers
# ─────────────────────────────────────────────────────────────────────────────
def now_utc() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


def share_expiry(days: int = SHARE_DAYS_DEFAULT) -> _dt.datetime:
    return now_utc() + _dt.timedelta(days=max(1, int(days or SHARE_DAYS_DEFAULT)))


def portal_expiry(days: int = PORTAL_DAYS_DEFAULT) -> Optional[_dt.datetime]:
    if not days or int(days) <= 0:
        return None
    return now_utc() + _dt.timedelta(days=int(days))


def is_expired(value: Optional[_dt.datetime]) -> bool:
    """None = koi expiry nahi. Naive datetime ko UTC maan lete hain (SQLite)."""
    if value is None:
        return False
    dt = value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_dt.timezone.utc)
    return dt < now_utc()
