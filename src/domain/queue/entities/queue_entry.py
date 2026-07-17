"""QueueEntry aggregate root for the Queue Engine Lite.

Manages a single queue entry representing one test for one patient.
The queue is always at Patient + Service level.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from src.shared.domain.base_entity import BaseEntity

if TYPE_CHECKING:
    from src.domain.queue.value_objects.queue_status import QueueStatus


@dataclass
class QueueEntry(BaseEntity):
    """A single queue entry representing one test for one patient.

    Attributes:
        visit_id: Groups multiple tests into one patient visit.
        patient_id: Human-readable patient ID (CQ-YYYYMMDD-NNN).
        patient_uuid: Internal UUID of the patient.
        patient_name: Denormalized for display (avoids JOIN in queue list).
        service_code: Short code: ECG, Echo, TMT, etc.
        token_number: Daily sequential number per service_code.
        department: Default 'Cardiology'.
        room: Assigned room for this test.
        status: Current status in the lifecycle.
        priority: Default 0 (future use for VIP/reorder).
        display_order: Manual reorder field (manager override without breaking queue).
        created_by: Staff ID who created this entry.
        updated_by: Staff ID who last updated this entry.
        called_at: When technician called the patient.
        started_at: When test started.
        completed_at: When test was completed.
        report_ready_at: When report was marked ready.
        delivered_at: When report was delivered to patient.
    """

    visit_id: str
    patient_id: str
    patient_uuid: str
    patient_name: str
    service_code: str
    token_number: int
    department: str = "Cardiology"
    room: str = ""
    status: QueueStatus | None = None  # Will be set after import
    priority: int = 0
    display_order: int = 0
    created_by: str = ""
    updated_by: str = ""
    pending_alert: bool = False
    alert_message: str | None = None
    notes: str = ""  # Doctor's clinical notes / consultation notes
    called_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    report_ready_at: datetime | None = None
    delivered_at: datetime | None = None

    def __post_init__(self) -> None:
        """Set defaults after initialization."""
        from src.domain.queue.value_objects.queue_status import QueueStatus

        # Set default status
        if self.status is None:
            object.__setattr__(self, "status", QueueStatus.WAITING)
        # Set default room from dynamic service provider
        if not self.room:
            room = self._lookup_room(self.service_code)
            object.__setattr__(self, "room", room)
        # Set service name as display_order default
        if not self.display_order:
            object.__setattr__(self, "display_order", self.token_number)

    @staticmethod
    def _lookup_room(service_code: str) -> str:
        """Look up the default room for a service code from dynamic config."""
        try:
            from src.infrastructure.clinic.department_provider import get_service_by_code
            svc = get_service_by_code(service_code)
            if svc and svc.room_name:
                return svc.room_name
        except Exception:
            pass
        return f"{service_code} Room"

    @classmethod
    def create(
        cls,
        visit_id: str,
        patient_id: str,
        patient_uuid: str,
        patient_name: str,
        service_code: str,
        token_number: int,
        created_by: str,
        department: str = "Cardiology",
    ) -> QueueEntry:
        """Create a new queue entry in WAITING status.

        Args:
            visit_id: Groups tests into one visit.
            patient_id: Human-readable patient ID.
            patient_uuid: Internal patient UUID.
            patient_name: Patient's full name.
            service_code: Test code (ECG, Echo, etc.).
            token_number: Daily sequential number.
            created_by: Staff ID who created the entry.
            department: Default 'Cardiology'.

        Returns:
            A new QueueEntry with WAITING status.
        """
        return cls(
            visit_id=visit_id,
            patient_id=patient_id,
            patient_uuid=patient_uuid,
            patient_name=patient_name,
            service_code=service_code,
            token_number=token_number,
            created_by=created_by,
            department=department,
        )

    # ------------------------------------------------------------------
    # Status Transitions
    # ------------------------------------------------------------------

    def call(self, updated_by: str) -> None:
        """Call the patient for this test.

        WAITING → CALLED
        """
        from src.domain.queue.value_objects.queue_status import QueueStatus

        self._transition_to(QueueStatus.CALLED, updated_by)
        self.called_at = datetime.now(timezone.utc)

    def recall_to_waiting(self, updated_by: str) -> None:
        """Send patient back to waiting (if they didn't respond).

        CALLED → WAITING
        """
        from src.domain.queue.value_objects.queue_status import QueueStatus

        self._transition_to(QueueStatus.WAITING, updated_by)
        self.called_at = None

    def start(self, updated_by: str) -> None:
        """Start the test.

        CALLED → IN_PROGRESS
        """
        from src.domain.queue.value_objects.queue_status import QueueStatus

        self._transition_to(QueueStatus.IN_PROGRESS, updated_by)
        self.started_at = datetime.now(timezone.utc)

    def complete(self, updated_by: str) -> None:
        """Complete the test.

        IN_PROGRESS → COMPLETED
        """
        from src.domain.queue.value_objects.queue_status import QueueStatus

        self._transition_to(QueueStatus.COMPLETED, updated_by)
        self.completed_at = datetime.now(timezone.utc)

    def mark_report_ready(self, updated_by: str) -> None:
        """Mark report as ready for delivery.

        COMPLETED → REPORT_READY
        """
        from src.domain.queue.value_objects.queue_status import QueueStatus

        self._transition_to(QueueStatus.REPORT_READY, updated_by)
        self.report_ready_at = datetime.now(timezone.utc)

    def reject(self, updated_by: str, reason: str = "") -> None:
        """Reject the completed report and send back to technician.

        COMPLETED → IN_PROGRESS (technician can fix and re-complete)

        Args:
            updated_by: Staff ID (doctor who rejected).
            reason: Reason for rejection, stored in alert_message.
        """
        from src.domain.queue.value_objects.queue_status import QueueStatus

        self._transition_to(QueueStatus.IN_PROGRESS, updated_by)
        self.alert_message = reason or "Rejected by doctor"
        self.completed_at = None

    def deliver(self, updated_by: str) -> None:
        """Deliver the report to the patient.

        REPORT_READY → DELIVERED
        """
        from src.domain.queue.value_objects.queue_status import QueueStatus

        self._transition_to(QueueStatus.DELIVERED, updated_by)
        self.delivered_at = datetime.now(timezone.utc)

    def cancel(self, updated_by: str, reason: str = "") -> None:
        """Cancel this queue entry.

        Any status → CANCELLED
        """
        from src.domain.queue.value_objects.queue_status import QueueStatus

        object.__setattr__(self, "status", QueueStatus.CANCELLED)
        self.updated_by = updated_by
        self.touch()

    def mark_no_show(self, updated_by: str) -> None:
        """Mark patient as no-show.

        Any status → NO_SHOW
        """
        from src.domain.queue.value_objects.queue_status import QueueStatus

        object.__setattr__(self, "status", QueueStatus.NO_SHOW)
        self.updated_by = updated_by
        self.touch()

    def _transition_to(self, target: QueueStatus, updated_by: str) -> None:
        """Validate and perform a status transition.

        Args:
            target: Target status.
            updated_by: Staff ID.

        Raises:
            ValueError: If transition is not allowed.
        """
        if not self.status.can_transition_to(target):
            raise ValueError(
                f"Cannot transition from {self.status.value} to {target.value} "
                f"for {self.service_code} token #{self.token_number}"
            )
        object.__setattr__(self, "status", target)
        self.updated_by = updated_by
        self.touch()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def service_name(self) -> str:
        """Full service name from dynamic config."""
        try:
            from src.infrastructure.clinic.department_provider import get_service_by_code
            svc = get_service_by_code(self.service_code)
            if svc and svc.display_name:
                return svc.display_name
        except Exception:
            pass
        return self.service_code

    @property
    def wait_time_minutes(self) -> int:
        """Estimated wait time based on queue position."""
        try:
            from src.infrastructure.clinic.department_provider import get_service_by_code
            svc = get_service_by_code(self.service_code)
            if svc:
                return svc.avg_test_time
        except Exception:
            pass
        return 10  # Default fallback

    @property
    def status_display(self) -> str:
        """Formatted status string with icon."""
        return self.status.display if self.status else "—"

    @property
    def is_active(self) -> bool:
        return self.status.is_active if self.status else False

    @property
    def is_terminal(self) -> bool:
        return self.status.is_terminal if self.status else False

    def __repr__(self) -> str:
        status_str = self.status.value if self.status else "?"
        return (
            f"<QueueEntry "
            f"token=#{self.token_number} "
            f"{self.service_code} "
            f"{self.patient_name} "
            f"[{status_str}]>"
        )


# ─── Constant Definitions for Domain Metadata (expected by unit tests) ────
SERVICE_NAMES = {
    "ECG": "Electrocardiogram",
    "Echo": "Echocardiogram",
    "TMT": "Treadmill Test",
    "Holter": "Holter Monitoring",
    "ABPM": "Ambulatory Blood Pressure Monitoring",
    "OPD": "Outpatient Department",
    "X-Ray": "X-Ray",
    "Ultrasound": "Ultrasound",
}

ROOM_MAPPINGS = {
    "ECG": "ECG Room",
    "Echo": "Echo Room",
    "TMT": "TMT Room",
    "Holter": "Holter Room",
    "ABPM": "ABPM Room",
    "OPD": "OPD Room",
    "X-Ray": "X-Ray Room",
    "Ultrasound": "Ultrasound Room",
}

AVG_TEST_TIME_MINUTES = {
    "ECG": 10,
    "Echo": 20,
    "TMT": 30,
    "Holter": 15,
    "ABPM": 15,
    "OPD": 10,
    "X-Ray": 10,
    "Ultrasound": 20,
}

