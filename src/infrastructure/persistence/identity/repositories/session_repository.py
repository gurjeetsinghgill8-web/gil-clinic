"""SQLAlchemy repository for Session aggregate.

Implements session-specific queries: active sessions, sessions by user,
batch expiry revocation. Uses Specification pattern for filtering.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, update

from src.domain.identity.entities.session import Session
from src.infrastructure.identity.models.session_model import SessionModel
from src.infrastructure.persistence.identity.mappers.session_mapper import (
    SessionMapper,
)
from src.infrastructure.persistence.identity.repositories.base_repository import (
    BaseRepository,
)
from src.infrastructure.persistence.identity.specifications.base_specification import (
    Specification,
)
from src.infrastructure.persistence.identity.specifications.session_specifications import (
    ActiveSessionsSpecification,
    ByUserSpecification,
    ExpiredSessionsSpecification,
    RevokedSessionsSpecification,
    TrustedDeviceSpecification,
)
from src.infrastructure.persistence.identity.specifications.user_specifications import (
    NotDeletedSpecification,
)


class SqlAlchemySessionRepository(BaseRepository[Session, SessionModel]):
    """Repository for Session aggregate with OCC and Specification support."""

    def __init__(self, session) -> None:
        super().__init__(session)
        self._mapper = SessionMapper()

    @property
    def _model_class(self) -> type[SessionModel]:
        return SessionModel

    def _to_domain(self, model: SessionModel) -> Session:
        return self._mapper.to_domain(model)

    def _apply_to_model(self, model: SessionModel, entity: Session) -> None:
        self._mapper.apply_to_model(model, entity)

    # ------------------------------------------------------------------
    # Session-specific queries
    # ------------------------------------------------------------------

    async def list_active_by_user_id(self, user_id: str) -> list[Session]:
        """Get all active sessions for a user.

        Args:
            user_id: UUID of the user.

        Returns:
            List of active Session domain entities.
        """
        spec = (
            ByUserSpecification(user_id)
            & ActiveSessionsSpecification()
            & NotDeletedSpecification()
        )
        return await self.find(spec)

    async def list_by_user_id(self, user_id: str) -> list[Session]:
        """Get ALL sessions (active + expired + revoked) for a user.

        Args:
            user_id: UUID of the user.

        Returns:
            List of all Session domain entities for the user.
        """
        spec = ByUserSpecification(user_id) & NotDeletedSpecification()
        return await self.find(spec)

    async def get_trusted_by_user(self, user_id: str) -> list[Session]:
        """Get trusted active sessions for a user.

        Useful for MFA bypass logic.

        Args:
            user_id: UUID of the user.

        Returns:
            List of trusted active Session domain entities.
        """
        spec = (
            ByUserSpecification(user_id)
            & ActiveSessionsSpecification()
            & TrustedDeviceSpecification()
            & NotDeletedSpecification()
        )
        return await self.find(spec)

    async def count_active_by_user_id(self, user_id: str) -> int:
        """Count active sessions for a user.

        Args:
            user_id: UUID of the user.

        Returns:
            Count of active sessions.
        """
        spec = (
            ByUserSpecification(user_id)
            & ActiveSessionsSpecification()
            & NotDeletedSpecification()
        )
        return await self.count(spec)

    # ------------------------------------------------------------------
    # Batch operations
    # ------------------------------------------------------------------

    async def revoke_session(self, session_id: str) -> None:
        """Revoke a specific session.

        Args:
            session_id: UUID string of the session to revoke.
        """
        session = await self.get_by_id(session_id)
        if session:
            session.revoke("Manually revoked")
            await self.save(session)

    async def revoke_all_user_sessions(
        self,
        user_id: str,
        exclude_session_id: str | None = None,
    ) -> int:
        """Revoke ALL active sessions for a user.

        Uses a bulk UPDATE query (no OCC per row).

        Args:
            user_id: UUID of the user.
            exclude_session_id: Optional session to leave active.

        Returns:
            Number of sessions revoked.
        """
        now = datetime.now(timezone.utc)
        conditions = [
            SessionModel.user_id == user_id,
            SessionModel.revoked_at.is_(None),
            SessionModel.is_deleted == False,  # noqa: E712
        ]
        if exclude_session_id:
            conditions.append(SessionModel.id != exclude_session_id)

        stmt = (
            update(SessionModel)
            .where(*conditions)
            .values(
                revoked_at=now,
                updated_at=now,
            )
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount

    async def revoke_all_expired(self) -> int:
        """Revoke all expired sessions in bulk.

        Called by the cleanup job. Marks revoked_at on all expired sessions
        that haven't been revoked yet.

        Returns:
            Number of sessions revoked.
        """
        now = datetime.now(timezone.utc)
        stmt = (
            update(SessionModel)
            .where(
                SessionModel.expires_at <= now,
                SessionModel.revoked_at.is_(None),
                SessionModel.is_deleted == False,  # noqa: E712
            )
            .values(
                revoked_at=now,
                updated_at=now,
            )
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount

    async def cleanup_old_sessions(self, days: int = 90) -> int:
        """Hard-delete sessions older than specified days.

        Args:
            days: Age threshold in days (default 90).

        Returns:
            Number of hard-deleted sessions.
        """
        from sqlalchemy import delete

        cutoff = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        from datetime import timedelta

        cutoff = cutoff - timedelta(days=days)

        stmt = delete(SessionModel).where(
            SessionModel.created_at < cutoff,
            SessionModel.is_deleted == True,  # noqa: E712
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount
