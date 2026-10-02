"""Unit of Work interface for the Identity Engine.

Defines the atomic transaction boundary for identity use cases.
Each use case gets its own unit of work that provides:

1. Repository access (UserRepository, SessionRepository, etc.)
2. Event collection (events are published after commit)
3. Commit / Rollback

The UnitOfWork is created by a factory (e.g., SqlAlchemyUnitOfWork)
and injected into each use case.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, AsyncIterator, Protocol

if TYPE_CHECKING:
    from src.domain.identity.ports.user_repository import UserRepository
    from src.domain.identity.ports.session_repository import SessionRepository
    from src.domain.identity.ports.refresh_token_repository import (
        RefreshTokenRepository,
    )
    from src.domain.identity.ports.role_repository import RoleRepository
    from src.domain.identity.ports.otp_repository import OtpRepository
    from src.domain.identity.ports.event_publisher import EventPublisher


class IdentityUnitOfWork(Protocol):
    """Atomic transaction boundary for identity use cases.

    Provides all repository access within a single transaction.
    Events collected during the use case are published after commit.

    Usage:
        async with uow as unit:
            user = await unit.users.get_by_username("admin")
            user.record_successful_login()
            await unit.users.save(user)
            await unit.commit()
    """

    # Repository accessors
    users: UserRepository
    sessions: SessionRepository
    tokens: RefreshTokenRepository
    roles: RoleRepository
    otps: OtpRepository
    events: EventPublisher

    async def commit(self) -> None:
        """Commit the current transaction.

        Persists all aggregate changes and outbox events atomically.
        """
        ...

    async def rollback(self) -> None:
        """Rollback the current transaction.

        Discards all uncommitted changes.
        """
        ...

    async def flush(self) -> None:
        """Flush pending changes without committing.

        Useful for getting generated IDs before commit.
        """
        ...

    async def __aenter__(self) -> IdentityUnitOfWork:
        """Enter async context manager."""
        ...

    async def __aexit__(self, *args) -> None:
        """Exit async context manager (auto-rollback on error)."""
        ...
