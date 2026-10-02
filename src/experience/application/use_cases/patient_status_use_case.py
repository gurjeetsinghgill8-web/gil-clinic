"""Experience Engine — Patient Status Use Case.

Reads patient test statuses from the Queue Engine
and returns enriched status data with wait times and ETA for the PWA dashboard.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from src.application.common.base_use_case import BaseUseCase
from src.application.common.command import Command
from src.application.common.result import Result
from src.application.common.exceptions import NotFoundError
from src.infrastructure.clinic.settings_provider import get_clinic_settings

if TYPE_CHECKING:
    from src.domain.patient.ports.patient_repository import PatientRepository
    from src.domain.queue.ports.queue_repository import QueueRepository
    from src.domain.queue.entities.queue_entry import QueueEntry


# Status flow order for display
STATUS_ORDER = ["waiting", "called", "in_progress", "completed", "report_ready", "delivered"]

STATUS_DISPLAY = {
    "waiting":       "🟡 Waiting",
    "called":        "🔵 Called",
    "in_progress":   "🟠 In Progress",
    "completed":     "✅ Completed",
    "report_ready":  "📋 Report Ready",
    "delivered":     "📄 Delivered",
}

def _get_service_attr(service_code: str, attr: str, default: Any) -> Any:
    """Get a service attribute from the dynamic service provider.

    Args:
        service_code: The service code (e.g., "ECG").
        attr: The attribute name (e.g., "avg_test_time", "room_name").
        default: Default value if not found.

    Returns:
        The attribute value or default.
    """
    try:
        from src.infrastructure.clinic.department_provider import get_service_by_code
        svc = get_service_by_code(service_code)
        if svc:
            return getattr(svc, attr, default)
    except Exception:
        pass
    return default


def _get_hospital_info() -> dict[str, str]:
    """Get hospital branding info from clinic settings."""
    cs = get_clinic_settings()
    return {"name": cs.name, "specialty": cs.specialty}


class PatientStatusUseCase(BaseUseCase):
    """Use case for retrieving patient status and test information.

    Returns enriched test data with wait times, status display,
    and estimated completion times for the PWA dashboard.
    Now reads from Queue Engine for real-time queue positions.
    """

    def __init__(
        self,
        patient_repo: PatientRepository,
        queue_repo: QueueRepository | None = None,
    ) -> None:
        super().__init__()
        self._patient_repo = patient_repo
        self._queue_repo = queue_repo

    async def authorize(self, command: Command) -> None:
        """Patient status is accessible via session token."""
        pass

    async def execute(self, command: Command) -> Result:
        """Execute patient status retrieval.

        Args:
            command: Command with patient_uuid.

        Returns:
            Result with full status data for the PWA dashboard.
        """
        dto = command.data
        patient_uuid = dto.get("patient_uuid", "")

        try:
            # Load patient aggregate
            patient = await self._patient_repo.get_by_id(patient_uuid)
            if not patient:
                raise NotFoundError(
                    message="Patient not found.",
                )

            # Build status response with real queue data
            status_data = await self._build_status_response(patient, patient_uuid)

            return Result.ok(
                data=status_data,
                message="Status retrieved successfully",
            )

        except NotFoundError as exc:
            return Result.fail(
                error=str(exc),
                code=exc.code,
                details=exc.details,
            )

    async def _build_status_response(
        self, patient, patient_uuid: str
    ) -> dict[str, Any]:
        """Build the full status response dict with real queue data.

        Args:
            patient: Patient aggregate.
            patient_uuid: UUID string for fetching queue entries.

        Returns:
            Status response dict with tests array.
        """
        now = datetime.now(timezone.utc)

        # Fetch queue entries for this patient
        tests_data: list[dict[str, Any]] = []
        queue_entries: list[QueueEntry] = []
        if self._queue_repo:
            try:
                queue_entries = await self._queue_repo.list_patient_queue(
                    patient_uuid
                )
            except Exception:
                queue_entries = []

        # Enrich each queue entry with wait time and ETA
        for entry in queue_entries:
            status_lower = entry.status.value.lower() if entry.status else "waiting"
            status_display = STATUS_DISPLAY.get(status_lower, status_lower)

            # Calculate queue position (number of entries ahead in same service)
            queue_position = 0
            wait_minutes = 0
            expected_time = "Now / अभी"

            if status_lower in ("waiting", "called") and entry.service_code:
                try:
                    queue_depth = await self._queue_repo.get_queue_depth(
                        entry.service_code
                    )
                    # Our position is how many are ahead of us
                    # For simplicity, use the token gap
                    queue_position = max(0, queue_depth)

                    wait_minutes = self.calculate_wait_time(
                        entry.service_code, queue_position
                    )
                    expected_time = self.calculate_expected_time(
                        entry.service_code, queue_position
                    )
                except Exception:
                    pass

            tests_data.append({
                "id": str(entry.id),
                "test_name": entry.service_name,
                "service_code": entry.service_code,
                "status": status_lower,
                "status_display": status_display,
                "token_number": entry.token_number,
                "queue_position": queue_position,
                "room": entry.room,
                "wait_minutes": wait_minutes,
                "expected_time": expected_time,
                "called_at": entry.called_at.isoformat() if entry.called_at else None,
                "started_at": entry.started_at.isoformat() if entry.started_at else None,
                "completed_at": entry.completed_at.isoformat() if entry.completed_at else None,
            })

        response = {
            "patient": {
                "patient_id": patient.patient_id,
                "name": patient.demographics.name,
                "age": patient.demographics.age,
                "gender": patient.demographics.gender,
                "phone": patient.contact.phone[-4:],
            },
            "visit": {
                "total_visits": patient.total_visits,
                "last_visit_at": patient.last_visit_at.isoformat()
                if patient.last_visit_at else None,
                "is_first_visit": patient.is_first_visit,
            },
            "tests": tests_data,
            "hospital": _get_hospital_info(),
            "timestamp": now.isoformat(),
        }

        return response

    @staticmethod
    def calculate_wait_time(test_name: str, queue_position: int) -> int:
        """Calculate estimated wait time in minutes.

        Args:
            test_name: Name of the test (service code).
            queue_position: Current position in queue.

        Returns:
            Wait time in minutes.
        """
        avg_time = _get_service_attr(test_name, "avg_test_time", 10)
        return max(queue_position - 1, 0) * avg_time

    @staticmethod
    def calculate_expected_time(test_name: str, queue_position: int) -> str:
        """Calculate expected time string.

        Args:
            test_name: Name of the test.
            queue_position: Current position in queue.

        Returns:
            Formatted time string like "~3:45 PM" or "Now / अभी".
        """
        wait_minutes = PatientStatusUseCase.calculate_wait_time(
            test_name, queue_position
        )
        if wait_minutes <= 0:
            return "Now / अभी"
        expected = datetime.now() + __import__("datetime").timedelta(
            minutes=wait_minutes
        )
        hour = expected.hour
        ampm = "AM" if hour < 12 else "PM"
        hour12 = hour if 1 <= hour <= 12 else (hour - 12 if hour > 12 else 12)
        return f"~{hour12}:{expected.strftime('%M')} {ampm}"
