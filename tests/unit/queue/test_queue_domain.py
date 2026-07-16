"""Unit tests for Queue Lite domain layer.

Tests cover:
- QueueEntry creation with factory method
- All status transitions (valid)
- Invalid transition rejection
- Service naming and room mapping
- Terminal vs active state properties
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest

from src.domain.queue.entities.queue_entry import (
    QueueEntry,
    SERVICE_NAMES,
    ROOM_MAPPINGS,
    AVG_TEST_TIME_MINUTES,
)
from src.domain.queue.value_objects.queue_status import QueueStatus


class TestQueueStatus:
    """QueueStatus enum behavior."""

    def test_valid_transitions(self):
        """Verify all allowed transitions."""
        assert QueueStatus.WAITING.can_transition_to(QueueStatus.CALLED)
        assert QueueStatus.WAITING.can_transition_to(QueueStatus.CANCELLED)
        assert QueueStatus.WAITING.can_transition_to(QueueStatus.NO_SHOW)

        assert QueueStatus.CALLED.can_transition_to(QueueStatus.IN_PROGRESS)
        assert QueueStatus.CALLED.can_transition_to(QueueStatus.WAITING)
        assert QueueStatus.CALLED.can_transition_to(QueueStatus.CANCELLED)
        assert QueueStatus.CALLED.can_transition_to(QueueStatus.NO_SHOW)

        assert QueueStatus.IN_PROGRESS.can_transition_to(QueueStatus.COMPLETED)
        assert QueueStatus.IN_PROGRESS.can_transition_to(QueueStatus.CANCELLED)

        assert QueueStatus.COMPLETED.can_transition_to(QueueStatus.REPORT_READY)

        assert QueueStatus.REPORT_READY.can_transition_to(QueueStatus.DELIVERED)

    def test_invalid_transitions(self):
        """Verify disallowed transitions raise on attempt."""
        # WAITING cannot skip to IN_PROGRESS
        assert not QueueStatus.WAITING.can_transition_to(QueueStatus.IN_PROGRESS)
        # Terminal states cannot transition
        assert not QueueStatus.DELIVERED.can_transition_to(QueueStatus.WAITING)
        assert not QueueStatus.CANCELLED.can_transition_to(QueueStatus.WAITING)
        assert not QueueStatus.NO_SHOW.can_transition_to(QueueStatus.WAITING)
        # COMPLETED cannot go back to IN_PROGRESS
        assert not QueueStatus.COMPLETED.can_transition_to(QueueStatus.IN_PROGRESS)

    def test_active_statuses(self):
        """Verify which statuses are considered active."""
        assert QueueStatus.WAITING.is_active
        assert QueueStatus.CALLED.is_active
        assert QueueStatus.IN_PROGRESS.is_active
        # COMPLETED + REPORT_READY are not 'active' — patient is done waiting
        assert not QueueStatus.COMPLETED.is_active
        assert not QueueStatus.REPORT_READY.is_active
        assert not QueueStatus.DELIVERED.is_active
        assert not QueueStatus.CANCELLED.is_active
        assert not QueueStatus.NO_SHOW.is_active

    def test_terminal_statuses(self):
        """Verify terminal statuses."""
        assert QueueStatus.DELIVERED.is_terminal
        assert QueueStatus.CANCELLED.is_terminal
        assert QueueStatus.NO_SHOW.is_terminal
        assert not QueueStatus.WAITING.is_terminal

    def test_display_values(self):
        """Verify display names and icons."""
        assert "Called" in QueueStatus.CALLED.display
        assert "In Progress" in QueueStatus.IN_PROGRESS.display_name


class TestQueueEntryCreate:
    """QueueEntry creation via factory method."""

    def test_create_basic(self):
        """Create a basic queue entry from factory."""
        entry = QueueEntry.create(
            visit_id="VIS-20260714-123456",
            patient_id="CQ-20260714-001",
            patient_uuid="550e8400-e29b-41d4-a716-446655440000",
            patient_name="Rahul Sharma",
            service_code="ECG",
            token_number=5,
            created_by="reception",
        )
        assert entry.status == QueueStatus.WAITING
        assert entry.visit_id == "VIS-20260714-123456"
        assert entry.token_number == 5
        assert entry.service_code == "ECG"
        assert entry.service_name == "Electrocardiogram"
        assert entry.room == "ECG Room 1"
        assert entry.department == "Cardiology"
        assert entry.is_active
        assert not entry.is_terminal
        assert isinstance(entry.id, UUID)

    def test_create_with_echo(self):
        """Create entry for Echo test — verify room and name."""
        entry = QueueEntry.create(
            visit_id="VIS-20260714-123456",
            patient_id="CQ-20260714-001",
            patient_uuid="550e8400-e29b-41d4-a716-446655440000",
            patient_name="Priya Singh",
            service_code="Echo",
            token_number=3,
            created_by="reception",
        )
        assert entry.service_name == "Echocardiogram"
        assert entry.room == "Echo Room 1"
        assert entry.token_number == 3

    def test_create_unknown_service(self):
        """Creates entry even for unknown service code."""
        entry = QueueEntry.create(
            visit_id="VIS-20260714-123456",
            patient_id="CQ-20260714-001",
            patient_uuid="550e8400-e29b-41d4-a716-446655440000",
            patient_name="Test",
            service_code="MRI",
            token_number=1,
            created_by="reception",
        )
        assert entry.service_name == "MRI"  # Falls back to code
        assert entry.room == "MRI Room"  # Generic room name

    def test_create_multiple_services(self):
        """Create multiple entries for one visit (multiple tests)."""
        visit_id = "VIS-20260714-999999"
        patient_id = "CQ-20260714-010"
        entries = []
        codes = ["ECG", "Echo", "TMT"]
        for i, code in enumerate(codes):
            entry = QueueEntry.create(
                visit_id=visit_id,
                patient_id=patient_id,
                patient_uuid="550e8400-e29b-41d4-a716-446655440000",
                patient_name="Amit Patel",
                service_code=code,
                token_number=i + 1,
                created_by="reception",
            )
            entries.append(entry)

        assert len(entries) == 3
        assert entries[0].service_code == "ECG"
        assert entries[1].service_code == "Echo"
        assert entries[2].service_code == "TMT"
        # All belong to same visit
        assert all(e.visit_id == visit_id for e in entries)
        # All start WAITING
        assert all(e.status == QueueStatus.WAITING for e in entries)


class TestQueueEntryTransitions:
    """Status transition lifecycle."""

    @pytest.fixture
    def entry(self) -> QueueEntry:
        return QueueEntry.create(
            visit_id="VIS-20260714-000001",
            patient_id="CQ-20260714-001",
            patient_uuid="550e8400-e29b-41d4-a716-446655440000",
            patient_name="Test Patient",
            service_code="ECG",
            token_number=1,
            created_by="reception",
        )

    def test_full_lifecycle(self, entry: QueueEntry):
        """Walk through complete lifecycle: WAITING → DELIVERED."""
        entry.call("tech1")
        assert entry.status == QueueStatus.CALLED
        assert entry.called_at is not None

        entry.start("tech1")
        assert entry.status == QueueStatus.IN_PROGRESS
        assert entry.started_at is not None

        entry.complete("tech1")
        assert entry.status == QueueStatus.COMPLETED
        assert entry.completed_at is not None

        entry.mark_report_ready("tech1")
        assert entry.status == QueueStatus.REPORT_READY
        assert entry.report_ready_at is not None

        entry.deliver("tech1")
        assert entry.status == QueueStatus.DELIVERED
        assert entry.delivered_at is not None
        assert entry.is_terminal

    def test_recall_to_waiting(self, entry: QueueEntry):
        """Call → Recall to waiting."""
        entry.call("tech1")
        entry.recall_to_waiting("tech1")
        assert entry.status == QueueStatus.WAITING
        assert entry.called_at is None  # Reset

    def test_cancel_from_waiting(self, entry: QueueEntry):
        """Cancel a waiting entry."""
        entry.cancel("reception", "Patient left")
        assert entry.status == QueueStatus.CANCELLED
        assert entry.is_terminal

    def test_cancel_from_in_progress(self, entry: QueueEntry):
        """Cancel during test."""
        entry.call("tech1")
        entry.start("tech1")
        entry.cancel("tech1", "Equipment failure")
        assert entry.status == QueueStatus.CANCELLED

    def test_no_show(self, entry: QueueEntry):
        """Mark as no-show."""
        entry.call("tech1")
        entry.mark_no_show("tech1")
        assert entry.status == QueueStatus.NO_SHOW
        assert entry.is_terminal

    def test_invalid_transition_raises(self, entry: QueueEntry):
        """Cannot complete directly from waiting."""
        with pytest.raises(ValueError, match="Cannot transition"):
            entry.complete("tech1")

    def test_invalid_transition_called_to_complete(self, entry: QueueEntry):
        """Cannot skip IN_PROGRESS."""
        entry.call("tech1")
        with pytest.raises(ValueError, match="Cannot transition"):
            entry.complete("tech1")

    def test_transition_from_terminal_raises(self, entry: QueueEntry):
        """Cannot call a delivered entry."""
        entry.call("tech1")
        entry.start("tech1")
        entry.complete("tech1")
        entry.mark_report_ready("tech1")
        entry.deliver("tech1")
        with pytest.raises(ValueError, match="Cannot transition"):
            entry.call("tech1")

    def test_version_increments_on_transition(self, entry: QueueEntry):
        """Version should increase on each status change."""
        v1 = entry.version
        entry.call("tech1")
        assert entry.version == v1 + 1
        entry.start("tech1")
        assert entry.version == v1 + 2


class TestServiceMetadata:
    """Service name, room, and time mappings."""

    def test_all_services_have_names(self):
        """Every service code has a display name."""
        codes = ["ECG", "Echo", "TMT", "Holter", "ABPM", "OPD", "X-Ray", "Ultrasound"]
        for code in codes:
            assert code in SERVICE_NAMES
            assert isinstance(SERVICE_NAMES[code], str)
            assert len(SERVICE_NAMES[code]) > 0

    def test_all_services_have_rooms(self):
        """Every service code has a room assignment."""
        codes = ["ECG", "Echo", "TMT", "Holter", "ABPM", "OPD", "X-Ray", "Ultrasound"]
        for code in codes:
            assert code in ROOM_MAPPINGS
            assert "Room" in ROOM_MAPPINGS[code]

    def test_all_services_have_avg_time(self):
        """Every service code has an estimated test time."""
        codes = ["ECG", "Echo", "TMT", "Holter", "ABPM", "OPD", "X-Ray", "Ultrasound"]
        for code in codes:
            assert code in AVG_TEST_TIME_MINUTES
            assert AVG_TEST_TIME_MINUTES[code] > 0
