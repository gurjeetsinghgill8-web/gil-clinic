"""Queue Lite — Technician Actions (Call, Start, Complete, Report Ready).

Single use case handling all technician status transitions.
Every action is recorded in the audit log.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.application.common.base_use_case import BaseUseCase
from src.application.common.command import Command
from src.application.common.result import Result
from src.application.common.exceptions import NotFoundError, ValidationError
from src.domain.queue.events.queue_events import STATUS_TO_EVENT

if TYPE_CHECKING:
    from src.domain.queue.ports.queue_repository import QueueRepository
    from src.infrastructure.persistence.queue.repositories.audit_repository import (
        SqlAlchemyAuditRepository,
    )


class TechnicianActionUseCase(BaseUseCase):
    """Use case for technician actions: call, start, complete, report-ready."""

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
        action = dto.get("action", "")
        updated_by = dto.get("updated_by", "technician")

        try:
            entry = await self._queue_repo.get_by_id(entry_id)
            if not entry:
                raise NotFoundError(
                    message=f"Queue entry '{entry_id}' not found.",
                    details={"entry_id": entry_id},
                )

            # Execute the action
            action_map = {
                "call": (entry.call, [updated_by]),
                "recall": (entry.recall_to_waiting, [updated_by]),
                "start": (entry.start, [updated_by]),
                "complete": (entry.complete, [updated_by]),
                "report-ready": (entry.mark_report_ready, [updated_by]),
                "deliver": (entry.deliver, [updated_by]),
                "reject": (entry.reject, [updated_by, dto.get("reason", "")]),
                "cancel": (entry.cancel, [updated_by, dto.get("reason", "")]),
                "no-show": (entry.mark_no_show, [updated_by]),
            }

            if action not in action_map:
                raise ValidationError(
                    message=f"Unknown action: {action}",
                    details={"action": action, "allowed": list(action_map.keys())},
                )

            func, args = action_map[action]

            # Capture previous status before mutation
            previous_status = entry.status.value if entry.status else "UNKNOWN"
            action_event = STATUS_TO_EVENT.get(
                dto.get("target_status", ""), action.upper().replace("-", "_")
            )

            try:
                func(*args)
            except ValueError as e:
                raise ValidationError(
                    message=str(e),
                    details={
                        "entry_id": entry_id,
                        "current_status": entry.status.value if entry.status else "?",
                        "action": action,
                    },
                ) from e

            await self._queue_repo.save(entry)

            # Record audit entry
            new_status = entry.status.value if entry.status else "UNKNOWN"
            self.collect_audit({
                "actor": updated_by,
                "action": action_event,
                "resource_type": "queue_entry",
                "resource_id": entry_id,
                "old_status": previous_status,
                "new_status": new_status,
                "details": {
                    "service_code": entry.service_code,
                    "patient_name": entry.patient_name,
                    "token_number": entry.token_number,
                    "reason": dto.get("reason", ""),
                },
            })

            # Persist audit entries
            if self._audit_repo:
                await self._audit_repo.save_many(self._audit)

            return Result.ok(
                data={
                    "id": str(entry.id),
                    "patient_name": entry.patient_name,
                    "service_code": entry.service_code,
                    "token_number": entry.token_number,
                    "previous_status": previous_status,
                    "action": action,
                    "timestamp": entry.updated_at.isoformat(),
                    "message": f"{entry.patient_name} — {action}: {entry.status_display}",
                },
            )

        except (NotFoundError, ValidationError) as exc:
            return Result.fail(
                error=str(exc),
                code=exc.code,
                details=exc.details,
            )
