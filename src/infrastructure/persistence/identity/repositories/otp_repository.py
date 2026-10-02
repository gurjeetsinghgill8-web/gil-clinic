"""SQLAlchemy repository for OtpCode (value object / ephemeral entity).

OTPs are ephemeral — they expire in minutes. Includes bulk cleanup
for expired OTPs and per-user invalidation.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, update

from src.domain.identity.value_objects.otp_code import OtpCode
from src.infrastructure.identity.models.otp_code_model import OtpCodeModel
from src.infrastructure.persistence.identity.mappers.otp_mapper import (
    OtpMapper,
)
from src.infrastructure.persistence.identity.repositories.base_repository import (
    BaseRepository,
)
from src.infrastructure.persistence.identity.specifications.base_specification import (
    Specification,
)
from src.infrastructure.persistence.identity.specifications.user_specifications import (
    NotDeletedSpecification,
)


class SqlAlchemyOtpRepository(BaseRepository[OtpCode, OtpCodeModel]):
    """Repository for OtpCode with OCC and Specification support."""

    def __init__(self, session) -> None:
        super().__init__(session)
        self._mapper = OtpMapper()

    @property
    def _model_class(self) -> type[OtpCodeModel]:
        return OtpCodeModel

    def _to_domain(self, model: OtpCodeModel) -> OtpCode:
        return self._mapper.to_domain(model)

    def _apply_to_model(self, model: OtpCodeModel, entity: OtpCode) -> None:
        self._mapper.apply_to_model(model, entity)

    # ------------------------------------------------------------------
    # OTP-specific queries
    # ------------------------------------------------------------------

    async def get_latest_by_user_id(self, user_id: str) -> OtpCode | None:
        """Get the most recent OTP for a user.

        Used during OTP verification — loads the latest OTP to verify against.

        Args:
            user_id: UUID of the user.

        Returns:
            Most recent OtpCode, or None if no OTP exists.
        """
        query = (
            select(OtpCodeModel)
            .where(
                OtpCodeModel.user_id == user_id,
                OtpCodeModel.is_deleted == False,  # noqa: E712
            )
            .order_by(OtpCodeModel.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(query)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def list_by_user(self, user_id: str) -> list[OtpCode]:
        """List all OTPs ever created for a user (ordered newest first).

        Args:
            user_id: UUID of the user.

        Returns:
            List of OtpCode domain entities.
        """
        query = (
            select(OtpCodeModel)
            .where(
                OtpCodeModel.user_id == user_id,
                OtpCodeModel.is_deleted == False,  # noqa: E712
            )
            .order_by(OtpCodeModel.created_at.desc())
        )
        result = await self.session.execute(query)
        models = list(result.scalars().unique().all())
        return [self._to_domain(m) for m in models]

    async def count_recent_by_user(
        self, user_id: str, within_minutes: int = 10
    ) -> int:
        """Count OTPs created for a user within a time window.

        Used for rate limiting (e.g., max 3 OTPs per 10 minutes).

        Args:
            user_id: UUID of the user.
            within_minutes: Time window in minutes (default 10).

        Returns:
            Count of OTPs in the time window.
        """
        from datetime import timedelta

        cutoff = datetime.now(timezone.utc) - timedelta(minutes=within_minutes)
        query = select(OtpCodeModel).where(
            OtpCodeModel.user_id == user_id,
            OtpCodeModel.created_at >= cutoff,
            OtpCodeModel.is_deleted == False,  # noqa: E712
        )
        result = await self.session.execute(query)
        models = list(result.scalars().all())
        return len(models)

    # ------------------------------------------------------------------
    # Batch operations
    # ------------------------------------------------------------------

    async def revoke_by_user_id(self, user_id: str) -> int:
        """Soft-delete all active OTPs for a user.

        Used when a new OTP is requested — invalidates previous OTPs.

        Args:
            user_id: UUID of the user.

        Returns:
            Number of OTPs invalidated.
        """
        now = datetime.now(timezone.utc)
        stmt = (
            update(OtpCodeModel)
            .where(
                OtpCodeModel.user_id == user_id,
                OtpCodeModel.is_deleted == False,  # noqa: E712
            )
            .values(
                is_deleted=True,
                deleted_at=now,
            )
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount

    async def cleanup_expired(self) -> int:
        """Hard-delete all expired OTPs.

        Called by the cleanup job to purge expired OTP codes.

        Returns:
            Number of deleted OTPs.
        """
        from sqlalchemy import delete

        now = datetime.now(timezone.utc)
        stmt = delete(OtpCodeModel).where(
            OtpCodeModel.expires_at <= now
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount
