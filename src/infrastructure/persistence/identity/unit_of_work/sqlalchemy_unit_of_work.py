"""SQLAlchemy Identity Unit of Work.

Provides atomic transaction boundaries for identity use cases.
All 5 repositories + event publisher are created from a single session.

Usage:
    async with SqlAlchemyIdentityUnitOfWork(session) as uow:
        user = await uow.users.get_by_username("admin")
        user.record_successful_login()
        await uow.users.save(user)
        await uow.commit()
"""

from __future__ import annotations

from typing import Any, AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.persistence.identity.repositories.otp_repository import (
    SqlAlchemyOtpRepository,
)
from src.infrastructure.persistence.identity.repositories.refresh_token_repository import (
    SqlAlchemyRefreshTokenRepository,
)
from src.infrastructure.persistence.identity.repositories.role_repository import (
    SqlAlchemyRoleRepository,
)
from src.infrastructure.persistence.identity.repositories.session_repository import (
    SqlAlchemySessionRepository,
)
from src.infrastructure.persistence.identity.repositories.user_repository import (
    SqlAlchemyUserRepository,
)
from src.infrastructure.persistence.shared.events.outbox_publisher import (
    OutboxEventPublisher,
)


class SqlAlchemyIdentityUnitOfWork:
    """SQLAlchemy implementation of IdentityUnitOfWork.

    Provides:
    - All 5 repository accessors (users, sessions, tokens, roles, otps)
    - Event publisher (OutboxEventPublisher for outbox pattern)
    - Commit / Rollback / Flush
    - Async context manager (auto-rollback on error)
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._committed = False

        # Repositories — all share the same session
        self.users = SqlAlchemyUserRepository(session)
        self.sessions = SqlAlchemySessionRepository(session)
        self.tokens = SqlAlchemyRefreshTokenRepository(session)
        self.roles = SqlAlchemyRoleRepository(session)
        self.otps = SqlAlchemyOtpRepository(session)
        self.events = OutboxEventPublisher(session)

    async def commit(self) -> None:
        """Commit the current transaction.

        Persists all aggregate changes and outbox events atomically.
        """
        await self._session.commit()
        self._committed = True

    async def rollback(self) -> None:
        """Rollback the current transaction.

        Discards all uncommitted changes.
        """
        await self._session.rollback()

    async def flush(self) -> None:
        """Flush pending changes without committing.

        Useful for getting generated IDs before commit.
        """
        await self._session.flush()

    async def __aenter__(self) -> SqlAlchemyIdentityUnitOfWork:
        """Enter async context manager."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit async context manager.

        Auto-commits on success, auto-rollbacks on error.
        """
        if exc_type is not None:
            await self.rollback()
        elif not self._committed:
            await self.commit()
        await self._session.close()
