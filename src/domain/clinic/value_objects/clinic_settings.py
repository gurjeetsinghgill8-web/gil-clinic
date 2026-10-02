"""ClinicSettings — domain value object.

Represents the clinic's branding and contact information.
This is a singleton config — there is exactly one clinic.

Default values are "GIL CLINIC" with Cardiology specialty.
These can be overridden via the admin API (persisted to JSON file)
or via environment variables.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ClinicSettings:
    """Clinic branding and contact information.

    Attributes:
        name: Clinic name (default: "GIL CLINIC").
        specialty: Clinic specialty (default: "Cardiology").
        logo_emoji: Emoji used as logo (default: "🏥").
        phone: Contact phone number.
        address: Clinic address.
        doctor_name: Doctor's name for display on token slips, etc.
    """

    name: str = "GIL CLINIC"
    specialty: str = "Cardiology"
    logo_emoji: str = "🏥"
    phone: str = ""
    address: str = ""
    doctor_name: str = "Dr. Gurjeet Singh Gill"

    @classmethod
    def defaults(cls) -> ClinicSettings:
        """Get the default clinic settings.

        Returns:
            ClinicSettings with factory defaults.
        """
        return cls()

    def to_dict(self) -> dict[str, str]:
        """Convert to a flat dict for JSON serialization.

        Returns:
            Dict with all setting fields.
        """
        return {
            "name": self.name,
            "specialty": self.specialty,
            "logo_emoji": self.logo_emoji,
            "phone": self.phone,
            "address": self.address,
            "doctor_name": self.doctor_name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> ClinicSettings:
        """Create from a flat dict (from JSON or API).

        Args:
            data: Dict with setting fields. Missing fields use defaults.

        Returns:
            New ClinicSettings instance.
        """
        return cls(
            name=data.get("name", "GIL CLINIC"),
            specialty=data.get("specialty", "Cardiology"),
            logo_emoji=data.get("logo_emoji", "🏥"),
            phone=data.get("phone", ""),
            address=data.get("address", ""),
            doctor_name=data.get("doctor_name", "Dr. Gurjeet Singh Gill"),
        )

    def merge(self, overrides: dict[str, str]) -> ClinicSettings:
        """Create a new ClinicSettings with only the provided fields overridden.

        Args:
            overrides: Partial dict of fields to update.

        Returns:
            New ClinicSettings with merged values.
        """
        merged = self.to_dict()
        merged.update(overrides)
        return ClinicSettings.from_dict(merged)

    def __repr__(self) -> str:
        return (
            f"<ClinicSettings name='{self.name}' "
            f"specialty='{self.specialty}' "
            f"phone='{self.phone}'>"
        )
