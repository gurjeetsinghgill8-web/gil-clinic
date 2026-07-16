"""AuthenticateWithPinUseCase — PIN-based staff login.

Orchestrates:
1. Validate input (PIN format, username)
2. Load User aggregate from UserRepository
3. Call User.can_authenticate() for lockout/active checks
4. Call PinHasher.verify() for PIN verification
5. Call User.record_failed_attempt() or record_successful_login()
6. Create Session via Session.create()
7. Create RefreshToken via RefreshToken.create()
8. Create JWT via TokenService.create_access_token()
9. Publish domain events (login, lockout, failed attempt)
10. Commit via UnitOfWork
11. Return AuthenticateResponse

Dependencies:
- UserRepository, SessionRepository, RefreshTokenRepository
- PinHasher, TokenService, EventPublisher
- LockoutPolicy, SessionPolicy
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
    ForbiddenError,
)
from src.application.identity.dtos.requests import AuthenticateWithPinRequest
from src.application.identity.dtos.responses import AuthenticateResponse
from src.domain.identity.entities.session import Session
from src.domain.identity.entities.refresh_token import RefreshToken
from src.domain.identity.entities.user import User
from src.domain.identity.value_objects.device_info import DeviceInfo
from src.domain.identity.policies.lockout_policy import LockoutPolicy
from src.domain.identity.policies.session_policy import SessionPolicy
from src.domain.identity.services.authentication_service import (
    AuthenticationDomainService,
)
from src.domain.identity.events.identity_events import (
    user_login,
    login_failed,
    account_locked,
)

if TYPE_CHECKING:
    from src.domain.identity.ports.user_repository import UserRepository
    from src.domain.identity.ports.session_repository import SessionRepository
    from src.domain.identity.ports.refresh_token_repository import (
        RefreshTokenRepository,
    )
    from src.domain.identity.ports.event_publisher import EventPublisher
    from src.domain.identity.ports.pin_hasher import PinHasher
    from src.domain.identity.ports.token_service import TokenService


class AuthenticateWithPinUseCase(BaseUseCase):
    """Use case for PIN-based staff authentication."""

    def __init__(
        self,
        user_repo: UserRepository,
        session_repo: SessionRepository,
        token_repo: RefreshTokenRepository,
        event_publisher: EventPublisher,
        pin_hasher: PinHasher,
        token_service: TokenService,
    ) -> None:
        super().__init__()
        self._user_repo = user_repo
        self._session_repo = session_repo
        self._token_repo = token_repo
        self._event_publisher = event_publisher
        self._pin_hasher = pin_hasher
        self._token_service = token_service
        self._lockout_policy = LockoutPolicy()
        self._session_policy = SessionPolicy()
        self._domain_service = AuthenticationDomainService()

    async def authorize(self, command: Command) -> None:
        """PIN login is a public endpoint — no authorization needed."""
        pass

    async def validate(self, command: Command) -> None:
        """Validate PIN format and username presence."""
        dto: AuthenticateWithPinRequest = command.data

        if not dto.username or not dto.username.strip():
            raise ValidationError(
                message="Username is required.",
                details={"field": "username"},
            )

        valid, error = self._domain_service.validate_pin_format(dto.pin)
        if not valid:
            raise ValidationError(
                message=error or "Invalid PIN format",
                details={"field": "pin"},
            )

    async def execute(self, command: Command) -> Result:
        """Execute PIN authentication flow.

        Args:
            command: Command with AuthenticateWithPinRequest as data.

        Returns:
            Result with AuthenticateResponse or error.
        """
        dto: AuthenticateWithPinRequest = command.data

        try:
            # 1. Load user
            user = await self._user_repo.get_by_username(dto.username)
            if not user or not user.is_active:
                raise NotFoundError(
                    message="User not found or deactivated.",
                    details={"username": dto.username},
                )

            # 2. Check lockout
            try:
                user.can_authenticate()
            except Exception as exc:
                raise UnauthorizedError(
                    message=str(exc),
                    details={"username": dto.username},
                ) from exc

            # 3. Build device info
            device_info = (
                DeviceInfo.from_request(
                    device_id=dto.device_id,
                    device_name=dto.device_name,
                    user_agent=dto.user_agent,
                    ip_address=dto.ip_address,
                )
                if any([dto.device_id, dto.user_agent])
                else None
            )

            # 4. Verify PIN
            if not user.pin_hash or not self._pin_hasher.verify(
                dto.pin, user.pin_hash
            ):
                return await self._handle_pin_failure(user, dto.username)

            # 5. Successful login
            user.record_successful_login()
            await self._user_repo.save(user)

            # 6. Check session limit
            active_sessions = (
                await self._session_repo.count_active_by_user_id(str(user.id))
            )
            can_create, limit_msg = self._session_policy.can_create_session(
                active_sessions
            )
            if not can_create:
                raise ForbiddenError(
                    message=limit_msg or "Session limit reached",
                    details={"active_sessions": active_sessions},
                )

            # 7. Create session
            session = Session.create(
                user_id=user.id,
                device_info=device_info,
            )
            await self._session_repo.save(session)

            # 8. Create refresh token
            raw_refresh = self._token_service.hash_token(
                f"{user.id}:{session.id}:{session.created_at.isoformat()}"
            )
            refresh_token = RefreshToken.create(
                user_id=user.id,
                token_hash=self._token_service.hash_token(raw_refresh),
                session_id=session.id,
                device_id=device_info.device_id if device_info else None,
            )
            await self._token_repo.save(refresh_token)

            # 9. Generate access token
            access_token = self._token_service.create_access_token(
                user_id=str(user.id),
                role=user.role_code,
                session_id=str(session.id),
            )

            # 10. Publish event
            self._event_publisher.publish(
                user_login(
                    user_id=str(user.id),
                    session_id=str(session.id),
                    device_id=device_info.device_id if device_info else None,
                    ip_address=device_info.ip_address if device_info else None,
                )
            )

            return Result.ok(
                data=AuthenticateResponse(
                    access_token=access_token,
                    refresh_token=raw_refresh,
                    session_id=str(session.id),
                    user_id=str(user.id),
                    username=user.username,
                    role=user.role_code,
                ),
                message="Authentication successful",
            )

        except (NotFoundError, UnauthorizedError, ForbiddenError) as exc:
            return Result.fail(
                error=str(exc),
                code=exc.code,
                details=exc.details,
            )

    async def _handle_pin_failure(
        self, user: User, username: str
    ) -> Result:
        """Handle a failed PIN verification.

        Args:
            user: The user aggregate.
            username: Username for error reporting.

        Returns:
            Result with failure error.
        """
        result = user.record_failed_attempt()
        await self._user_repo.save(user)

        # Publish failure event
        self._event_publisher.publish(
            login_failed(
                user_id=str(user.id),
                method="pin",
                attempt_count=user.login_attempts,
            )
        )

        # Publish lockout event if just locked
        if result and result.locked:
            self._event_publisher.publish(
                account_locked(
                    user_id=str(user.id),
                    locked_until=result.locked_until.isoformat()
                    if result.locked_until
                    else "",
                )
            )

        return Result.fail(
            error="Invalid credentials. Galat PIN/password.",
            code="IDENTITY_003",
            details={
                "remaining_attempts": user.remaining_attempts,
            },
        )
