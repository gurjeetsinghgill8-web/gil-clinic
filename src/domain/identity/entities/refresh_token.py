"""Refresh token aggregate for the Identity Engine.

The RefreshToken is a separate aggregate from User and Session, enabling:
- Refresh token rotation (old token revoked when new one issued)
- Multi-device refresh token management
- Individual token revocation without affecting the session

Refresh token rotation:
1. Client sends refresh token → service validates it
2. Service issues NEW refresh token, revokes OLD one
3. If a revoked token is reused → all tokens for that user are revoked
   (suggests token theft — security alert is published)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from src.shared.domain.base_entity import BaseEntity

if TYPE_CHECKING:
    import uuid


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
REFRESH_TOKEN_EXPIRY_DAYS: int = 30


@dataclass
class RefreshToken(BaseEntity):
    """Refresh token aggregate.

    Attributes:
        user_id: UUID of the owning User.
        token_hash: SHA-256 hash of the raw refresh token.
        session_id: UUID of the associated Session (optional, SET NULL on delete).
        device_id: Device identifier (optional).
        is_revoked: Whether this token has been revoked.
        expires_at: When the token expires (default 30 days).
        revoked_at: When the token was revoked (None = active).
    """

    user_id: uuid.UUID
    token_hash: str
    session_id: uuid.UUID | None = None
    device_id: str | None = None
    is_revoked: bool = False
    expires_at: datetime | None = None
    revoked_at: datetime | None = None

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        user_id: uuid.UUID,
        token_hash: str,
        session_id: uuid.UUID | None = None,
        device_id: str | None = None,
        expiry_days: int = REFRESH_TOKEN_EXPIRY_DAYS,
    ) -> RefreshToken:
        """Create a new refresh token.

        Args:
            user_id: UUID of the token owner.
            token_hash: SHA-256 hash of the refresh token.
            session_id: Optional associated session.
            device_id: Optional device identifier.
            expiry_days: Token lifetime in days (default 30).

        Returns:
            A new active RefreshToken instance.
        """
        return cls(
            user_id=user_id,
            token_hash=token_hash,
            session_id=session_id,
            device_id=device_id,
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=expiry_days),
        )

    # ------------------------------------------------------------------
    # State Checks
    # ------------------------------------------------------------------

    @property
    def is_active(self) -> bool:
        """Check if the token is still valid.

        A token is active if:
        - It has not been revoked
        - It has not expired
        """
        if self.is_revoked:
            return False
        if self.expires_at and self.expires_at <= datetime.now(timezone.utc):
            return False
        return True

    @property
    def is_expired(self) -> bool:
        """Check if the token has passed its expiry time."""
        if self.expires_at is None:
            return False
        return self.expires_at <= datetime.now(timezone.utc)

    # ------------------------------------------------------------------
    # Token Rotation
    # ------------------------------------------------------------------

    def revoke(self) -> None:
        """Revoke this token.

        Called during token rotation when a new token is issued.
        """
        self.is_revoked = True
        self.revoked_at = datetime.now(timezone.utc)
        self.touch()

    def rotate(self, new_token_hash: str) -> RefreshToken:
        """Create a new token and revoke this one (rotation).

        The old token is revoked, and a new token is created.
        If a revoked token is subsequently reused, it indicates theft.

        Args:
            new_token_hash: SHA-256 hash of the new refresh token.

        Returns:
            A new RefreshToken representing the rotated token.
        """
        self.revoke()
        return RefreshToken.create(
            user_id=self.user_id,
            token_hash=new_token_hash,
            session_id=self.session_id,
            device_id=self.device_id,
        )

    # ------------------------------------------------------------------
    # Theft Detection
    # ------------------------------------------------------------------

    def detect_reuse(self) -> bool:
        """Check if a revoked token is being used again.

        Returns:
            True if this token has already been revoked (indicates theft).
        """
        return self.is_revoked

    def __repr__(self) -> str:
        return (
            f"<RefreshToken id={self.id} "
            f"user_id={self.user_id} "
            f"active={self.is_active}>"
        )
