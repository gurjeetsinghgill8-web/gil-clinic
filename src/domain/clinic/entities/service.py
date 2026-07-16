"""Service entity for the Clinic Engine.

Represents a medical test or service offered within a department
(e.g., ECG, Echo, TMT under Cardiology).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class Service:
    """A service/test offered by a department.

    Attributes:
        code: Short unique code (e.g., "ECG", "Echo", "TMT").
        display_name: Full display name (e.g., "Electrocardiogram").
        department_code: FK to Department.code.
        room_name: Default room for this service (e.g., "ECG Room 1").
        avg_test_time: Average duration in minutes.
        is_active: Whether this service is currently offered.
        created_at: When this service was created.
        updated_at: When this service was last modified.
    """

    code: str
    display_name: str
    department_code: str
    room_name: str = ""
    avg_test_time: int = 10
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def create(
        cls,
        code: str,
        display_name: str,
        department_code: str,
        room_name: str = "",
        avg_test_time: int = 10,
    ) -> Service:
        """Factory method to create a new Service.

        Args:
            code: Short unique code (e.g., "ECG").
            display_name: Full display name.
            department_code: Code of the parent department.
            room_name: Default room name.
            avg_test_time: Average test duration in minutes.

        Returns:
            A new Service instance.
        """
        now = datetime.now(timezone.utc)
        return cls(
            code=code,
            display_name=display_name,
            department_code=department_code,
            room_name=room_name,
            avg_test_time=avg_test_time,
            created_at=now,
            updated_at=now,
        )

    def update(
        self,
        display_name: str | None = None,
        room_name: str | None = None,
        avg_test_time: int | None = None,
        is_active: bool | None = None,
    ) -> None:
        """Update service fields in-place.

        Args:
            display_name: New display name.
            room_name: New room name.
            avg_test_time: New average test time in minutes.
            is_active: New active status.
        """
        if display_name is not None:
            self.display_name = display_name
        if room_name is not None:
            self.room_name = room_name
        if avg_test_time is not None:
            self.avg_test_time = avg_test_time
        if is_active is not None:
            self.is_active = is_active
        self.updated_at = datetime.now(timezone.utc)

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON storage."""
        return {
            "code": self.code,
            "display_name": self.display_name,
            "department_code": self.department_code,
            "room_name": self.room_name,
            "avg_test_time": self.avg_test_time,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Service:
        """Deserialize from dictionary.

        Args:
            data: Dictionary with service fields.

        Returns:
            A Service instance.
        """
        return cls(
            code=data.get("code", ""),
            display_name=data.get("display_name", ""),
            department_code=data.get("department_code", ""),
            room_name=data.get("room_name", ""),
            avg_test_time=data.get("avg_test_time", 10),
            is_active=data.get("is_active", True),
            created_at=_parse_dt(data.get("created_at")),
            updated_at=_parse_dt(data.get("updated_at")),
        )

    def __repr__(self) -> str:
        return (
            f"<Service code={self.code} "
            f"name={self.display_name} "
            f"dept={self.department_code} "
            f"room={self.room_name} "
            f"time={self.avg_test_time}min>"
        )


def _parse_dt(value: str | None) -> datetime | None:
    """Parse an ISO datetime string, returning None if empty."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None
