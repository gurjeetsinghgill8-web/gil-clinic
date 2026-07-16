"""QRIdentity value object for the Patient Engine.

Each patient gets a unique QR identity that enables:
- PWA login via QR scan (no credentials needed)
- Token slip QR codes
- Bedside / kiosk patient identification
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class QRIdentity:
    """Immutable QR identity value object.

    Attributes:
        qr_hash: SHA-256 hash of the QR payload for lookup.
        qr_payload: Encrypted payload containing patient_id + salt + expiry.
        generated_at: When the QR was generated.
        expires_at: Optional expiry — QR codes can be time-limited.
    """

    qr_hash: str
    qr_payload: str
    generated_at: datetime
    expires_at: datetime | None = None

    @classmethod
    def create(
        cls,
        qr_hash: str,
        qr_payload: str,
        expires_at: datetime | None = None,
    ) -> QRIdentity:
        return cls(
            qr_hash=qr_hash,
            qr_payload=qr_payload,
            generated_at=datetime.now(timezone.utc),
            expires_at=expires_at,
        )

    @property
    def is_expired(self) -> bool:
        """Check if this QR identity has expired."""
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def is_valid(self) -> bool:
        """QR is valid if not expired."""
        return not self.is_expired

    def __repr__(self) -> str:
        status = "EXPIRED" if self.is_expired else "valid"
        return f"<QRIdentity hash={self.qr_hash[:12]}... {status}>"
