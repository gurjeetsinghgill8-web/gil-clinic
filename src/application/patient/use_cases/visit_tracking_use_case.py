"""VisitTrackingUseCase — record and track patient visits.

Supports:
1. Record a visit (called when patient is registered for tests)
2. Get visit history / timeline

Dependencies:
- PatientRepository, EventPublisher
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.application.common.base_use_case import BaseUseCase
from src.application.common.command import Command
from src.application.common.result import Result
from src.application.common.exceptions import NotFoundError
from src.domain.patient.events.patient_events import patient_visited

if TYPE_CHECKING:
    from src.domain.patient.ports.patient_repository import PatientRepository
    from src.domain.identity.ports.event_publisher import EventPublisher


class VisitTrackingUseCase(BaseUseCase):
    """Use case for tracking patient visits."""

    def __init__(
        self,
        patient_repo: PatientRepository,
        event_publisher: EventPublisher,
    ) -> None:
        super().__init__()
        self._patient_repo = patient_repo
        self._event_publisher = event_publisher

    async def authorize(self, command: Command) -> None:
        """Visit tracking requires staff authentication."""
        pass

    async def execute(self, command: Command) -> Result:
        """Execute visit tracking operation.

        Args:
            command: Command with operation type and parameters.

        Returns:
            Result with visit data.
        """
        dto = command.data
        operation = getattr(dto, "operation", "record")

        try:
            if operation == "record_visit":
                return await self._record_visit(dto)
            elif operation == "get_timeline":
                return await self._get_timeline(dto)
            else:
                from src.application.common.exceptions import ValidationError
                raise ValidationError(
                    message=f"Unknown operation: {operation}",
                    details={"operation": operation},
                )

        except NotFoundError as exc:
            return Result.fail(
                error=str(exc),
                code=exc.code,
                details=exc.details,
            )

    async def _record_visit(self, dto) -> Result:
        """Record a new visit for the patient."""
        patient = await self._patient_repo.get_by_patient_id(dto.patient_id)
        if not patient:
            raise NotFoundError(
                message=f"Patient with ID '{dto.patient_id}' not found.",
                details={"patient_id": dto.patient_id},
            )

        if not patient.can_register_visit:
            from src.application.common.exceptions import ConflictError
            raise ConflictError(
                message=f"Patient '{dto.patient_id}' cannot register a new visit (status: {patient.status.status.value}).",
                details={"status": patient.status.status.value},
            )

        patient.record_visit()
        await self._patient_repo.save(patient)

        self._event_publisher.publish(
            patient_visited(
                patient_id=str(patient.id),
                visit_number=patient.total_visits,
            )
        )

        return Result.ok(
            data={
                "patient_id": patient.patient_id,
                "visit_number": patient.total_visits,
                "last_visit_at": patient.last_visit_at.isoformat()
                if patient.last_visit_at else None,
            },
            message=f"Visit #{patient.total_visits} recorded for {patient.demographics.name}.",
        )

    async def _get_timeline(self, dto) -> Result:
        """Return patient timeline information (visit count, last visit, etc.)."""
        patient = await self._patient_repo.get_by_patient_id(dto.patient_id)
        if not patient:
            raise NotFoundError(
                message=f"Patient with ID '{dto.patient_id}' not found.",
                details={"patient_id": dto.patient_id},
            )

        return Result.ok(
            data={
                "patient_id": patient.patient_id,
                "name": patient.demographics.name,
                "total_visits": patient.total_visits,
                "first_visit": patient.is_first_visit,
                "last_visit_at": patient.last_visit_at.isoformat()
                if patient.last_visit_at else None,
                "days_since_last_visit": patient.days_since_last_visit,
                "status": patient.status.status.value,
                "device_count": patient.device_count,
                "has_qr_identity": patient.has_qr_identity(),
            },
        )
