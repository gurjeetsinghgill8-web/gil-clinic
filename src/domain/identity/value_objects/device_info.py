"""DeviceInfo value object for the Identity Engine.

Captures information about the device used during authentication.
This is used for:
- Multi-device session tracking
- Device trust management
- Security auditing
- Suspicious login detection
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DeviceInfo:
    """Immutable device information value object.

    Attributes:
        device_id: Unique device identifier (e.g., fingerprint hash).
        device_name: Human-readable device name (e.g., "iPhone 15").
        user_agent: Browser / HTTP user agent string.
        ip_address: IP address of the device.
    """

    device_id: str | None = None
    device_name: str | None = None
    user_agent: str | None = None
    ip_address: str | None = None

    @classmethod
    def unknown(cls) -> DeviceInfo:
        """Create a DeviceInfo representing an unknown device.

        Returns:
            DeviceInfo with all fields set to None.
        """
        return cls()

    @classmethod
    def from_request(
        cls,
        device_id: str | None = None,
        device_name: str | None = None,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> DeviceInfo:
        """Create DeviceInfo from request headers/metadata.

        Args:
            device_id: Client-provided device identifier.
            device_name: Client-provided device name.
            user_agent: User-Agent header value.
            ip_address: Request IP address.

        Returns:
            DeviceInfo with provided fields, None for missing.
        """
        return cls(
            device_id=device_id,
            device_name=device_name,
            user_agent=user_agent,
            ip_address=ip_address,
        )

    def is_known(self) -> bool:
        """Check if enough device info is available for identification.

        Returns:
            True if at least one identifying field is present.
        """
        return bool(self.device_id or self.user_agent or self.ip_address)

    def fingerprint(self) -> str | None:
        """Generate a simple device fingerprint.

        Uses device_id if available, otherwise generates from available fields.

        Returns:
            Fingerprint string, or None if no data available.
        """
        if self.device_id:
            return self.device_id
        if self.user_agent:
            import hashlib
            return hashlib.sha256(self.user_agent.encode()).hexdigest()[:16]
        return None

    def __repr__(self) -> str:
        return (
            f"<DeviceInfo "
            f"id={self.device_id or '?'} "
            f"name={self.device_name or '?'}>"
        )
