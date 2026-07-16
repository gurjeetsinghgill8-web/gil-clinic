"""Session aggregate for the Identity Engine.

The Session is a separate aggregate from User, enabling:
- Multi-device session tracking (concurrent sessions on different devices)
- Individual session revocation without logging out other sessions
- Device trust management
- Session expiry tracking

Session publishes events — it never calls other aggregates directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from src.shared.domain.base_entity import BaseEntity

if TYPE_CHECKING:
    import uuid

    from src.domain.identity.value_objects.device_info import DeviceInfo


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_SESSION_DURATION_HOURS: int = 24
MAX_SESSIONS_PER_USER: int = 10


@dataclass
class Session(BaseEntity):
    """User session aggregate.

    Represents a single authenticated session for a user on a specific device.
    Sessions are independent — revoking one does not affect others.

    Attributes:
        user_id: UUID of the owning User.
        device_id: Device identifier (optional).
        device_name: Human-readable device name.
        user_agent: Browser/device user agent string.
        ip_address: IP address at session creation.
        last_activity: Timestamp of the last request.
        is_trusted: Whether the device is marked as trusted.
        expires_at: When the session expires (default 24h from creation).
        revoked_at: When the session was revoked (None = active).
    """

    user_id: uuid.UUID
    device_id: str | None = None
    device_name: str | None = None
    user_agent: str | None = None
    ip_address: str | None = None
    last_activity: datetime | None = None
    is_trusted: bool = False
    expires_at: datetime | None = None
    revoked_at: datetime | None = None

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        user_id: uuid.UUID,
        device_info: DeviceInfo | None = None,
        duration_hours: int = DEFAULT_SESSION_DURATION_HOURS,
    ) -> Session:
        """Create a new authenticated session.

        Args:
            user_id: UUID of the authenticated user.
            device_info: Information about the device.
            duration_hours: Session lifetime in hours (default 24).

        Returns:
            A new active Session instance.
        """
        now = datetime.now(timezone.utc)
        return cls(
            user_id=user_id,
            device_id=device_info.device_id if device_info else None,
            device_name=device_info.device_name if device_info else None,
            user_agent=device_info.user_agent if device_info else None,
            ip_address=device_info.ip_address if device_info else None,
            last_activity=now,
            expires_at=now + timedelta(hours=duration_hours),
        )

    # ------------------------------------------------------------------
    # State Checks
    # ------------------------------------------------------------------

    @property
    def is_active(self) -> bool:
        """Check if the session is still valid.

        A session is active if:
        - It has not been revoked
        - It has not expired
        """
        if self.revoked_at is not None:
            return False
        if self.expires_at and self.expires_at <= datetime.now(timezone.utc):
            return False
        return True

    @property
    def is_expired(self) -> bool:
        """Check if the session has passed its expiry time."""
        if self.expires_at is None:
            return False
        return self.expires_at <= datetime.now(timezone.utc)

    def time_remaining(self) -> timedelta:
        """Get the time remaining before session expiry.

        Returns:
            timedelta of remaining time (0 if expired or no expiry).
        """
        if self.expires_at is None:
            return timedelta()
        remaining = self.expires_at - datetime.now(timezone.utc)
        return max(remaining, timedelta())

    # ------------------------------------------------------------------
    # Activity
    # ------------------------------------------------------------------

    def record_activity(self) -> None:
        """Update the last_activity timestamp.

        Called on each authenticated request to keep the session alive.
        """
        self.last_activity = datetime.now(timezone.utc)
        self.touch()

    def extend_expiry(self, extra_hours: int = 24) -> None:
        """Extend the session expiry time.

        Args:
            extra_hours: Hours to add from now.
        """
        self.expires_at = datetime.now(timezone.utc) + timedelta(
            hours=extra_hours
        )
        self.touch()

    # ------------------------------------------------------------------
    # Revocation
    # ------------------------------------------------------------------

    def revoke(self, reason: str | None = None) -> None:
        """Revoke the session, making it inactive.

        Args:
            reason: Optional reason for revocation.
        """
        self.revoked_at = datetime.now(timezone.utc)
        self.touch()

    # ------------------------------------------------------------------
    # Device Trust
    # ------------------------------------------------------------------

    def mark_trusted(self) -> None:
        """Mark the device as trusted (skip MFA for future logins)."""
        self.is_trusted = True
        self.touch()

    def mark_untrusted(self) -> None:
        """Remove trusted status from the device."""
        self.is_trusted = False
        self.touch()

    def __repr__(self) -> str:
        return (
            f"<Session id={self.id} "
            f"user_id={self.user_id} "
            f"active={self.is_active} "
            f"device={self.device_name}>"
        )
