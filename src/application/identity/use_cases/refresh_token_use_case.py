"""RefreshTokenUseCase — token rotation with theft detection.

Orchestrates:
1. Find existing token by hash via RefreshTokenRepository
2. Check token.detect_reuse() — if revoked, signal theft
3. Check token.is_active — if expired, reject
4. Load User to verify active
5. Call token.rotate(new_hash) — revokes old, creates new
6. Save both old (revoked) and new (active) tokens
7. Generate new JWT via TokenService
8. Publish events (token_refreshed, security_alert on theft)
9. Return TokenRefreshResponse
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.application.common.base_use_case import BaseUseCase
from src.application.common.command import Command
from src.application.common.result import Result
from src.application.common.exceptions import (
    NotFoundError,
    UnauthorizedError,
    ForbiddenError,
)
from src.application.identity.dtos.requests import RefreshTokenRequest
from src.application.identity.dtos.responses import TokenRefreshResponse
from src.domain.identity.events.identity_events import (
    token_refreshed,
    security_alert,
)

if TYPE_CHECKING:
    from src.domain.identity.ports.user_repository import UserRepository
    from src.domain.identity.ports.refresh_token_repository import (
        RefreshTokenRepository,
    )
    from src.domain.identity.ports.session_repository import SessionRepository
    from src.domain.identity.ports.event_publisher import EventPublisher
    from src.domain.identity.ports.token_service import TokenService


class RefreshTokenUseCase(BaseUseCase):
    """Use case for refresh token rotation."""

    def __init__(
        self,
        user_repo: UserRepository,
        token_repo: RefreshTokenRepository,
        session_repo: SessionRepository,
        event_publisher: EventPublisher,
        token_service: TokenService,
    ) -> None:
        super().__init__()
        self._user_repo = user_repo
        self._token_repo = token_repo
        self._session_repo = session_repo
        self._event_publisher = event_publisher
        self._token_service = token_service

    async def validate(self, command: Command) -> None:
        """Validate input presence."""
        dto: RefreshTokenRequest = command.data
        if not dto.user_id:
            raise UnauthorizedError(message="User ID is required.")
        if not dto.refresh_token_hash:
            raise UnauthorizedError(message="Refresh token is required.")

    async def execute(self, command: Command) -> Result:
        """Execute token rotation."""
        dto: RefreshTokenRequest = command.data

        try:
            # 1. Find existing token
            token = await self._token_repo.get_by_token_hash(
                dto.refresh_token_hash
            )
            if not token:
                raise UnauthorizedError(
                    message="Refresh token not found.",
                    details={"reason": "token_not_found"},
                )

            # 2. Theft detection
            if token.detect_reuse():
                # Revoke ALL tokens and sessions — token theft
                await self._token_repo.revoke_by_user_id(dto.user_id)
                await self._session_repo.revoke_all_user_sessions(dto.user_id)

                self._event_publisher.publish(
                    security_alert(
                        user_id=dto.user_id,
                        alert_type="TOKEN_THEFT",
                        details={
                            "token_id": str(token.id),
                            "action": "all_tokens_and_sessions_revoked",
                        },
                    )
                )

                raise ForbiddenError(
                    message="Token reuse detected. All sessions revoked. "
                    "Please login again.",
                    details={"reason": "token_reuse_theft_detected"},
                )

            # 3. Check token active
            if not token.is_active:
                raise UnauthorizedError(
                    message="Refresh token expired or revoked.",
                    details={"reason": "token_inactive"},
                )

            # 4. Verify user is active
            user = await self._user_repo.get_by_id(dto.user_id)
            if not user or not user.is_active:
                raise NotFoundError(
                    message="User account is inactive or not found.",
                    details={"user_id": dto.user_id},
                )

            # 5. Rotate the token
            new_raw = self._token_service.hash_token(
                f"{dto.user_id}:{token.session_id}:{token.created_at.isoformat()}"
            )
            new_token = token.rotate(
                self._token_service.hash_token(new_raw)
            )

            # Save both the revoked old token and the new token
            await self._token_repo.save(token)  # revoked old
            await self._token_repo.save(new_token)  # new active

            # 6. Generate new JWT
            access_token = self._token_service.create_access_token(
                user_id=str(user.id),
                role=user.role_code,
                session_id=str(token.session_id) if token.session_id else "",
            )

            # 7. Publish event
            self._event_publisher.publish(
                token_refreshed(
                    user_id=dto.user_id,
                    old_token_id=str(token.id),
                    new_token_id=str(new_token.id),
                )
            )

            return Result.ok(
                data=TokenRefreshResponse(
                    access_token=access_token,
                    refresh_token=new_raw,
                ),
                message="Token refreshed successfully",
            )

        except (NotFoundError, UnauthorizedError, ForbiddenError) as exc:
            return Result.fail(
                error=str(exc),
                code=exc.code,
                details=exc.details,
            )
