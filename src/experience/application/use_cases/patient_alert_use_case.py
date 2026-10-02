"""Experience Engine — Patient Alert Check Use Case.

Patient PWA calls this to check for pending alerts.
If an alert exists, it is returned and auto-cleared atomically.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from src.application.common.base_use_case import BaseUseCase
from src.application.common.command import Command
from src.application.common.result import Result

if TYPE_CHECKING:
    from src.domain.queue.ports.queue_repository import QueueRepository


class PatientAlertUseCase(BaseUseCase):
    """Use case for checking and clearing patient alerts.

    Called by the patient PWA every refresh cycle.
    If a pending alert exists, it is returned and cleared in one atomic call.
    """

    def __init__(self, queue_repo: QueueRepository) -> None:
        super().__init__()
        self._queue_repo = queue_repo

    async def authorize(self, command: Command) -> None:
        pass

    async def execute(self, command: Command) -> Result:
        dto = command.data
        patient_uuid = dto.get("patient_uuid", "")

        # Get all active queue entries for this patient
        entries = await self._queue_repo.get_active_by_patient(patient_uuid)

        # Check each entry for a pending alert
        for entry in entries:
            has_alert, alert_message = await self._queue_repo.check_alert(
                str(entry.id)
            )
            if has_alert:
                # Clear the alert atomically
                await self._queue_repo.clear_alert(str(entry.id))

                return Result.ok(
                    data={
                        "alert": True,
                        "message": alert_message or "Please proceed",
                        "room": entry.room,
                        "service_code": entry.service_code,
                        "service_name": entry.service_name,
                        "token_number": entry.token_number,
                    },
                    message="Alert found",
                )

        # No alert
        return Result.ok(
            data={
                "alert": False,
                "message": None,
            },
        )
