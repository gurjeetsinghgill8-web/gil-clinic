"""Dependency injection set-up for Identity Engine use cases.

Provides factory functions that instantiate use cases with their
required infrastructure dependencies (repositories, services, UoW).
"""

from __future__ import annotations

from typing import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.identity.use_cases.assign_role_use_case import (
    AssignRoleUseCase,
)
from src.application.identity.use_cases.authenticate_with_password_use_case import (
    AuthenticateWithPasswordUseCase,
)
from src.application.identity.use_cases.authenticate_with_pin_use_case import (
    AuthenticateWithPinUseCase,
)
from src.application.identity.use_cases.change_pin_use_case import ChangePinUseCase
from src.application.identity.use_cases.logout_use_case import LogoutUseCase
from src.application.identity.use_cases.refresh_token_use_case import (
    RefreshTokenUseCase,
)
from src.application.identity.use_cases.request_otp_use_case import RequestOtpUseCase
from src.application.identity.use_cases.unlock_account_use_case import (
    UnlockAccountUseCase,
)
from src.application.identity.use_cases.verify_otp_use_case import VerifyOtpUseCase
from src.infrastructure.identity.services import (
    BcryptPinHasher,
    JwtTokenService,
    OtpGeneratorService,
)
from src.infrastructure.persistence.identity.repositories.user_repository import (
    SqlAlchemyUserRepository,
)
from src.infrastructure.persistence.identity.repositories.session_repository import (
    SqlAlchemySessionRepository,
)
from src.infrastructure.persistence.identity.unit_of_work.factory import (
    IdentityUnitOfWorkFactory,
)

# ------------------------------------------------------------------
# Session / Unit of Work
# ------------------------------------------------------------------

# Global session factory — set during app startup
_session_factory: callable | None = None


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session.

    This should be overridden by the FastAPI app's lifespan.
    """
    if _session_factory is None:
        raise RuntimeError(
            "Database session factory not configured. "
            "Call configure_database() during app startup."
        )
    async with _session_factory() as session:
        yield session


async def get_unit_of_work(
    session: AsyncSession = Depends(get_db_session),
) -> AsyncGenerator:
    """Get a Unit of Work for the identity engine."""
    factory = IdentityUnitOfWorkFactory()
    async with factory.from_session(session) as uow:
        yield uow


# ------------------------------------------------------------------
# Services (singletons)
# ------------------------------------------------------------------

_pin_hasher: BcryptPinHasher | None = None
_token_service: JwtTokenService | None = None
_otp_service: OtpGeneratorService | None = None


def get_pin_hasher() -> BcryptPinHasher:
    global _pin_hasher
    if _pin_hasher is None:
        _pin_hasher = BcryptPinHasher()
    return _pin_hasher


def get_token_service() -> JwtTokenService:
    global _token_service
    if _token_service is None:
        _token_service = JwtTokenService()
    return _token_service


def get_otp_service() -> OtpGeneratorService:
    global _otp_service
    if _otp_service is None:
        _otp_service = OtpGeneratorService()
    return _otp_service


# ------------------------------------------------------------------
# Repositories
# ------------------------------------------------------------------

async def get_user_repository(
    session: AsyncSession = Depends(get_db_session),
) -> SqlAlchemyUserRepository:
    return SqlAlchemyUserRepository(session)


async def get_session_repository(
    session: AsyncSession = Depends(get_db_session),
) -> SqlAlchemySessionRepository:
    return SqlAlchemySessionRepository(session)


# ------------------------------------------------------------------
# Use Case factories
# ------------------------------------------------------------------

async def get_auth_with_pin_use_case(
    uow=Depends(get_unit_of_work),
) -> AuthenticateWithPinUseCase:
    return AuthenticateWithPinUseCase(
        unit_of_work=uow,
        pin_hasher=get_pin_hasher(),
        token_service=get_token_service(),
    )


async def get_auth_with_password_use_case(
    uow=Depends(get_unit_of_work),
) -> AuthenticateWithPasswordUseCase:
    return AuthenticateWithPasswordUseCase(
        unit_of_work=uow,
        pin_hasher=get_pin_hasher(),
        token_service=get_token_service(),
    )


async def get_refresh_token_use_case(
    uow=Depends(get_unit_of_work),
) -> RefreshTokenUseCase:
    return RefreshTokenUseCase(
        unit_of_work=uow,
        token_service=get_token_service(),
    )


async def get_logout_use_case(
    uow=Depends(get_unit_of_work),
) -> LogoutUseCase:
    return LogoutUseCase(unit_of_work=uow)


async def get_change_pin_use_case(
    uow=Depends(get_unit_of_work),
) -> ChangePinUseCase:
    return ChangePinUseCase(
        unit_of_work=uow,
        pin_hasher=get_pin_hasher(),
    )


async def get_request_otp_use_case(
    uow=Depends(get_unit_of_work),
) -> RequestOtpUseCase:
    return RequestOtpUseCase(
        unit_of_work=uow,
        otp_service=get_otp_service(),
    )


async def get_verify_otp_use_case(
    uow=Depends(get_unit_of_work),
) -> VerifyOtpUseCase:
    return VerifyOtpUseCase(
        unit_of_work=uow,
        otp_service=get_otp_service(),
    )


async def get_assign_role_use_case(
    uow=Depends(get_unit_of_work),
) -> AssignRoleUseCase:
    return AssignRoleUseCase(unit_of_work=uow)


async def get_unlock_account_use_case(
    uow=Depends(get_unit_of_work),
) -> UnlockAccountUseCase:
    return UnlockAccountUseCase(unit_of_work=uow)


# ------------------------------------------------------------------
# Configuration hook
# ------------------------------------------------------------------

def configure_database(session_factory: callable) -> None:
    """Configure the database session factory.

    Call this during FastAPI app startup:
        @app.on_event("startup")
        async def startup():
            engine = create_async_engine(settings.DATABASE_URL)
            configure_database(lambda: AsyncSession(engine))
    """
    global _session_factory
    _session_factory = session_factory
