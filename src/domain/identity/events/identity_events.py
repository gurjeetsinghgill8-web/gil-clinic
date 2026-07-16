"""Domain events for the Identity Engine.

All 19 IDENTITY.* event types.

Identity publishes events only — never makes direct calls to other engines.
Events follow CloudEvents 1.0 specification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class IdentityEvent:
    """Base class for all Identity domain events.

    Attributes:
        event_name: Fully qualified event name (e.g., "IDENTITY.USER.LOGIN").
        aggregate_id: UUID of the aggregate that generated the event.
        timestamp: When the event occurred (UTC).
        payload: Event-specific data.
    """

    event_name: str
    aggregate_id: str
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to CloudEvents-compatible dict."""
        return {
            "specversion": "1.0",
            "type": self.event_name,
            "source": "/api/v1/identity",
            "subject": self.aggregate_id,
            "time": self.timestamp.isoformat(),
            "datacontenttype": "application/json",
            "data": {
                "aggregateId": self.aggregate_id,
                **self.payload,
            },
        }


# =============================================================================
# Concrete Event Helpers
# =============================================================================

def user_created(
    user_id: str,
    username: str,
    role: str,
    department: str | None,
) -> IdentityEvent:
    """Published when a new staff user is created."""
    return IdentityEvent(
        event_name="IDENTITY.USER.CREATED",
        aggregate_id=user_id,
        payload={
            "username": username,
            "role": role,
            "department": department,
        },
    )


def user_updated(
    user_id: str,
    changed_fields: list[str],
) -> IdentityEvent:
    """Published when a user's profile is updated."""
    return IdentityEvent(
        event_name="IDENTITY.USER.UPDATED",
        aggregate_id=user_id,
        payload={"changedFields": changed_fields},
    )


def user_disabled(user_id: str, reason: str | None = None) -> IdentityEvent:
    """Published when a user is deactivated."""
    return IdentityEvent(
        event_name="IDENTITY.USER.DISABLED",
        aggregate_id=user_id,
        payload={"reason": reason},
    )


def user_reactivated(user_id: str) -> IdentityEvent:
    """Published when a user is reactivated."""
    return IdentityEvent(
        event_name="IDENTITY.USER.REACTIVATED",
        aggregate_id=user_id,
    )


def user_login(
    user_id: str,
    session_id: str,
    device_id: str | None,
    ip_address: str | None,
) -> IdentityEvent:
    """Published on successful login."""
    return IdentityEvent(
        event_name="IDENTITY.USER.LOGIN",
        aggregate_id=user_id,
        payload={
            "sessionId": session_id,
            "deviceId": device_id,
            "ip": ip_address,
        },
    )


def user_logout(user_id: str, session_id: str) -> IdentityEvent:
    """Published when a user logs out."""
    return IdentityEvent(
        event_name="IDENTITY.USER.LOGOUT",
        aggregate_id=user_id,
        payload={"sessionId": session_id},
    )


def otp_sent(user_id: str, purpose: str) -> IdentityEvent:
    """Published when an OTP is requested."""
    return IdentityEvent(
        event_name="IDENTITY.OTP.SENT",
        aggregate_id=user_id,
        payload={"purpose": purpose},
    )


def otp_verified(user_id: str, purpose: str) -> IdentityEvent:
    """Published when an OTP is successfully verified."""
    return IdentityEvent(
        event_name="IDENTITY.OTP.VERIFIED",
        aggregate_id=user_id,
        payload={"purpose": purpose},
    )


def token_refreshed(
    user_id: str,
    old_token_id: str,
    new_token_id: str,
) -> IdentityEvent:
    """Published when an access token is refreshed (with rotation)."""
    return IdentityEvent(
        event_name="IDENTITY.TOKEN.REFRESHED",
        aggregate_id=user_id,
        payload={
            "oldTokenId": old_token_id,
            "newTokenId": new_token_id,
        },
    )


def role_assigned(
    user_id: str,
    old_role: str | None,
    new_role: str,
) -> IdentityEvent:
    """Published when a user's role is changed."""
    return IdentityEvent(
        event_name="IDENTITY.ROLE.ASSIGNED",
        aggregate_id=user_id,
        payload={
            "oldRole": old_role,
            "newRole": new_role,
        },
    )


def login_failed(
    user_id: str,
    method: str,
    attempt_count: int,
) -> IdentityEvent:
    """Published on a failed login attempt."""
    return IdentityEvent(
        event_name="IDENTITY.AUTH.FAILED",
        aggregate_id=user_id,
        payload={
            "method": method,
            "attemptCount": attempt_count,
        },
    )


def account_locked(
    user_id: str,
    locked_until: str,
) -> IdentityEvent:
    """Published when an account is locked (5 failed attempts)."""
    return IdentityEvent(
        event_name="IDENTITY.AUTH.LOCKED",
        aggregate_id=user_id,
        payload={"lockedUntil": locked_until},
    )


def account_unlocked(user_id: str, unlocked_by: str) -> IdentityEvent:
    """Published when an account is unlocked (admin or auto-expiry)."""
    return IdentityEvent(
        event_name="IDENTITY.AUTH.UNLOCKED",
        aggregate_id=user_id,
        payload={"unlockedBy": unlocked_by},
    )


def pin_changed(user_id: str) -> IdentityEvent:
    """Published when a PIN is changed."""
    return IdentityEvent(
        event_name="IDENTITY.PIN.CHANGED",
        aggregate_id=user_id,
    )


def session_expired(
    user_id: str,
    session_id: str,
    reason: str,
) -> IdentityEvent:
    """Published when a session expires or times out."""
    return IdentityEvent(
        event_name="IDENTITY.SESSION.EXPIRED",
        aggregate_id=user_id,
        payload={
            "sessionId": session_id,
            "reason": reason,
        },
    )


def session_revoked(
    user_id: str,
    session_id: str,
    revoked_by: str,
) -> IdentityEvent:
    """Published when a session is revoked by an admin."""
    return IdentityEvent(
        event_name="IDENTITY.SESSION.REVOKED",
        aggregate_id=user_id,
        payload={
            "sessionId": session_id,
            "revokedBy": revoked_by,
        },
    )


def security_alert(
    user_id: str,
    alert_type: str,
    details: dict | None = None,
) -> IdentityEvent:
    """Published when suspicious activity is detected."""
    return IdentityEvent(
        event_name="IDENTITY.SECURITY.ALERT",
        aggregate_id=user_id,
        payload={
            "alertType": alert_type,
            "details": details or {},
        },
    )


def device_trusted(
    user_id: str,
    session_id: str,
    device_id: str,
) -> IdentityEvent:
    """Published when a device is marked as trusted."""
    return IdentityEvent(
        event_name="IDENTITY.DEVICE.TRUSTED",
        aggregate_id=user_id,
        payload={
            "sessionId": session_id,
            "deviceId": device_id,
        },
    )


def device_untrusted(user_id: str, device_id: str) -> IdentityEvent:
    """Published when device trust is revoked."""
    return IdentityEvent(
        event_name="IDENTITY.DEVICE.UNTRUSTED",
        aggregate_id=user_id,
        payload={"deviceId": device_id},
    )
