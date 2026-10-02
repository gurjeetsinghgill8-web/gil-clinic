"""Queue Lite — Send Alert/Reminder to Patient.

Technician sends a browser notification (beep + vibrate + banner)
to the patient's phone. Only allowed for WAITING or CALLED status.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from src.application.common.base_use_case import BaseUseCase
from src.application.common.command import Command
from src.application.common.result import Result
from src.application.common.exceptions import NotFoundError, ValidationError
from src.domain.queue.events.queue_events import QUEUE_ALERT

if TYPE_CHECKING:
    from src.domain.queue.ports.queue_repository import QueueRepository
    from src.infrastructure.persistence.queue.repositories.audit_repository import (
        SqlAlchemyAuditRepository,
    )


# Rate limit: minimum seconds between alerts for the same entry
ALERT_COOLDOWN_SECONDS = 30


class AlertUseCase(BaseUseCase):
    """Use case for sending alerts/reminders to patients.

    Technician triggers a browser notification on the patient's PWA.
    """

    def __init__(
        self,
        queue_repo: QueueRepository,
        audit_repo: SqlAlchemyAuditRepository | None = None,
    ) -> None:
        super().__init__()
        self._queue_repo = queue_repo
        self._audit_repo = audit_repo

    async def authorize(self, command: Command) -> None:
        pass

    async def execute(self, command: Command) -> Result:
        dto = command.data
        entry_id = dto.get("entry_id", "")
        message = dto.get("message", "")
        updated_by = dto.get("updated_by", "technician")

        try:
            # Load the queue entry
            entry = await self._queue_repo.get_by_id(entry_id)
            if not entry:
                raise NotFoundError(
                    message=f"Queue entry '{entry_id}' not found.",
                    details={"entry_id": entry_id},
                )

            # Validate status — alert only for WAITING or CALLED
            if entry.status and entry.status.value not in ("WAITING", "CALLED"):
                raise ValidationError(
                    message=f"Cannot alert patient in '{entry.status.value}' status.",
                    details={
                        "entry_id": entry_id,
                        "current_status": entry.status.value,
                        "action": "alert",
                    },
                )

            # Default message
            if not message:
                message = f"Please proceed to {entry.room}"

            # Set the alert
            await self._queue_repo.set_alert(entry_id, message)

            # Audit
            self.collect_audit({
                "actor": updated_by,
                "action": QUEUE_ALERT,
                "resource_type": "queue_entry",
                "resource_id": entry_id,
                "old_status": entry.status.value if entry.status else None,
                "new_status": entry.status.value if entry.status else None,
                "details": {
                    "patient_name": entry.patient_name,
                    "service_code": entry.service_code,
                    "token_number": entry.token_number,
                    "alert_message": message,
                },
            })

            if self._audit_repo:
                await self._audit_repo.save_many(self._audit)

            return Result.ok(
                data={
                    "entry_id": entry_id,
                    "patient_name": entry.patient_name,
                    "message": message,
                    "sent": True,
                },
                message=f"🔔 Alert sent to {entry.patient_name}",
            )

        except (NotFoundError, ValidationError) as exc:
            return Result.fail(
                error=str(exc),
                code=exc.code,
                details=exc.details,
            )
