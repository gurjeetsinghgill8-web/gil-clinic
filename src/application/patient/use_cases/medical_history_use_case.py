"""MedicalHistoryUseCase — manage patient medical history.

Supports:
1. Add medical history entry
2. List medical history

Dependencies:
- PatientRepository
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.application.common.base_use_case import BaseUseCase
from src.application.common.command import Command
from src.application.common.result import Result
from src.application.common.exceptions import NotFoundError, ValidationError
from src.application.patient.dtos.responses import AddMedicalHistoryRequest
from src.domain.patient.value_objects.medical_history import (
    MedicalHistoryEntry,
)
from src.domain.patient.events.patient_events import (
    patient_medical_history_updated,
)

if TYPE_CHECKING:
    from src.domain.patient.ports.patient_repository import PatientRepository
    from src.domain.identity.ports.event_publisher import EventPublisher


class MedicalHistoryUseCase(BaseUseCase):
    """Use case for managing patient medical history."""

    def __init__(
        self,
        patient_repo: PatientRepository,
        event_publisher: EventPublisher,
    ) -> None:
        super().__init__()
        self._patient_repo = patient_repo
        self._event_publisher = event_publisher

    async def authorize(self, command: Command) -> None:
        """Medical history management requires staff authentication."""
        pass

    async def execute(self, command: Command) -> Result:
        """Execute medical history operation.

        Args:
            command: Command with operation type and parameters.

        Returns:
            Result with medical history data.
        """
        dto = command.data
        operation = getattr(dto, "operation", "add")

        try:
            if operation == "add":
                return await self._add_history(dto)
            elif operation == "list":
                return await self._list_history(dto)
            else:
                raise ValidationError(
                    message=f"Unknown operation: {operation}",
                    details={"operation": operation},
                )

        except (NotFoundError, ValidationError) as exc:
            return Result.fail(
                error=str(exc),
                code=exc.code,
                details=exc.details,
            )

    async def _add_history(self, dto: AddMedicalHistoryRequest) -> Result:
        """Add a medical history entry."""
        patient = await self._patient_repo.get_by_patient_id(dto.patient_id)
        if not patient:
            raise NotFoundError(
                message=f"Patient with ID '{dto.patient_id}' not found.",
                details={"patient_id": dto.patient_id},
            )

        entry = MedicalHistoryEntry(
            condition=dto.condition,
            diagnosed_at=dto.diagnosed_at,
            notes=dto.notes,
            is_active=dto.is_active,
        )
        patient.add_medical_history(entry)
        await self._patient_repo.save(patient)

        self._event_publisher.publish(
            patient_medical_history_updated(
                patient_id=str(patient.id),
                condition=dto.condition,
            )
        )

        return Result.ok(
            data={
                "condition": dto.condition,
                "diagnosed_at": dto.diagnosed_at,
                "is_active": dto.is_active,
            },
            message=f"Medical history entry added: {dto.condition}.",
        )

    async def _list_history(self, dto) -> Result:
        """List all medical history entries for a patient."""
        patient = await self._patient_repo.get_by_patient_id(dto.patient_id)
        if not patient:
            raise NotFoundError(
                message=f"Patient with ID '{dto.patient_id}' not found.",
                details={"patient_id": dto.patient_id},
            )

        entries = [
            {
                "condition": e.condition,
                "diagnosed_at": e.diagnosed_at,
                "notes": e.notes,
                "is_active": e.is_active,
                "recorded_at": e.recorded_at.isoformat(),
            }
            for e in patient.medical_history
        ]

        return Result.ok(
            data={
                "patient_id": patient.patient_id,
                "entries": entries,
                "count": len(entries),
            },
        )
