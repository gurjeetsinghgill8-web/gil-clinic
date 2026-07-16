"""Transaction manager interface for Unit of Work.

Defines the contract for atomic transaction boundaries across all engines.
Infrastructure provides the actual implementation (SQLAlchemy async session).
"""

from __future__ import annotations

from typing import AsyncIterator, Protocol


class TransactionManager(Protocol):
    """Interface for atomic transaction management.

    Every use case runs inside a transaction:
    1. Use case starts
    2. Aggregates are loaded and modified
    3. Domain events are collected
    4. Transaction commits (all changes + outbox events)
    5. If any step fails → rollback

    Implementation is provided by the infrastructure layer.
    """

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
