"""Mapper: QueueEntry domain ↔ QueueEntryModel."""

from __future__ import annotations

from src.domain.queue.entities.queue_entry import QueueEntry
from src.domain.queue.value_objects.queue_status import QueueStatus
from src.infrastructure.queue.models.queue_entry_model import QueueEntryModel


class QueueEntryMapper:
    """Converts between QueueEntry domain entity and QueueEntryModel."""

    @staticmethod
    def to_model(entity: QueueEntry) -> QueueEntryModel:
        return QueueEntryModel(
            id=entity.id,
            visit_id=entity.visit_id,
            patient_id=entity.patient_id,
            patient_uuid=entity.patient_uuid,
            patient_name=entity.patient_name,
            service_code=entity.service_code,
            token_number=entity.token_number,
            department=entity.department,
            room=entity.room,
            status=entity.status.value if entity.status else "WAITING",
            priority=entity.priority,
            display_order=entity.display_order,
            created_by=entity.created_by,
            updated_by=entity.updated_by,
            pending_alert=entity.pending_alert,
            alert_message=entity.alert_message,
            notes=entity.notes,
            called_at=entity.called_at,
            started_at=entity.started_at,
            completed_at=entity.completed_at,
            report_ready_at=entity.report_ready_at,
            delivered_at=entity.delivered_at,
            version=entity.version,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    @staticmethod
    def to_domain(model: QueueEntryModel) -> QueueEntry:
        try:
            status = QueueStatus(model.status)
        except (ValueError, TypeError):
            status = QueueStatus.WAITING

        entry = QueueEntry(
            id=model.id,
            visit_id=model.visit_id,
            patient_id=model.patient_id,
            patient_uuid=model.patient_uuid,
            patient_name=model.patient_name,
            service_code=model.service_code,
            token_number=model.token_number,
            department=model.department,
            room=model.room,
            status=status,
            priority=model.priority,
            display_order=model.display_order,
            created_by=model.created_by,
            updated_by=model.updated_by,
            pending_alert=model.pending_alert,
            alert_message=model.alert_message,
            notes=model.notes or "",
            called_at=model.called_at,
            started_at=model.started_at,
            completed_at=model.completed_at,
            report_ready_at=model.report_ready_at,
            delivered_at=model.delivered_at,
            version=model.version,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
        return entry

    @staticmethod
    def apply_to_model(model: QueueEntryModel, entity: QueueEntry) -> None:
        model.status = entity.status.value if entity.status else "WAITING"
        model.priority = entity.priority
        model.display_order = entity.display_order
        model.updated_by = entity.updated_by
        model.pending_alert = entity.pending_alert
        model.alert_message = entity.alert_message
        model.notes = entity.notes
        model.called_at = entity.called_at
        model.started_at = entity.started_at
        model.completed_at = entity.completed_at
        model.report_ready_at = entity.report_ready_at
        model.delivered_at = entity.delivered_at
        model.version = entity.version
        model.updated_at = entity.updated_at
