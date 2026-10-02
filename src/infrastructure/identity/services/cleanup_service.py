"""Database cleanup service for identity engine ephemeral tables.

Prevents unbounded growth of session, refresh token, OTP, and outbox tables.
Should be run as a scheduled background job (Celery beat / cron).

Cleanup schedule recommendation:
- Every 5 minutes: expired OTP codes
- Every 1 hour: expired sessions, expired tokens, published outbox
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.identity.models import (
    OtpCodeModel,
    OutboxModel,
    RefreshTokenModel,
    SessionModel,
)
from src.shared.infrastructure.logging import get_logger

logger = get_logger(__name__)


class CleanupService:
    """Service for cleaning up expired data from identity tables.

    All cleanup operations use DELETE with WHERE clauses on indexed columns
    for efficient execution.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def cleanup_expired_otps(self) -> int:
        """Delete OTP codes that have expired.

        OTPs are valid for 5 minutes. This cleanup removes expired entries.

        Returns:
            Number of rows deleted.
        """
        now = datetime.now(timezone.utc)
        stmt = delete(OtpCodeModel).where(OtpCodeModel.expires_at < now)
        result = await self.session.execute(stmt)
        await self.session.commit()
        count = result.rowcount
        if count > 0:
            logger.info("Cleaned up %d expired OTP codes", count)
        return count

    async def cleanup_expired_sessions(self, retention_days: int = 30) -> int:
        """Delete sessions that expired more than retention_days ago.

        Active (non-expired) sessions are preserved. Only sessions whose
        expires_at is past the retention window are removed.

        Args:
            retention_days: Keep sessions for this many days after expiry.

        Returns:
            Number of rows deleted.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        stmt = delete(SessionModel).where(
            SessionModel.expires_at < cutoff
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        count = result.rowcount
        if count > 0:
            logger.info(
                "Cleaned up %d expired sessions (retention: %d days)",
                count, retention_days,
            )
        return count

    async def cleanup_expired_tokens(self, retention_days: int = 30) -> int:
        """Delete refresh tokens that expired more than retention_days ago.

        Active (non-revoked, non-expired) tokens are preserved. Only tokens
        past the retention window are removed.

        Args:
            retention_days: Keep tokens for this many days after expiry.

        Returns:
            Number of rows deleted.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        stmt = delete(RefreshTokenModel).where(
            RefreshTokenModel.expires_at < cutoff
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        count = result.rowcount
        if count > 0:
            logger.info(
                "Cleaned up %d expired refresh tokens (retention: %d days)",
                count, retention_days,
            )
        return count

    async def cleanup_published_outbox(self, retention_hours: int = 24) -> int:
        """Delete outbox events that have been published.

        Only PUBLISHED events older than retention_hours are removed.
        PENDING or FAILED events are preserved for retry.

        Args:
            retention_hours: Keep published events for this many hours.

        Returns:
            Number of rows deleted.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=retention_hours)
        stmt = delete(OutboxModel).where(
            OutboxModel.status == "PUBLISHED"
        ).where(
            OutboxModel.published_at < cutoff
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        count = result.rowcount
        if count > 0:
            logger.info(
                "Cleaned up %d published outbox events (retention: %d hours)",
                count, retention_hours,
            )
        return count

    async def cleanup_all(self) -> dict[str, int]:
        """Run all cleanup operations in sequence.

        Returns:
            Dict of operation name to rows deleted count.
        """
        results = {
            "otp_codes": await self.cleanup_expired_otps(),
            "sessions": await self.cleanup_expired_sessions(),
            "tokens": await self.cleanup_expired_tokens(),
            "outbox": await self.cleanup_published_outbox(),
        }
        total = sum(results.values())
        logger.info(
            "Cleanup complete: %d total rows removed (%s)",
            total,
            ", ".join(f"{k}={v}" for k, v in results.items()),
        )
        return results

    async def get_stale_counts(self) -> dict[str, int]:
        """Count rows that would be cleaned up (without deleting).

        Useful for monitoring and alerting.

        Returns:
            Dict of table name to stale row count.
        """
        now = datetime.now(timezone.utc)
        results: dict[str, int] = {}

        # Expired OTPs
        stmt = text(
            "SELECT COUNT(*) FROM identity.otp_codes WHERE expires_at < :now"
        )
        result = await self.session.execute(stmt, {"now": now})
        results["otp_codes"] = result.scalar() or 0

        # Expired sessions beyond retention
        cutoff_30d = now - timedelta(days=30)
        stmt = text(
            "SELECT COUNT(*) FROM identity.user_sessions WHERE expires_at < :cutoff"
        )
        result = await self.session.execute(stmt, {"cutoff": cutoff_30d})
        results["sessions"] = result.scalar() or 0

        # Expired tokens beyond retention
        stmt = text(
            "SELECT COUNT(*) FROM identity.refresh_tokens WHERE expires_at < :cutoff"
        )
        result = await self.session.execute(stmt, {"cutoff": cutoff_30d})
        results["tokens"] = result.scalar() or 0

        # Published outbox beyond retention
        cutoff_24h = now - timedelta(hours=24)
        stmt = text(
            "SELECT COUNT(*) FROM identity.outbox WHERE status = 'PUBLISHED' AND published_at < :cutoff"
        )
        result = await self.session.execute(stmt, {"cutoff": cutoff_24h})
        results["outbox"] = result.scalar() or 0

        return results
