"""MedicalHistory value object for the Patient Engine.

Encapsulates a single medical history record entry.
A patient can have multiple entries forming their timeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class MedicalHistoryEntry:
    """An individual medical history record.

    Attributes:
        condition: Condition name (e.g., 'Hypertension', 'Diabetes').
        diagnosed_at: When the condition was diagnosed (date string or year).
        notes: Optional notes about the condition.
        is_active: Whether the condition is currently active.
        recorded_at: When this entry was recorded.
    """

    condition: str
    diagnosed_at: str | None = None
    notes: str | None = None
    is_active: bool = True
    recorded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __repr__(self) -> str:
        status = "ACTIVE" if self.is_active else "resolved"
        return f"<MedicalHistoryEntry {self.condition} ({status})>"
