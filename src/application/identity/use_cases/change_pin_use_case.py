"""ChangePinUseCase — change a user's PIN.

Orchestrates:
1. Validate new PIN format via AuthenticationDomainService
2. Load User aggregate
3. Verify old PIN via PinHasher.verify()
4. Set new PIN hash via User.set_pin()
5. Revoke other sessions via SessionRepository
6. Revoke tokens via RefreshTokenRepository
7. Publish pin_changed event
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
from src.application.identity.dtos.requests import ChangePinRequest
from src.application.identity.dtos.responses import PinChangedResponse
from src.domain.identity.services.authentication_service import (
    AuthenticationDomainService,
)
from src.domain.identity.events.identity_events import pin_changed

if TYPE_CHECKING:
    from src.domain.identity.ports.user_repository import UserRepository
    from src.domain.identity.ports.session_repository import SessionRepository
    from src.domain.identity.ports.refresh_token_repository import (
        RefreshTokenRepository,
    )
    from src.domain.identity.ports.event_publisher import EventPublisher
    from src.domain.identity.ports.pin_hasher import PinHasher


class ChangePinUseCase(BaseUseCase):
    """Use case for changing a user's PIN."""

    def __init__(
        self,
        user_repo: UserRepository,
        session_repo: SessionRepository,
        token_repo: RefreshTokenRepository,
        event_publisher: EventPublisher,
        pin_hasher: PinHasher,
    ) -> None:
        super().__init__()
        self._user_repo = user_repo
        self._session_repo = session_repo
        self._token_repo = token_repo
        self._event_publisher = event_publisher
        self._pin_hasher = pin_hasher
        self._domain_service = AuthenticationDomainService()

    async def validate(self, command: Command) -> None:
        """Validate PIN format."""
        dto: ChangePinRequest = command.data

        if not dto.user_id:
            raise ValidationError(message="User ID is required.")

        valid, error = self._domain_service.validate_pin_format(dto.new_pin)
        if not valid:
            raise ValidationError(
                message=error or "Invalid PIN format",
                details={"field": "new_pin"},
            )

        if dto.old_pin == dto.new_pin:
            raise ValidationError(
                message="New PIN must be different from old PIN.",
                details={"field": "new_pin"},
            )

    async def execute(self, command: Command) -> Result:
        """Execute PIN change."""
        dto: ChangePinRequest = command.data

        try:
            # 1. Load user
            user = await self._user_repo.get_by_id(dto.user_id)
            if not user:
                raise NotFoundError(
                    message="User not found.",
                    details={"user_id": dto.user_id},
                )

            # 2. Verify old PIN (if user has one)
            if user.pin_hash and not self._pin_hasher.verify(
                dto.old_pin, user.pin_hash
            ):
                raise UnauthorizedError(
                    message="Current PIN is wrong. Aapka current PIN galat hai.",
                    details={"reason": "wrong_old_pin"},
                )

            # 3. Set new PIN
            new_hash = self._pin_hasher.hash(dto.new_pin)
            user.set_pin(new_hash)
            await self._user_repo.save(user)

            # 4. Revoke other sessions (security measure)
            sessions_revoked = (
                await self._session_repo.revoke_all_user_sessions(
                    dto.user_id, exclude_session_id=None
                )
            )
            await self._token_repo.revoke_by_user_id(dto.user_id)

            # 5. Publish event
            self._event_publisher.publish(
                pin_changed(user_id=dto.user_id)
            )

            return Result.ok(
                data=PinChangedResponse(
                    message="PIN changed successfully",
                    sessions_revoked=sessions_revoked,
                ),
            )

        except (NotFoundError, UnauthorizedError) as exc:
            return Result.fail(
                error=str(exc), code=exc.code, details=exc.details
            )
