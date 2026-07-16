"""VerifyOtpUseCase — verify a one-time password.

Orchestrates:
1. Load latest OTP for user via OtpRepository
2. Call otp.verify() for expiry/attempts checks
3. Save updated OTP (attempt count incremented)
4. Publish otp_verified event on success
5. Return OtpVerifiedResponse
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.application.common.base_use_case import BaseUseCase
from src.application.common.command import Command
from src.application.common.result import Result
from src.application.common.exceptions import (
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from src.application.identity.dtos.requests import VerifyOtpRequest
from src.application.identity.dtos.responses import OtpVerifiedResponse
from src.domain.identity.events.identity_events import otp_verified

if TYPE_CHECKING:
    from src.domain.identity.ports.otp_repository import OtpRepository
    from src.domain.identity.ports.otp_service import OtpService
    from src.domain.identity.ports.event_publisher import EventPublisher


class VerifyOtpUseCase(BaseUseCase):
    """Use case for verifying an OTP."""

    def __init__(
        self,
        otp_repo: OtpRepository,
        otp_service: OtpService,
        event_publisher: EventPublisher,
    ) -> None:
        super().__init__()
        self._otp_repo = otp_repo
        self._otp_service = otp_service
        self._event_publisher = event_publisher

    async def validate(self, command: Command) -> None:
        """Validate OTP format."""
        dto: VerifyOtpRequest = command.data
        if not dto.user_id:
            raise ValidationError(message="User ID is required.")
        if not dto.otp or not dto.otp.isdigit() or len(dto.otp) != 6:
            raise ValidationError(
                message="OTP must be exactly 6 digits.",
                details={"field": "otp"},
            )

    async def execute(self, command: Command) -> Result:
        """Execute OTP verification."""
        dto: VerifyOtpRequest = command.data

        try:
            # 1. Load latest OTP
            otp_code = await self._otp_repo.get_latest_by_user_id(dto.user_id)
            if not otp_code:
                raise NotFoundError(
                    message="No OTP found. Please request a new one.",
                    details={"user_id": dto.user_id},
                )

            # 2. Verify OTP (handles expiry, max attempts internally)
            try:
                verified = otp_code.verify(dto.otp, self._otp_service)
            except Exception as exc:
                # Save updated attempt count before re-raising
                await self._otp_repo.save(otp_code)
                raise UnauthorizedError(
                    message=str(exc),
                    details={"user_id": dto.user_id},
                ) from exc

            # 3. Save updated OTP (attempt count incremented)
            await self._otp_repo.save(otp_code)

            if verified:
                # 4. Publish event
                self._event_publisher.publish(
                    otp_verified(
                        user_id=dto.user_id,
                        purpose=dto.purpose,
                    )
                )

                return Result.ok(
                    data=OtpVerifiedResponse(
                        verified=True,
                        message="OTP verified successfully",
                    ),
                )

            # 5. Wrong OTP (verify returned False, no exception)
            return Result.fail(
                error="Invalid OTP. Galat OTP.",
                code="IDENTITY_003",
                details={
                    "remaining_attempts": otp_code.remaining_attempts,
                },
            )

        except (NotFoundError, UnauthorizedError) as exc:
            return Result.fail(
                error=str(exc), code=exc.code, details=exc.details
            )
