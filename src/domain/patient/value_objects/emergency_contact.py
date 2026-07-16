"""EmergencyContact value object for the Patient Engine."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EmergencyContact:
    """Immutable emergency contact information.

    Attributes:
        name: Full name of emergency contact person.
        relationship: e.g., 'spouse', 'parent', 'sibling'.
        phone: 10-digit mobile number.
    """

    name: str
    relationship: str
    phone: str

    @classmethod
    def create(cls, name: str, relationship: str, phone: str) -> EmergencyContact:
        if not phone.isdigit() or len(phone) != 10:
            raise ValueError(f"Emergency contact phone must be 10 digits, got '{phone}'")
        return cls(name=name, relationship=relationship, phone=phone)

    def __repr__(self) -> str:
        return f"<EmergencyContact {self.name} ({self.relationship})>"
