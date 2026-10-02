"""Queue Lite — Doctor Workspace.

Composite view for the doctor's room showing:
- Consultation queue (WAITING/CALLED patients to see)
- Completed tests pending doctor review (COMPLETED)
- Reports ready for delivery (REPORT_READY)
- Grouped by visit_id with enriched patient demographics
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.application.common.base_use_case import BaseUseCase
from src.application.common.command import Command
from src.application.common.result import Result

if TYPE_CHECKING:
    from src.domain.queue.ports.queue_repository import QueueRepository
    from src.domain.patient.ports.patient_repository import PatientRepository


def _elapsed_minutes(dt) -> int | None:
    """Calculate elapsed minutes from a datetime to now."""
    if dt is None:
        return None
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    # Handle offset-naive datetimes (e.g. from SQLite func.now())
    if dt.tzinfo is None:
        now = now.replace(tzinfo=None)
    delta = now - dt
    return int(delta.total_seconds() / 60)


async def _enrich_entry(entry, patient_repo: PatientRepository) -> dict:
    """Enrich a single queue entry with patient demographics."""
    age = None
    gender = None
    phone = None
    blood_group = None
    medical_history = []

    if entry.patient_uuid:
        patient = await patient_repo.get_by_id(entry.patient_uuid)
        if patient:
            if patient.demographics:
                age = patient.demographics.age
                gender = patient.demographics.gender
                blood_group = patient.demographics.blood_group
            if patient.contact:
                phone = patient.contact.phone
            if patient.medical_history:
                medical_history = [
                    {
                        "condition": h.condition,
                        "is_active": h.is_active,
                    }
                    for h in patient.medical_history[-3:]  # Last 3 entries
                ]

    return {
        "id": str(entry.id),
        "visit_id": entry.visit_id,
        "patient_id": entry.patient_id,
        "patient_uuid": entry.patient_uuid,
        "patient_name": entry.patient_name,
        "age": age,
        "gender": gender,
        "phone": phone,
        "blood_group": blood_group,
        "medical_history": medical_history,
        "notes": entry.notes,
        "alert_message": entry.alert_message,
        "service_code": entry.service_code,
        "service_name": entry.service_name,
        "token_number": entry.token_number,
        "department": entry.department,
        "room": entry.room,
        "status": entry.status.value if entry.status else "?",
        "status_display": entry.status_display,
        "created_by": entry.created_by,
        "called_at": entry.called_at.isoformat() if entry.called_at else None,
        "started_at": entry.started_at.isoformat() if entry.started_at else None,
        "completed_at": entry.completed_at.isoformat() if entry.completed_at else None,
        "report_ready_at": entry.report_ready_at.isoformat() if entry.report_ready_at else None,
        "elapsed_minutes": _elapsed_minutes(entry.completed_at or entry.updated_at),
        "created_at": entry.created_at.isoformat(),
    }


async def _enrich_visit_group(
    visit_id: str,
    entries: list,
    patient_repo: PatientRepository,
) -> dict:
    """Group entries by visit_id with patient info and all tests."""
    if not entries:
        return None

    first = entries[0]
    base = await _enrich_entry(first, patient_repo)

    base["tests"] = [
        {
            "id": str(e.id),
            "service_code": e.service_code,
            "service_name": e.service_name,
            "token_number": e.token_number,
            "status": e.status.value if e.status else "?",
            "status_display": e.status_display,
        }
        for e in entries
    ]
    return base


class DoctorQueueUseCase(BaseUseCase):
    """Use case for the Doctor's full workspace.

    Returns:
        - Consultation queue: WAITING + CALLED entries grouped by visit
        - Pending review: COMPLETED entries grouped by visit
        - Ready for delivery: REPORT_READY entries grouped by visit
        - Combined stats
    """

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

    async def execute(self, command: Command) -> Result:
        dto = command.data
        limit = dto.get("limit", 100)

        try:
            # Fetch all three queues
            waiting = await self._queue_repo.list_by_status(
                status="WAITING", limit=limit
            )
            called = await self._queue_repo.list_by_status(
                status="CALLED", limit=limit
            )
            completed = await self._queue_repo.list_by_status(
                status="COMPLETED", limit=limit
            )
            report_ready = await self._queue_repo.list_by_status(
                status="REPORT_READY", limit=limit
            )

            # Group consultation queue (WAITING + CALLED) by visit_id
            consultation_entries = waiting + called
            consultation_by_visit: dict[str, list] = {}
            for e in consultation_entries:
                consultation_by_visit.setdefault(e.visit_id, []).append(e)

            consultation_queue = []
            for visit_id, entries in consultation_by_visit.items():
                grouped = await _enrich_visit_group(visit_id, entries, self._patient_repo)
                if grouped:
                    consultation_queue.append(grouped)

            # Sort consultation: CALLED first, then WAITING by token
            def _sort_key(g):
                has_called = any(t["status"] == "CALLED" for t in g.get("tests", []))
                return (0 if has_called else 1, g.get("token_number", 0))
            consultation_queue.sort(key=_sort_key)

            # Group completed by visit
            completed_by_visit: dict[str, list] = {}
            for e in completed:
                completed_by_visit.setdefault(e.visit_id, []).append(e)
            pending_review = []
            for visit_id, entries in completed_by_visit.items():
                grouped = await _enrich_visit_group(visit_id, entries, self._patient_repo)
                if grouped:
                    pending_review.append(grouped)

            # Group report_ready by visit
            ready_by_visit: dict[str, list] = {}
            for e in report_ready:
                ready_by_visit.setdefault(e.visit_id, []).append(e)
            ready_for_delivery = []
            for visit_id, entries in ready_by_visit.items():
                grouped = await _enrich_visit_group(visit_id, entries, self._patient_repo)
                if grouped:
                    ready_for_delivery.append(grouped)

            # Flatten for simple entry list (used by existing doctor dashboard)
            def _flatten(groups):
                flat = []
                for g in groups:
                    for t in g.get("tests", []):
                        flat.append({
                            **{k: g[k] for k in ("id", "visit_id", "patient_id", "patient_uuid", "patient_name", "age", "gender", "phone", "blood_group", "notes", "alert_message")},
                            **t,
                            "department": g.get("department", ""),
                            "room": g.get("room", ""),
                            "created_by": g.get("created_by", ""),
                            "called_at": g.get("called_at"),
                            "started_at": g.get("started_at"),
                            "completed_at": g.get("completed_at"),
                            "report_ready_at": g.get("report_ready_at"),
                            "elapsed_minutes": g.get("elapsed_minutes"),
                            "created_at": g.get("created_at"),
                        })
                return flat

            return Result.ok(
                data={
                    "stats": {
                        "consultation": len(consultation_queue),
                        "pending_review": len(pending_review),
                        "ready_for_delivery": len(ready_for_delivery),
                        "total": len(consultation_queue) + len(pending_review) + len(ready_for_delivery),
                    },
                    "consultation_queue": consultation_queue,
                    "pending_review": pending_review,
                    "ready_for_delivery": ready_for_delivery,
                    "pending_review_flat": _flatten(pending_review),
                    "ready_for_delivery_flat": _flatten(ready_for_delivery),
                },
            )

        except Exception as exc:
            return Result.fail(
                error=str(exc),
                code="DOCTOR_500",
            )
