"""Session repository interface (port).

Defines the contract for persisting and retrieving Session aggregates.
Implemented by SqlAlchemySessionRepository in the infrastructure layer.
"""

from __future__ import annotations

from typing import Protocol

from src.domain.identity.entities.session import Session


class SessionRepository(Protocol):
    """Interface for Session aggregate persistence.

    Sessions are a separate aggregate from User, enabling independent
    session lifecycle management.
    """

    async def save(self, session: Session) -> None:
        """Persist a new or updated session.

        Args:
            session: Session aggregate to save.
        """
        ...

    async def get_by_id(self, session_id: str) -> Session | None:
        """Get a session by its UUID.

        Args:
            session_id: UUID string.

        Returns:
            Session if found, None otherwise.
        """
        ...

    async def list_by_user_id(self, user_id: str) -> list[Session]:
        """List all sessions for a user.

        Args:
            user_id: UUID string of the user.

        Returns:
            List of Session aggregates for this user.
        """
        ...

    async def list_active_by_user_id(self, user_id: str) -> list[Session]:
        """List active (non-revoked, non-expired) sessions for a user.

        Args:
            user_id: UUID string of the user.

        Returns:
            List of active Session aggregates.
        """
        ...

    async def revoke_session(self, session_id: str) -> None:
        """Revoke a specific session.

        Args:
            session_id: UUID string of the session to revoke.
        """
        ...

    async def revoke_all_user_sessions(
        self, user_id: str, exclude_session_id: str | None = None
    ) -> int:
        """Revoke all sessions for a user, optionally excluding one.

        Args:
            user_id: UUID string of the user.
            exclude_session_id: Optional session to leave active.

        Returns:
            Number of revoked sessions.
        """
        ...

    async def count_active_by_user_id(self, user_id: str) -> int:
        """Count active sessions for a user.

        Args:
            user_id: UUID string of the user.

        Returns:
            Number of active sessions.
        """
        ...
