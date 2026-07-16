"""OTP code value object for the Identity Engine.

Manages the lifecycle of a one-time password:
- Generation (handled by infrastructure OtpService)
- Verification against stored hash
- Attempt counting (max 5 attempts)
- Expiry (5-minute window)

OTPs are stored as SHA-256 hashes, never in plaintext.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from src.shared.domain.base_entity import BaseEntity

if TYPE_CHECKING:
    import uuid


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
OTP_EXPIRY_MINUTES: int = 5
MAX_OTP_ATTEMPTS: int = 5
OTP_LENGTH: int = 6


@dataclass
class OtpCode(BaseEntity):
    """OTP code value object (entity-like with identity for DB mapping).

    Although it has an id for persistence, in the domain it behaves
    like a value object attached to a User.

    Attributes:
        user_id: UUID of the user who requested the OTP.
        code_hash: SHA-256 hash of the OTP code.
        attempts: Number of verification attempts made.
        expires_at: When the OTP expires (5 min from creation).
    """

    user_id: uuid.UUID
    code_hash: str
    attempts: int = 0
    expires_at: datetime | None = None

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        user_id: uuid.UUID,
        code_hash: str,
        expiry_minutes: int = OTP_EXPIRY_MINUTES,
    ) -> OtpCode:
        """Create a new OTP code.

        Args:
            user_id: UUID of the requesting user.
            code_hash: SHA-256 hash of the generated OTP.
            expiry_minutes: OTP lifetime in minutes (default 5).

        Returns:
            A new OtpCode instance.
        """
        return cls(
            user_id=user_id,
            code_hash=code_hash,
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=expiry_minutes),
        )

    # ------------------------------------------------------------------
    # State Checks
    # ------------------------------------------------------------------

    @property
    def is_expired(self) -> bool:
        """Check if the OTP has expired."""
        if self.expires_at is None:
            return False
        return self.expires_at <= datetime.now(timezone.utc)

    @property
    def is_max_attempts_reached(self) -> bool:
        """Check if max verification attempts have been reached."""
        return self.attempts >= MAX_OTP_ATTEMPTS

    @property
    def can_verify(self) -> bool:
        """Check if verification is still allowed.

        Returns:
            True if not expired and attempts remaining.
        """
        return not self.is_expired and not self.is_max_attempts_reached

    @property
    def remaining_attempts(self) -> int:
        """Number of remaining verification attempts."""
        return max(0, MAX_OTP_ATTEMPTS - self.attempts)

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------

    def verify(self, otp: str, otp_service) -> bool:
        """Verify an OTP against the stored hash.

        Increments attempt counter regardless of success/failure.

        Args:
            otp: Plaintext OTP to verify.
            otp_service: OtpService protocol for hash verification.

        Returns:
            True if OTP matches and is not expired.

        Raises:
            OtpExpiredError: If OTP has expired.
            MaxOtpAttemptsError: If max attempts reached.
        """
        from src.domain.identity.exceptions.domain_error import (
            MaxOtpAttemptsError,
            OtpExpiredError,
        )

        if self.is_expired:
            raise OtpExpiredError(
                details={"otp_id": str(self.id)}
            )

        if self.is_max_attempts_reached:
            raise MaxOtpAttemptsError(
                details={"otp_id": str(self.id)}
            )

        self.attempts += 1

        if otp_service.verify(otp, self.code_hash):
            return True

        return False

    def __repr__(self) -> str:
        return (
            f"<OtpCode id={self.id} "
            f"user_id={self.user_id} "
            f"expired={self.is_expired} "
            f"attempts={self.attempts}/{MAX_OTP_ATTEMPTS}>"
        )
