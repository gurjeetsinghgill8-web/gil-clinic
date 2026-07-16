"""Patient Status value object.

Tracks the patient's overall lifecycle status.
This is derived from the active visit's test statuses in the Queue Engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PatientLifecycleStatus(str, Enum):
    """Top-level patient lifecycle states.

    ACTIVE — Patient has been seen recently and may have active visits.
    INACTIVE — No activity for a configurable period (default 90 days).
    BLOCKED — Flagged by admin for abuse / policy violation.
    MERGED — Duplicate record, merged into another patient.
    """

    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"
    MERGED = "merged"

    @property
    def display_name(self) -> str:
        names = {
            "active": "Active",
            "inactive": "Inactive",
            "blocked": "Blocked",
            "merged": "Merged",
        }
        return names[self.value]

    @property
    def icon(self) -> str:
        icons = {
            "active": "🟢",
            "inactive": "⚪",
            "blocked": "🔴",
            "merged": "🔀",
        }
        return icons[self.value]


@dataclass(frozen=True)
class PatientStatus:
    """Immutable patient status value object.

    Attributes:
        status: Current lifecycle status.
        reason: Optional reason if blocked/merged.
    """

    status: PatientLifecycleStatus = PatientLifecycleStatus.ACTIVE
    reason: str | None = None

    @classmethod
    def active(cls) -> PatientStatus:
        return cls(status=PatientLifecycleStatus.ACTIVE)

    @classmethod
    def inactive(cls) -> PatientStatus:
        return cls(status=PatientLifecycleStatus.INACTIVE)

    @classmethod
    def blocked(cls, reason: str) -> PatientStatus:
        return cls(status=PatientLifecycleStatus.BLOCKED, reason=reason)

    @classmethod
    def merged(cls, reason: str) -> PatientStatus:
        return cls(status=PatientLifecycleStatus.MERGED, reason=reason)

    @property
    def is_active(self) -> bool:
        return self.status == PatientLifecycleStatus.ACTIVE

    @property
    def can_visit(self) -> bool:
        """Check if patient can register for a new visit."""
        return self.status in (PatientLifecycleStatus.ACTIVE, PatientLifecycleStatus.INACTIVE)

    def __repr__(self) -> str:
        status_str = f"{self.status.icon} {self.status.display_name}"
        if self.reason:
            status_str += f" ({self.reason})"
        return f"<PatientStatus {status_str}>"
