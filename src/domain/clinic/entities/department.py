"""Department aggregate root for the Clinic Engine.

Represents a clinic department (e.g., Cardiology, Ultrasound, OPD).
Administrators can add, remove, or rename departments dynamically.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4


@dataclass
class Department:
    """A clinic department that groups related services/tests.

    Attributes:
        code: Short unique code (e.g., "CARDIO", "US", "OPD").
        name: Display name (e.g., "Cardiology", "Ultrasound").
        description: Optional description of the department.
        is_active: Whether this department is currently active.
        display_order: Sort order for display (lower = first).
        created_at: When this department was created.
        updated_at: When this department was last modified.
    """

    code: str
    name: str
    description: str = ""
    is_active: bool = True
    display_order: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def create(
        cls,
        code: str,
        name: str,
        description: str = "",
        display_order: int = 0,
    ) -> Department:
        """Factory method to create a new Department.

        Args:
            code: Short unique code (uppercase, no spaces).
            name: Display name.
            description: Optional description.
            display_order: Sort order.

        Returns:
            A new Department instance.
        """
        now = datetime.now(timezone.utc)
        return cls(
            code=code.upper().replace(" ", "_"),
            name=name,
            description=description,
            display_order=display_order,
            created_at=now,
            updated_at=now,
        )

    def update(
        self,
        name: str | None = None,
        description: str | None = None,
        is_active: bool | None = None,
        display_order: int | None = None,
    ) -> None:
        """Update department fields in-place.

        Args:
            name: New display name (or None to keep).
            description: New description (or None to keep).
            is_active: New active status (or None to keep).
            display_order: New sort order (or None to keep).
        """
        if name is not None:
            self.name = name
        if description is not None:
            self.description = description
        if is_active is not None:
            self.is_active = is_active
        if display_order is not None:
            self.display_order = display_order
        self.updated_at = datetime.now(timezone.utc)

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON storage."""
        return {
            "code": self.code,
            "name": self.name,
            "description": self.description,
            "is_active": self.is_active,
            "display_order": self.display_order,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Department:
        """Deserialize from dictionary.

        Args:
            data: Dictionary with department fields.

        Returns:
            A Department instance.
        """
        return cls(
            code=data.get("code", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            is_active=data.get("is_active", True),
            display_order=data.get("display_order", 0),
            created_at=_parse_dt(data.get("created_at")),
            updated_at=_parse_dt(data.get("updated_at")),
        )

    def __repr__(self) -> str:
        return (
            f"<Department code={self.code} "
            f"name={self.name} "
            f"active={self.is_active}>"
        )


def _parse_dt(value: str | None) -> datetime | None:
    """Parse an ISO datetime string, returning None if empty."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None
