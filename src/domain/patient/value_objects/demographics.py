"""Demographics value object for the Patient Engine.

Encapsulates patient demographic and biometric information.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Demographics:
    """Immutable patient demographics.

    Attributes:
        name: Full name of the patient.
        age: Age in years (1-150).
        gender: 'male', 'female', 'other'.
        date_of_birth: Optional precise DOB.
        blood_group: Optional blood group (A+, B+, O+, AB+, etc.).
    """

    name: str
    age: int
    gender: str
    date_of_birth: date | None = None
    blood_group: str | None = None

    def __post_init__(self) -> None:
        """Validate demographics on creation."""
        if not (1 <= self.age <= 150):
            raise ValueError(f"Age must be between 1 and 150, got {self.age}")
        if self.gender not in ("male", "female", "other"):
            raise ValueError(f"Gender must be 'male', 'female', or 'other', got '{self.gender}'")
        if self.blood_group and self.blood_group not in (
            "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-",
        ):
            raise ValueError(f"Invalid blood group: '{self.blood_group}'")

    @classmethod
    def create(
        cls,
        name: str,
        age: int,
        gender: str,
        date_of_birth: date | None = None,
        blood_group: str | None = None,
    ) -> Demographics:
        return cls(name=name, age=age, gender=gender, date_of_birth=date_of_birth, blood_group=blood_group)

    def __repr__(self) -> str:
        return f"<Demographics {self.name} ({self.age}y/{self.gender})>"
