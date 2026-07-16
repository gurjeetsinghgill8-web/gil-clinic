"""DeviceInfo value object for the Patient Engine.

Records registered devices for PWA-based patient experience.
Patients can register devices to receive:
- Push notifications (status updates, alerts)
- One-click login via QR scan
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class DeviceRegistration:
    """Immutable device registration.

    Attributes:
        device_id: Unique device identifier (browser fingerprint, device UUID).
        device_name: Human-readable name (e.g., "Patient's iPhone").
        push_token: FCM / Web Push token for notifications.
        platform: 'web', 'android', 'ios'.
        user_agent: Browser / device user-agent string.
        ip_address: IP at time of registration.
        registered_at: When the device was first registered.
        last_seen_at: Last activity timestamp.
    """

    device_id: str
    device_name: str | None = None
    push_token: str | None = None
    platform: str = "web"
    user_agent: str | None = None
    ip_address: str | None = None
    registered_at: datetime = datetime.now(timezone.utc)
    last_seen_at: datetime = datetime.now(timezone.utc)

    @classmethod
    def register(
        cls,
        device_id: str,
        device_name: str | None = None,
        push_token: str | None = None,
        platform: str = "web",
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> DeviceRegistration:
        return cls(
            device_id=device_id,
            device_name=device_name,
            push_token=push_token,
            platform=platform,
            user_agent=user_agent,
            ip_address=ip_address,
        )

    def seen_now(self) -> DeviceRegistration:
        """Return a new instance with updated last_seen_at (immutable pattern)."""
        return DeviceRegistration(
            device_id=self.device_id,
            device_name=self.device_name,
            push_token=self.push_token,
            platform=self.platform,
            user_agent=self.user_agent,
            ip_address=self.ip_address,
            registered_at=self.registered_at,
            last_seen_at=datetime.now(timezone.utc),
        )

    def __repr__(self) -> str:
        return f"<DeviceRegistration {self.device_name or self.device_id[:12]} ({self.platform})>"
