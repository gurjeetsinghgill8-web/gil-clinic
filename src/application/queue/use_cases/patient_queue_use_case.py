"""Queue Lite — Patient Queue Status (Patient PWA).

Returns the current queue position and status for a patient.
This is the endpoint the PWA dashboard calls to show live status.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.application.common.base_use_case import BaseUseCase
from src.application.common.command import Command
from src.application.common.result import Result
from src.application.common.exceptions import NotFoundError

if TYPE_CHECKING:
    from src.domain.queue.ports.queue_repository import QueueRepository
    from src.domain.patient.ports.patient_repository import PatientRepository


class PatientQueueUseCase(BaseUseCase):
    """Use case for patient's personal queue view (PWA dashboard)."""

    def __init__(
        self,
        queue_repo: QueueRepository,
        patient_repo: PatientRepository,
    ) -> None:
        super().__init__()
        self._queue_repo = queue_repo
        self._patient_repo = patient_repo

    async def authorize(self, command: Command) -> None:
        pass

    @staticmethod
    def _get_avg_test_time(service_code: str) -> int:
        """Get average test time in minutes from dynamic service config."""
        try:
            from src.infrastructure.clinic.department_provider import get_service_by_code
            svc = get_service_by_code(service_code)
            if svc:
                return svc.avg_test_time
        except Exception:
            pass
        return 10

    async def execute(self, command: Command) -> Result:
        dto = command.data
        patient_uuid = dto.get("patient_uuid", "")

        try:
            patient = await self._patient_repo.get_by_id(patient_uuid)
            if not patient:
                raise NotFoundError(message="Patient not found.")

            entries = await self._queue_repo.get_active_by_patient(patient_uuid)

            # Enrich with wait time and ETA
            enriched = []
            for e in entries:
                depth = await self._queue_repo.get_queue_depth(e.service_code)
                position = depth  # simplified

                avg_min = self._get_avg_test_time(e.service_code)
                wait_min = max(position - 1, 0) * avg_min

                enriched.append({
                    "id": str(e.id),
                    "service_code": e.service_code,
                    "service_name": e.service_name,
                    "token_number": e.token_number,
                    "status": e.status.value if e.status else "?",
                    "status_display": e.status_display,
                    "room": e.room,
                    "queue_position": position,
                    "wait_minutes": wait_min,
                    "called_at": e.called_at.isoformat() if e.called_at else None,
                    "started_at": e.started_at.isoformat() if e.started_at else None,
                })

            return Result.ok(
                data={
                    "patient_id": patient.patient_id,
                    "patient_name": patient.demographics.name,
                    "total_visits": patient.total_visits,
                    "entries": enriched,
                    "active_count": len(enriched),
                },
            )

        except NotFoundError as exc:
            return Result.fail(error=str(exc), code=exc.code, details=exc.details)
