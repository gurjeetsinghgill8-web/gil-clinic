"""Queue Entry repository interface (port)."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from src.domain.queue.entities.queue_entry import QueueEntry


class QueueRepository(Protocol):
    """Interface for QueueEntry persistence."""

    async def save(self, entry: QueueEntry) -> None:
        """Persist a new or updated queue entry."""
        ...

    async def save_many(self, entries: list[QueueEntry]) -> None:
        """Persist multiple queue entries in batch."""
        ...

    async def get_by_id(self, entry_uuid: str) -> QueueEntry | None:
        """Get a queue entry by its UUID."""
        ...

    async def get_active_by_patient(
        self, patient_uuid: str
    ) -> list[QueueEntry]:
        """Get all active (non-terminal) queue entries for a patient."""
        ...

    async def list_by_department(
        self,
        department: str,
        status_filter: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[QueueEntry]:
        """List queue entries for a department, with optional status filter."""
        ...

    async def list_by_visit(self, visit_id: str) -> list[QueueEntry]:
        """List all queue entries for a specific visit."""
        ...

    async def get_next_token_number(self, service_code: str, date_prefix: str) -> int:
        """Get the next sequential token number for a service today."""
        ...

    async def get_queue_depth(self, service_code: str) -> int:
        """Get the number of WAITING entries for a service."""
        ...

    async def count_by_status(self, department: str, status: str) -> int:
        """Count entries in a given status for a department."""
        ...

    async def list_by_status(
        self,
        status: str,
        offset: int = 0,
        limit: int = 100,
    ) -> list[QueueEntry]:
        """List queue entries by status across all departments (doctor view)."""
        ...

    async def list_patient_queue(self, patient_uuid: str) -> list[QueueEntry]:
        """Get all queue entries for a patient (patient PWA view)."""
        ...

    # ------------------------------------------------------------------
    # Analytics / Manager Dashboard
    # ------------------------------------------------------------------

    async def count_created_between(
        self, start: datetime, end: datetime
    ) -> int:
        """Count queue entries created between two datetimes.

        Args:
            start: Start of range (inclusive).
            end: End of range (inclusive).

        Returns:
            Total count of entries created in the date range.
        """
        ...

    async def get_service_stats(
        self, date_from: datetime, date_to: datetime
    ) -> list[dict]:
        """Per-service stats within a date range.

        Returns list of dicts with keys:
            service_code, count, avg_wait_minutes

        Args:
            date_from: Start of range.
            date_to: End of range.

        Returns:
            List of service stat dicts.
        """
        ...

    async def get_daily_counts(
        self, days: int = 7
    ) -> list[dict]:
        """Daily creation and completion counts for the last N days.

        Returns list of dicts with keys:
            date (str YYYY-MM-DD), created (int), completed (int)

        Args:
            days: Number of days to look back (default 7).

        Returns:
            List of daily stat dicts, oldest first.
        """
        ...

    # ------------------------------------------------------------------
    # Alert system
    # ------------------------------------------------------------------

    async def set_alert(self, entry_id: str, message: str) -> None:
        """Set pending_alert flag and message on a queue entry."""
        ...

    async def check_alert(self, entry_id: str) -> tuple[bool, str | None]:
        """Check if a queue entry has a pending alert.
        
        Returns:
            Tuple of (has_alert: bool, alert_message: str | None).
        """
        ...

    async def clear_alert(self, entry_id: str) -> None:
        """Clear the pending_alert flag on a queue entry."""
        ...
