"""SQLAlchemy repository for RefreshToken aggregate.

Supports token rotation, theft detection, and batch revocation.
Uses Specification pattern for filtering.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, update

from src.domain.identity.entities.refresh_token import RefreshToken
from src.infrastructure.identity.models.refresh_token_model import (
    RefreshTokenModel,
)
from src.infrastructure.persistence.identity.mappers.refresh_token_mapper import (
    RefreshTokenMapper,
)
from src.infrastructure.persistence.identity.repositories.base_repository import (
    BaseRepository,
)
from src.infrastructure.persistence.identity.specifications.base_specification import (
    Specification,
)


class SqlAlchemyRefreshTokenRepository(
    BaseRepository[RefreshToken, RefreshTokenModel]
):
    """Repository for RefreshToken aggregate with OCC and Specification support."""

    def __init__(self, session) -> None:
        super().__init__(session)
        self._mapper = RefreshTokenMapper()

    @property
    def _model_class(self) -> type[RefreshTokenModel]:
        return RefreshTokenModel

    def _to_domain(self, model: RefreshTokenModel) -> RefreshToken:
        return self._mapper.to_domain(model)

    def _apply_to_model(self, model: RefreshTokenModel, entity: RefreshToken) -> None:
        self._mapper.apply_to_model(model, entity)

    # ------------------------------------------------------------------
    # Token-specific queries
    # ------------------------------------------------------------------

    async def get_by_token_hash(self, token_hash: str) -> RefreshToken | None:
        """Get a refresh token by its SHA-256 hash.

        Args:
            token_hash: SHA-256 hash of the raw refresh token.

        Returns:
            RefreshToken domain entity if found, None otherwise.
        """
        query = select(RefreshTokenModel).where(
            RefreshTokenModel.token_hash == token_hash,
            RefreshTokenModel.is_deleted == False,  # noqa: E712
        )
        result = await self.session.execute(query)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def list_active_by_user_id(self, user_id: str) -> list[RefreshToken]:
        """List all active (non-revoked, non-expired) tokens for a user.

        Args:
            user_id: UUID of the user.

        Returns:
            List of active RefreshToken domain entities.
        """
        stmt = select(RefreshTokenModel).where(
            RefreshTokenModel.user_id == user_id,
            RefreshTokenModel.is_revoked == False,  # noqa: E712
            RefreshTokenModel.is_deleted == False,  # noqa: E712
            RefreshTokenModel.expires_at > datetime.now(timezone.utc),
        )
        result = await self.session.execute(stmt)
        models = list(result.scalars().unique().all())
        return [self._to_domain(m) for m in models]

    async def list_all_by_user(self, user_id: str) -> list[RefreshToken]:
        """List ALL tokens (active + revoked + expired) for a user.

        Args:
            user_id: UUID of the user.

        Returns:
            List of all RefreshToken domain entities for the user.
        """
        query = select(RefreshTokenModel).where(
            RefreshTokenModel.user_id == user_id,
            RefreshTokenModel.is_deleted == False,  # noqa: E712
        )
        result = await self.session.execute(query)
        models = list(result.scalars().unique().all())
        return [self._to_domain(m) for m in models]

    # ------------------------------------------------------------------
    # Batch operations
    # ------------------------------------------------------------------

    async def revoke_by_user_id(self, user_id: str) -> int:
        """Revoke ALL active tokens for a user.

        Used when token theft is detected or account is locked.
        Uses a single UPDATE query (bulk operation — no OCC per row).

        Args:
            user_id: UUID of the user.

        Returns:
            Number of tokens revoked.
        """
        now = datetime.now(timezone.utc)
        stmt = (
            update(RefreshTokenModel)
            .where(
                RefreshTokenModel.user_id == user_id,
                RefreshTokenModel.is_revoked == False,  # noqa: E712
                RefreshTokenModel.is_deleted == False,  # noqa: E712
            )
            .values(
                is_revoked=True,
                revoked_at=now,
            )
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount

    async def revoke_by_session_id(self, session_id: str) -> int:
        """Revoke all tokens associated with a specific session.

        Args:
            session_id: UUID of the session.

        Returns:
            Number of tokens revoked.
        """
        now = datetime.now(timezone.utc)
        stmt = (
            update(RefreshTokenModel)
            .where(
                RefreshTokenModel.session_id == session_id,
                RefreshTokenModel.is_revoked == False,  # noqa: E712
                RefreshTokenModel.is_deleted == False,  # noqa: E712
            )
            .values(
                is_revoked=True,
                revoked_at=now,
            )
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount

    async def cleanup_expired_tokens(self, days: int = 90) -> int:
        """Hard-delete expired tokens older than specified days.

        Args:
            days: Age threshold in days (default 90).

        Returns:
            Number of hard-deleted tokens.
        """
        from sqlalchemy import delete
        from datetime import timedelta

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        stmt = delete(RefreshTokenModel).where(
            RefreshTokenModel.expires_at < cutoff,
            RefreshTokenModel.is_deleted == True,  # noqa: E712
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount
