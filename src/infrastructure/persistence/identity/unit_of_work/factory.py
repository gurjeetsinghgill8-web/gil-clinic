"""Unit of Work factory for the Identity Engine.

Creates SqlAlchemyIdentityUnitOfWork instances for dependency injection.
Use in FastAPI or other DI frameworks.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.persistence.identity.unit_of_work.sqlalchemy_unit_of_work import (
    SqlAlchemyIdentityUnitOfWork,
)


class IdentityUnitOfWorkFactory:
    """Factory for creating identity Unit of Work instances.

    Usage:
        factory = IdentityUnitOfWorkFactory(get_session)

        async with factory.create() as uow:
            user = await uow.users.get_by_username("admin")
            ...

        # Or with an existing session:
        async with factory.from_session(session) as uow:
            ...
    """

    def __init__(
        self,
        session_factory: callable = None,
    ) -> None:
        """Initialize the factory.

        Args:
            session_factory: Async callable that returns an AsyncSession.
        """
        self._session_factory = session_factory

    @asynccontextmanager
    async def create(self) -> AsyncIterator[SqlAlchemyIdentityUnitOfWork]:
        """Create a new UoW with a fresh session.

        Yields:
            SqlAlchemyIdentityUnitOfWork instance.

        Raises:
            RuntimeError: If no session factory was configured.
        """
        if not self._session_factory:
            raise RuntimeError(
                "IdentityUnitOfWorkFactory: no session_factory configured. "
                "Use from_session() or provide a session_factory."
            )

        session = await anext(self._session_factory())  # type: ignore
        async with SqlAlchemyIdentityUnitOfWork(session) as uow:
            yield uow

    @staticmethod
    @asynccontextmanager
    async def from_session(
        session: AsyncSession,
    ) -> AsyncIterator[SqlAlchemyIdentityUnitOfWork]:
        """Create a UoW from an existing session.

        Args:
            session: An existing AsyncSession instance.

        Yields:
            SqlAlchemyIdentityUnitOfWork instance.
        """
        async with SqlAlchemyIdentityUnitOfWork(session) as uow:
            yield uow
