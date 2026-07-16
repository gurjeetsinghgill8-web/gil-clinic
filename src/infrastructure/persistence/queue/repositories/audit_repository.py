"""SqlAlchemyAuditRepository — persists and reads audit log entries.

Now supports read/query operations for the Manager Dashboard.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.queue.models.audit_log_model import AuditLogModel
from src.shared.domain.base_entity import uuid7


class SqlAlchemyAuditRepository:
    """Audit repository backed by SQLAlchemy.

    Supports append-only writes and read/query operations.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(
        self,
        actor: str,
        action: str,
        resource_type: str = "queue_entry",
        resource_id: str = "",
        old_status: str | None = None,
        new_status: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Write a single audit log entry."""
        entry = AuditLogModel(
            id=uuid7(),
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else "",
            old_status=old_status,
            new_status=new_status,
            details=details or {},
            created_at=datetime.now(timezone.utc),
        )
        self._session.add(entry)

    async def save_many(
        self,
        entries: list[dict[str, Any]],
    ) -> None:
        """Bulk write audit log entries.

        Each entry dict must have at minimum 'actor' and 'action'.
        Optional: resource_type, resource_id, old_status, new_status, details.
        """
        models = []
        now = datetime.now(timezone.utc)
        for e in entries:
            models.append(
                AuditLogModel(
                    id=uuid7(),
                    actor=e.get("actor", "system"),
                    action=e.get("action", "UNKNOWN"),
                    resource_type=e.get("resource_type", "queue_entry"),
                    resource_id=str(e.get("resource_id", "")),
                    old_status=e.get("old_status"),
                    new_status=e.get("new_status"),
                    details=e.get("details", {}),
                    created_at=now,
                )
            )
        self._session.add_all(models)

    # ------------------------------------------------------------------
    # Read / Query operations (for Manager Dashboard)
    # ------------------------------------------------------------------

    async def query(
        self,
        actor: str | None = None,
        action: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Query audit log entries with optional filters.

        Args:
            actor: Filter by actor name.
            action: Filter by action type (e.g. 'QUEUE_CALLED').
            date_from: Start of date range (inclusive).
            date_to: End of date range (inclusive).
            limit: Maximum records to return (default 50).

        Returns:
            List of audit entry dicts sorted by created_at DESC.
        """
        conditions = []
        if actor:
            conditions.append(AuditLogModel.actor == actor)
        if action:
            conditions.append(AuditLogModel.action == action)
        if date_from:
            conditions.append(AuditLogModel.created_at >= date_from)
        if date_to:
            conditions.append(AuditLogModel.created_at <= date_to)

        stmt = (
            select(AuditLogModel)
            .where(and_(*conditions) if conditions else True)
            .order_by(desc(AuditLogModel.created_at))
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [
            {
                "id": str(m.id),
                "actor": m.actor,
                "action": m.action,
                "resource_type": m.resource_type,
                "resource_id": m.resource_id,
                "old_status": m.old_status,
                "new_status": m.new_status,
                "details": m.details or {},
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in models
        ]

    async def count_by_action(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Count audit entries grouped by action type.

        Args:
            date_from: Start of date range (inclusive).
            date_to: End of date range (inclusive).

        Returns:
            List of dicts: action, count sorted by count DESC.
        """
        conditions = []
        if date_from:
            conditions.append(AuditLogModel.created_at >= date_from)
        if date_to:
            conditions.append(AuditLogModel.created_at <= date_to)

        stmt = (
            select(
                AuditLogModel.action,
                func.count(AuditLogModel.id).label("count"),
            )
            .where(and_(*conditions) if conditions else True)
            .group_by(AuditLogModel.action)
            .order_by(desc("count"))
        )
        result = await self._session.execute(stmt)
        rows = result.all()
        return [
            {"action": row.action, "count": row.count}
            for row in rows
        ]
