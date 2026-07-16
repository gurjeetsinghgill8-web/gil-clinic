"""ContactInfo value object for the Patient Engine.

Encapsulates patient contact details.
Phone is the primary identifier for patient lookup.
Email is optional and encrypted at rest.
"""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class ContactInfo:
    """Immutable patient contact information.

    Attributes:
        phone: 10-digit mobile number (primary identifier).
        phone_hash: SHA-256 hex digest of phone for lookups.
        email: Optional email address (encrypted at rest).
        address: Optional residential address.
    """

    phone: str
    phone_hash: str
    email: str | None = None
    address: str | None = None

    def __post_init__(self) -> None:
        """Validate phone format on creation."""
        if not re.match(r"^\d{10}$", self.phone):
            raise ValueError(f"Phone must be exactly 10 digits, got '{self.phone}'")
        if self.email and "@" not in self.email:
            raise ValueError(f"Invalid email format: '{self.email}'")

    @classmethod
    def create(cls, phone: str, phone_hash: str, email: str | None = None, address: str | None = None) -> ContactInfo:
        """Factory method with validation."""
        return cls(phone=phone, phone_hash=phone_hash, email=email, address=address)

    def __repr__(self) -> str:
        return f"<ContactInfo phone=******{self.phone[-4:]}>"
