"""LogoutUseCase — session and token revocation.

Orchestrates:
1. Revoke session(s) via SessionRepository
2. Revoke associated refresh tokens via RefreshTokenRepository
3. Publish logout event
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.application.common.base_use_case import BaseUseCase
from src.application.common.command import Command
from src.application.common.result import Result
from src.application.common.exceptions import NotFoundError
from src.application.identity.dtos.requests import LogoutRequest
from src.application.identity.dtos.responses import LogoutResponse
from src.domain.identity.events.identity_events import (
    user_logout,
    session_revoked,
)

if TYPE_CHECKING:
    from src.domain.identity.ports.session_repository import SessionRepository
    from src.domain.identity.ports.refresh_token_repository import (
        RefreshTokenRepository,
    )
    from src.domain.identity.ports.event_publisher import EventPublisher


class LogoutUseCase(BaseUseCase):
    """Use case for user logout."""

    def __init__(
        self,
        session_repo: SessionRepository,
        token_repo: RefreshTokenRepository,
        event_publisher: EventPublisher,
    ) -> None:
        super().__init__()
        self._session_repo = session_repo
        self._token_repo = token_repo
        self._event_publisher = event_publisher

    async def validate(self, command: Command) -> None:
        """Validate input presence."""
        dto: LogoutRequest = command.data
        if not dto.user_id:
            from src.application.common.exceptions import ValidationError
            raise ValidationError(message="User ID is required.")
        if not dto.session_id and not dto.revoke_all:
            from src.application.common.exceptions import ValidationError
            raise ValidationError(
                message="Either session_id or revoke_all=True is required.",
                details={"session_id": dto.session_id, "revoke_all": dto.revoke_all},
            )

    async def execute(self, command: Command) -> Result:
        """Execute logout."""
        dto: LogoutRequest = command.data

        try:
            if dto.revoke_all:
                # Revoke ALL sessions for this user
                count = await self._session_repo.revoke_all_user_sessions(
                    dto.user_id, exclude_session_id=None
                )
                await self._token_repo.revoke_by_user_id(dto.user_id)

                self._event_publisher.publish(
                    session_revoked(
                        user_id=dto.user_id,
                        session_id="ALL",
                        revoked_by="USER",
                    )
                )

                return Result.ok(
                    data=LogoutResponse(
                        message=f"All {count} sessions revoked",
                        sessions_revoked=count,
                    ),
                )
            else:
                # Revoke specific session
                session = await self._session_repo.get_by_id(dto.session_id)
                if not session:
                    raise NotFoundError(
                        message="Session not found.",
                        details={"session_id": dto.session_id},
                    )

                session.revoke()
                await self._session_repo.save(session)
                await self._token_repo.revoke_by_session_id(dto.session_id)

                self._event_publisher.publish(
                    user_logout(
                        user_id=dto.user_id,
                        session_id=dto.session_id,
                    )
                )

                return Result.ok(
                    data=LogoutResponse(message="Logged out successfully"),
                )

        except NotFoundError as exc:
            return Result.fail(
                error=str(exc), code=exc.code, details=exc.details
            )
