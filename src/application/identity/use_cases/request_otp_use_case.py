"""RequestOtpUseCase — request a one-time password.

Orchestrates:
1. Load User aggregate
2. Invalidate existing OTPs
3. Generate new OTP via OtpService
4. Store OTP hash via OtpRepository
5. Publish otp_sent event
6. Return OTP (in dev; production sends via SMS/email)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.application.common.base_use_case import BaseUseCase
from src.application.common.command import Command
from src.application.common.result import Result
from src.application.common.exceptions import NotFoundError, ValidationError
from src.application.identity.dtos.requests import RequestOtpRequest
from src.application.identity.dtos.responses import OtpResponse
from src.domain.identity.value_objects.otp_code import OtpCode
from src.domain.identity.events.identity_events import otp_sent

if TYPE_CHECKING:
    from src.domain.identity.ports.user_repository import UserRepository
    from src.domain.identity.ports.otp_repository import OtpRepository
    from src.domain.identity.ports.otp_service import OtpService
    from src.domain.identity.ports.event_publisher import EventPublisher


class RequestOtpUseCase(BaseUseCase):
    """Use case for requesting an OTP."""

    def __init__(
        self,
        user_repo: UserRepository,
        otp_repo: OtpRepository,
        otp_service: OtpService,
        event_publisher: EventPublisher,
    ) -> None:
        super().__init__()
        self._user_repo = user_repo
        self._otp_repo = otp_repo
        self._otp_service = otp_service
        self._event_publisher = event_publisher

    async def validate(self, command: Command) -> None:
        """Validate input."""
        dto: RequestOtpRequest = command.data
        if not dto.user_id:
            raise ValidationError(message="User ID is required.")
        if dto.purpose not in ("login", "pin_reset", "mfa"):
            raise ValidationError(
                message="Purpose must be 'login', 'pin_reset', or 'mfa'.",
                details={"purpose": dto.purpose},
            )

    async def execute(self, command: Command) -> Result:
        """Execute OTP request."""
        dto: RequestOtpRequest = command.data

        try:
            # 1. Verify user exists and is active
            user = await self._user_repo.get_by_id(dto.user_id)
            if not user or not user.is_active:
                raise NotFoundError(
                    message="User not found or deactivated.",
                    details={"user_id": dto.user_id},
                )

            # 2. Invalidate any existing OTPs for this user
            await self._otp_repo.revoke_by_user_id(dto.user_id)

            # 3. Generate new OTP
            otp = self._otp_service.generate()
            code_hash = self._otp_service.hash_otp(otp)

            # 4. Store OTP
            otp_code = OtpCode.create(
                user_id=user.id,
                code_hash=code_hash,
            )
            await self._otp_repo.save(otp_code)

            # 5. Publish event
            self._event_publisher.publish(
                otp_sent(
                    user_id=dto.user_id,
                    purpose=dto.purpose,
                )
            )

            # Return OTP (dev only; production sends via SMS/email)
            return Result.ok(
                data=OtpResponse(
                    message=f"OTP sent for {dto.purpose}",
                    otp=otp,  # Remove in production
                ),
            )

        except NotFoundError as exc:
            return Result.fail(
                error=str(exc), code=exc.code, details=exc.details
            )
