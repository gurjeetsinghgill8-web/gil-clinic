"""OTP repository interface (port).

Defines the contract for persisting and retrieving OTP codes.
Implemented by SqlAlchemyOtpRepository in the infrastructure layer.

OTPs have a short lifecycle — created during authentication flow,
verified/deleted within minutes.
"""

from __future__ import annotations

from typing import Protocol

from src.domain.identity.value_objects.otp_code import OtpCode


class OtpRepository(Protocol):
    """Interface for OTP code persistence.

    OTPs are ephemeral — they expire in 5 minutes and are cleaned up
    by the CleanupService background job.
    """

    async def save(self, otp: OtpCode) -> None:
        """Persist a new OTP code.

        Args:
            otp: OtpCode value object to save.
        """
        ...

    async def get_by_id(self, otp_id: str) -> OtpCode | None:
        """Get an OTP by its UUID.

        Args:
            otp_id: UUID string.

        Returns:
            OtpCode if found, None otherwise.
        """
        ...

    async def get_latest_by_user_id(self, user_id: str) -> OtpCode | None:
        """Get the most recent OTP for a user.

        Args:
            user_id: UUID string of the user.

        Returns:
            Most recent OtpCode if any, None otherwise.
        """
        ...

    async def revoke_by_user_id(self, user_id: str) -> int:
        """Revoke all pending OTPs for a user.

        Called when a new OTP is requested (invalidates old ones).

        Args:
            user_id: UUID string of the user.

        Returns:
            Number of revoked OTPs.
        """
        ...
