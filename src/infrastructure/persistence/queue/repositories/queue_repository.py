"""SqlAlchemyQueueRepository — implements QueueRepository protocol.

All methods are async and use AsyncSession for async-compatible operations.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import and_, asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.queue.entities.queue_entry import QueueEntry
from src.domain.queue.value_objects.queue_status import QueueStatus
from src.domain.queue.ports.queue_repository import QueueRepository
from src.infrastructure.persistence.queue.mappers.queue_mapper import QueueEntryMapper
from src.infrastructure.queue.models.queue_entry_model import QueueEntryModel


class SqlAlchemyQueueRepository(QueueRepository):
    """SQLAlchemy-backed implementation of QueueRepository.

    Uses an AsyncSession for async-compatible operations.
    """

    def __init__(self, session: AsyncSession):
        self._session = session
        self._mapper = QueueEntryMapper()

    def _to_uuid(self, val: str | uuid.UUID) -> uuid.UUID:
        """Convert a string or UUID to a UUID object."""
        return uuid.UUID(val) if isinstance(val, str) else val

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    async def save(self, entry: QueueEntry) -> None:
        """Insert or update a queue entry (OCC via version check)."""
        model = await self._session.get(QueueEntryModel, entry.id)
        if model is None:
            model = self._mapper.to_model(entry)
            self._session.add(model)
        else:
            # OCC: model version should be one less than entity version
            # (entity version was incremented by touch() during transition)
            if model.version != entry.version - 1:
                raise ValueError(
                    f"Optimistic lock conflict: model version {model.version} "
                    f"!= entity version {entry.version} for entry {entry.id}"
                )
            self._mapper.apply_to_model(model, entry)
        await self._session.flush()

    async def save_many(self, entries: list[QueueEntry]) -> None:
        """Insert or update multiple entries in a single transaction."""
        for entry in entries:
            await self.save(entry)

    async def delete(self, entry_id: str) -> None:
        """Delete a queue entry by ID."""
        model = await self._session.get(QueueEntryModel, self._to_uuid(entry_id))
        if model:
            await self._session.delete(model)
            await self._session.flush()

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    async def get_by_id(self, entry_uuid: str) -> QueueEntry | None:
        """Get a single queue entry by its UUID."""
        model = await self._session.get(QueueEntryModel, self._to_uuid(entry_uuid))
        if model is None:
            return None
        return self._mapper.to_domain(model)

    async def get_active_by_patient(
        self, patient_uuid: str
    ) -> list[QueueEntry]:
        """Get all non-terminal queue entries for a patient."""
        active_statuses = [s.value for s in QueueStatus if s.is_active]
        stmt = (
            select(QueueEntryModel)
            .where(
                and_(
                    QueueEntryModel.patient_uuid == patient_uuid,
                    QueueEntryModel.status.in_(active_statuses),
                )
            )
            .order_by(asc(QueueEntryModel.display_order))
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._mapper.to_domain(m) for m in models]

    async def list_by_department(
        self,
        department: str,
        status_filter: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[QueueEntry]:
        """List queue entries for a department, with optional status filter."""
        conditions = [QueueEntryModel.department == department]
        if status_filter:
            conditions.append(QueueEntryModel.status == status_filter)

        stmt = (
            select(QueueEntryModel)
            .where(and_(*conditions))
            .order_by(
                asc(QueueEntryModel.display_order),
                asc(QueueEntryModel.token_number),
            )
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._mapper.to_domain(m) for m in models]

    async def list_by_visit(self, visit_id: str) -> list[QueueEntry]:
        """Get all queue entries belonging to a visit."""
        stmt = (
            select(QueueEntryModel)
            .where(QueueEntryModel.visit_id == visit_id)
            .order_by(asc(QueueEntryModel.display_order))
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._mapper.to_domain(m) for m in models]

    async def get_next_token_number(
        self, service_code: str, date_prefix: str
    ) -> int:
        """Get the next sequential token number for a service today.

        Args:
            service_code: The test code (ECG, Echo, etc.).
            date_prefix: Date prefix like '20260714' to scope by day.

        Returns:
            The next available token number (starts at 1).
        """
        stmt = select(func.coalesce(func.max(QueueEntryModel.token_number), 0)).where(
            and_(
                QueueEntryModel.service_code == service_code,
                QueueEntryModel.visit_id.like(f"VIS-{date_prefix}-%"),
            )
        )
        result = await self._session.execute(stmt)
        max_token = result.scalar() or 0
        return max_token + 1

    async def get_queue_depth(self, service_code: str) -> int:
        """Count how many WAITING entries exist for a service."""
        stmt = select(func.count(QueueEntryModel.id)).where(
            and_(
                QueueEntryModel.service_code == service_code,
                QueueEntryModel.status == QueueStatus.WAITING.value,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def count_by_status(
        self, department: str, status: str
    ) -> int:
        """Count entries in a given status for a department."""
        stmt = select(func.count(QueueEntryModel.id)).where(
            and_(
                QueueEntryModel.department == department,
                QueueEntryModel.status == status,
                func.date(QueueEntryModel.created_at) == func.current_date(),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def list_patient_queue(
        self, patient_uuid: str
    ) -> list[QueueEntry]:
        """Get all queue entries for a patient (patient PWA view)."""
        stmt = (
            select(QueueEntryModel)
            .where(QueueEntryModel.patient_uuid == patient_uuid)
            .order_by(desc(QueueEntryModel.created_at))
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._mapper.to_domain(m) for m in models]

    async def list_by_status(
        self,
        status: str,
        offset: int = 0,
        limit: int = 100,
    ) -> list[QueueEntry]:
        """List queue entries by status across all departments (doctor view).

        Args:
            status: Status filter (e.g., 'COMPLETED', 'REPORT_READY').
            offset: Number of records to skip.
            limit: Maximum records to return.

        Returns:
            List of matching QueueEntry domain entities.
        """
        stmt = (
            select(QueueEntryModel)
            .where(
                and_(
                    QueueEntryModel.status == status,
                    func.date(QueueEntryModel.created_at) == func.current_date(),
                )
            )
            .order_by(desc(QueueEntryModel.created_at))
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._mapper.to_domain(m) for m in models]

    # ------------------------------------------------------------------
    # Analytics / Manager Dashboard
    # ------------------------------------------------------------------

    async def count_created_between(
        self, start: datetime, end: datetime
    ) -> int:
        """Count queue entries created between two datetimes."""
        stmt = select(func.count(QueueEntryModel.id)).where(
            and_(
                QueueEntryModel.created_at >= start,
                QueueEntryModel.created_at <= end,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def get_service_stats(
        self, date_from: datetime, date_to: datetime
    ) -> list[dict]:
        """Per-service stats within a date range.

        Returns list of dicts: service_code, count, avg_wait_minutes.
        avg_wait_minutes = AVG(completed_at - started_at) in minutes.
        """
        # SQLite: completed_at - started_at gives seconds, divide by 60
        # Use julianday for cross-platform compatibility
        wait_expr = func.avg(
            func.julianday(QueueEntryModel.completed_at)
            - func.julianday(QueueEntryModel.started_at)
        ) * 24 * 60

        stmt = (
            select(
                QueueEntryModel.service_code,
                func.count(QueueEntryModel.id).label("count"),
                func.coalesce(wait_expr, 0).label("avg_wait_minutes"),
            )
            .where(
                and_(
                    QueueEntryModel.created_at >= date_from,
                    QueueEntryModel.created_at <= date_to,
                    QueueEntryModel.completed_at.isnot(None),
                )
            )
            .group_by(QueueEntryModel.service_code)
            .order_by(desc("count"))
        )
        result = await self._session.execute(stmt)
        rows = result.all()
        return [
            {
                "service_code": row.service_code,
                "count": row.count,
                "avg_wait_minutes": round(float(row.avg_wait_minutes), 1),
            }
            for row in rows
        ]

    async def get_daily_counts(
        self, days: int = 7
    ) -> list[dict]:
        """Daily creation and completion counts for the last N days.

        Returns list of dicts: date (str YYYY-MM-DD), created (int), completed (int).
        """
        from datetime import timedelta

        since = datetime.now(timezone.utc) - timedelta(days=days)

        # Created counts per day
        created_subq = (
            select(
                func.date(QueueEntryModel.created_at).label("day"),
                func.count(QueueEntryModel.id).label("created"),
            )
            .where(QueueEntryModel.created_at >= since)
            .group_by(func.date(QueueEntryModel.created_at))
            .subquery()
        )

        # Completed counts per day
        completed_subq = (
            select(
                func.date(QueueEntryModel.completed_at).label("day"),
                func.count(QueueEntryModel.id).label("completed"),
            )
            .where(
                and_(
                    QueueEntryModel.completed_at >= since,
                    QueueEntryModel.completed_at.isnot(None),
                )
            )
            .group_by(func.date(QueueEntryModel.completed_at))
            .subquery()
        )

        # Full outer join on day
        stmt = (
            select(
                func.coalesce(created_subq.c.day, completed_subq.c.day).label("day"),
                func.coalesce(created_subq.c.created, 0).label("created"),
                func.coalesce(completed_subq.c.completed, 0).label("completed"),
            )
            .select_from(created_subq)
            .outerjoin(
                completed_subq,
                created_subq.c.day == completed_subq.c.day,
            )
            .order_by(asc("day"))
        )
        result = await self._session.execute(stmt)
        rows = result.all()

        # Build complete date range filling in zeros
        date_map = {}
        for i in range(days + 1):
            d = (datetime.now(timezone.utc) - timedelta(days=days - i)).strftime("%Y-%m-%d")
            date_map[d] = {"date": d, "created": 0, "completed": 0}
        for row in rows:
            key = str(row.day)
            if key in date_map:
                date_map[key]["created"] = row.created
                date_map[key]["completed"] = row.completed

        return list(date_map.values())

    # ------------------------------------------------------------------
    # Alert system
    # ------------------------------------------------------------------

    async def set_alert(self, entry_id: str, message: str) -> None:
        """Set pending_alert flag and message on a queue entry."""
        model = await self._session.get(QueueEntryModel, self._to_uuid(entry_id))
        if model is None:
            raise ValueError(f"Queue entry '{entry_id}' not found for alert")
        model.pending_alert = True
        model.alert_message = message
        await self._session.flush()

    async def check_alert(self, entry_id: str) -> tuple[bool, str | None]:
        """Check if a queue entry has a pending alert."""
        model = await self._session.get(QueueEntryModel, self._to_uuid(entry_id))
        if model is None:
            return False, None
        return bool(model.pending_alert), model.alert_message

    async def clear_alert(self, entry_id: str) -> None:
        """Clear the pending_alert flag on a queue entry."""
        model = await self._session.get(QueueEntryModel, self._to_uuid(entry_id))
        if model is None:
            return
        model.pending_alert = False
        model.alert_message = None
        await self._session.flush()
