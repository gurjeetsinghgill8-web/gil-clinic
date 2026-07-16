"""Queue Lite — List Queue Entries (Technician Dashboard).

Returns today's queue for a department, with optional status filter.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.application.common.base_use_case import BaseUseCase
from src.application.common.command import Command
from src.application.common.result import Result
from src.application.common.exceptions import ValidationError

if TYPE_CHECKING:
    from src.domain.queue.ports.queue_repository import QueueRepository


# Status display order for the dashboard
STATUS_SORT_ORDER = {
    "WAITING": 0,
    "CALLED": 1,
    "IN_PROGRESS": 2,
    "COMPLETED": 3,
    "REPORT_READY": 4,
}


class ListQueueUseCase(BaseUseCase):
    """Use case for listing queue entries (Technician Dashboard)."""

    def __init__(self, queue_repo: QueueRepository) -> None:
        super().__init__()
        self._queue_repo = queue_repo

    async def authorize(self, command: Command) -> None:
        pass

    async def execute(self, command: Command) -> Result:
        dto = command.data
        department = dto.get("department", "Cardiology")
        status_filter = dto.get("status")
        offset = dto.get("offset", 0)
        limit = dto.get("limit", 100)

        try:
            entries = await self._queue_repo.list_by_department(
                department=department,
                status_filter=status_filter,
                offset=offset,
                limit=limit,
            )

            # Counts for dashboard stats
            waiting_count = await self._queue_repo.count_by_status(department, "WAITING")
            called_count = await self._queue_repo.count_by_status(department, "CALLED")
            in_progress_count = await self._queue_repo.count_by_status(department, "IN_PROGRESS")

            # Sort: active first, then by status order, then by token
            sorted_entries = sorted(
                entries,
                key=lambda e: (
                    0 if e.is_active else 1,
                    STATUS_SORT_ORDER.get(e.status.value if e.status else "", 99),
                    e.token_number,
                ),
            )

            return Result.ok(
                data={
                    "department": department,
                    "total": len(sorted_entries),
                    "stats": {
                        "waiting": waiting_count,
                        "called": called_count,
                        "in_progress": in_progress_count,
                        "active": waiting_count + called_count + in_progress_count,
                    },
                    "entries": [
                        {
                            "id": str(e.id),
                            "visit_id": e.visit_id,
                            "patient_id": e.patient_id,
                            "patient_name": e.patient_name,
                            "service_code": e.service_code,
                            "service_name": e.service_name,
                            "token_number": e.token_number,
                            "room": e.room,
                            "status": e.status.value if e.status else "?",
                            "status_display": e.status_display,
                            "is_active": e.is_active,
                            "display_order": e.display_order,
                            "alert_message": e.alert_message,
                            "notes": e.notes,
                            "called_at": e.called_at.isoformat() if e.called_at else None,
                            "started_at": e.started_at.isoformat() if e.started_at else None,
                            "completed_at": e.completed_at.isoformat() if e.completed_at else None,
                            "created_at": e.created_at.isoformat(),
                        }
                        for e in sorted_entries
                    ],
                },
            )

        except ValidationError as exc:
            return Result.fail(error=str(exc), code=exc.code, details=exc.details)
