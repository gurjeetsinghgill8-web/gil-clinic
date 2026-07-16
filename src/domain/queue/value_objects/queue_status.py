"""QueueEntry status value object.

Strictly defined status lifecycle for queue entries.
"""

from __future__ import annotations

from enum import Enum


class QueueStatus(str, Enum):
    """Queue entry lifecycle states.

    WAITING → CALLED → IN_PROGRESS → COMPLETED → REPORT_READY → DELIVERED
    Any state → CANCELLED | NO_SHOW
    """

    WAITING = "WAITING"
    CALLED = "CALLED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    REPORT_READY = "REPORT_READY"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    NO_SHOW = "NO_SHOW"

    @property
    def display_name(self) -> str:
        return {
            "WAITING": "Waiting",
            "CALLED": "Called",
            "IN_PROGRESS": "In Progress",
            "COMPLETED": "Completed",
            "REPORT_READY": "Report Ready",
            "DELIVERED": "Delivered",
            "CANCELLED": "Cancelled",
            "NO_SHOW": "No Show",
        }[self.value]

    @property
    def icon(self) -> str:
        return {
            "WAITING": "🟡",
            "CALLED": "🔵",
            "IN_PROGRESS": "🟠",
            "COMPLETED": "✅",
            "REPORT_READY": "📋",
            "DELIVERED": "📄",
            "CANCELLED": "❌",
            "NO_SHOW": "🚫",
        }[self.value]

    @property
    def display(self) -> str:
        return f"{self.icon} {self.display_name}"

    def can_transition_to(self, target: QueueStatus) -> bool:
        """Check if a status transition is valid."""
        ALLOWED: dict[QueueStatus, set[QueueStatus]] = {
            QueueStatus.WAITING:       {QueueStatus.CALLED, QueueStatus.CANCELLED, QueueStatus.NO_SHOW},
            QueueStatus.CALLED:        {QueueStatus.IN_PROGRESS, QueueStatus.WAITING, QueueStatus.CANCELLED, QueueStatus.NO_SHOW},
            QueueStatus.IN_PROGRESS:   {QueueStatus.COMPLETED, QueueStatus.CANCELLED},
            QueueStatus.COMPLETED:     {QueueStatus.REPORT_READY, QueueStatus.IN_PROGRESS},
            QueueStatus.REPORT_READY:  {QueueStatus.DELIVERED},
            QueueStatus.DELIVERED:     set(),
            QueueStatus.CANCELLED:     set(),
            QueueStatus.NO_SHOW:       set(),
        }
        return target in ALLOWED.get(self, set())

    @property
    def is_active(self) -> bool:
        """Check if this status represents an active queue entry."""
        return self in {
            QueueStatus.WAITING, QueueStatus.CALLED, QueueStatus.IN_PROGRESS,
        }

    @property
    def is_terminal(self) -> bool:
        """Check if this is a terminal (end) state."""
        return self in {
            QueueStatus.DELIVERED, QueueStatus.CANCELLED, QueueStatus.NO_SHOW,
        }
