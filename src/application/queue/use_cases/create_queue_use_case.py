"""Queue Lite — Create Queue Entries (Reception).

Reception selects patient + tests → generates queue entries with tokens.
Each test gets its own queue entry with sequential token number.
Audit entries are recorded for each queue entry created.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from src.application.common.base_use_case import BaseUseCase
from src.application.common.command import Command
from src.application.common.result import Result
from src.application.common.exceptions import NotFoundError, ValidationError
from src.domain.queue.entities.queue_entry import QueueEntry
from src.domain.queue.events.queue_events import QUEUE_CREATED, STATUS_TO_EVENT

if TYPE_CHECKING:
    from src.domain.queue.ports.queue_repository import QueueRepository
    from src.domain.patient.ports.patient_repository import PatientRepository
    from src.infrastructure.persistence.queue.repositories.audit_repository import (
        SqlAlchemyAuditRepository,
    )


class CreateQueueUseCase(BaseUseCase):
    """Use case for creating queue entries (Reception workflow)."""

    def __init__(
        self,
        queue_repo: QueueRepository,
        patient_repo: PatientRepository,
        audit_repo: SqlAlchemyAuditRepository | None = None,
    ) -> None:
        super().__init__()
        self._queue_repo = queue_repo
        self._patient_repo = patient_repo
        self._audit_repo = audit_repo

    async def authorize(self, command: Command) -> None:
        pass

    async def execute(self, command: Command) -> Result:
        dto = command.data
        patient_id = dto.get("patient_id", "")
        service_codes = dto.get("services", [])
        created_by = dto.get("created_by", "reception")

        try:
            # Validate patient exists
            patient = await self._patient_repo.get_by_patient_id(patient_id)
            if not patient:
                raise NotFoundError(
                    message=f"Patient '{patient_id}' not found.",
                    details={"patient_id": patient_id},
                )

            if not patient.can_register_visit:
                raise ValidationError(
                    message=f"Patient '{patient_id}' cannot register (status: {patient.status.status.value}).",
                )

            if not service_codes:
                raise ValidationError(
                    message="At least one service/test must be selected.",
                    details={"field": "services"},
                )

            # Generate visit ID and record visit
            visit_id = datetime.now(timezone.utc).strftime("VIS-%Y%m%d-%f")
            patient.record_visit()
            await self._patient_repo.save(patient)

            # Create queue entries
            today = datetime.now(timezone.utc).strftime("%Y%m%d")
            entries = []
            for code in service_codes:
                token = await self._queue_repo.get_next_token_number(code, today)
                entry = QueueEntry.create(
                    visit_id=visit_id,
                    patient_id=patient.patient_id,
                    patient_uuid=str(patient.id),
                    patient_name=patient.demographics.name,
                    service_code=code.upper(),
                    token_number=token,
                    created_by=created_by,
                )
                await self._queue_repo.save(entry)
                entries.append(entry)

                # Record audit entry for each queue entry created
                self.collect_audit({
                    "actor": created_by,
                    "action": QUEUE_CREATED,
                    "resource_type": "queue_entry",
                    "resource_id": str(entry.id),
                    "old_status": None,
                    "new_status": "WAITING",
                    "details": {
                        "visit_id": visit_id,
                        "patient_id": patient.patient_id,
                        "patient_name": patient.demographics.name,
                        "service_code": code.upper(),
                        "token_number": token,
                    },
                })

            # Persist audit entries
            if self._audit and self._audit_repo:
                await self._audit_repo.save_many(self._audit)

            return Result.ok(
                data={
                    "visit_id": visit_id,
                    "patient_id": patient.patient_id,
                    "patient_name": patient.demographics.name,
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
                            "status": e.status.value if e.status else "WAITING",
                            "status_display": e.status_display,
                            "is_active": e.is_active,
                            "display_order": e.display_order,
                            "called_at": None,
                            "started_at": None,
                            "completed_at": None,
                            "report_ready_at": None,
                            "delivered_at": None,
                            "created_at": e.created_at.isoformat(),
                        }
                        for e in entries
                    ],
                    "total_entries": len(entries),
                    "message": (
                        f"{patient.demographics.name} registered for "
                        f"{len(entries)} test(s)."
                    ),
                },
            )

        except (NotFoundError, ValidationError) as exc:
            return Result.fail(
                error=str(exc),
                code=exc.code,
                details=exc.details,
            )
