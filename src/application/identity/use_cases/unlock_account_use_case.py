"""UnlockAccountUseCase — unlock a locked user account.

Orchestrates:
1. Load User aggregate
2. Call User.unlock()
3. Save user
4. Publish account_unlocked event
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.application.common.base_use_case import BaseUseCase
from src.application.common.command import Command
from src.application.common.result import Result
from src.application.common.exceptions import NotFoundError
from src.application.identity.dtos.requests import UnlockAccountRequest
from src.application.identity.dtos.responses import AccountUnlockedResponse
from src.domain.identity.events.identity_events import account_unlocked

if TYPE_CHECKING:
    from src.domain.identity.ports.user_repository import UserRepository
    from src.domain.identity.ports.event_publisher import EventPublisher


class UnlockAccountUseCase(BaseUseCase):
    """Use case for unlocking a locked user account."""

    def __init__(
        self,
        user_repo: UserRepository,
        event_publisher: EventPublisher,
    ) -> None:
        super().__init__()
        self._user_repo = user_repo
        self._event_publisher = event_publisher

    async def validate(self, command: Command) -> None:
        """Validate input presence."""
        dto: UnlockAccountRequest = command.data
        if not dto.user_id:
            from src.application.common.exceptions import ValidationError
            raise ValidationError(message="User ID is required.")
        if dto.unlocked_by not in ("admin", "system"):
            from src.application.common.exceptions import ValidationError
            raise ValidationError(
                message="unlocked_by must be 'admin' or 'system'.",
                details={"unlocked_by": dto.unlocked_by},
            )

    async def execute(self, command: Command) -> Result:
        """Execute account unlock."""
        dto: UnlockAccountRequest = command.data

        try:
            user = await self._user_repo.get_by_id(dto.user_id)
            if not user:
                raise NotFoundError(
                    message="User not found.",
                    details={"user_id": dto.user_id},
                )

            user.unlock(unlocked_by=dto.unlocked_by)
            await self._user_repo.save(user)

            self._event_publisher.publish(
                account_unlocked(
                    user_id=dto.user_id,
                    unlocked_by=dto.unlocked_by,
                )
            )

            return Result.ok(
                data=AccountUnlockedResponse(
                    message="Account unlocked successfully",
                    user_id=dto.user_id,
                ),
            )

        except NotFoundError as exc:
            return Result.fail(
                error=str(exc), code=exc.code, details=exc.details
            )
