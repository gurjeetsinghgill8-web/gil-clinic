"""Use case: Update clinic settings."""

from __future__ import annotations

from src.application.common.base_use_case import BaseUseCase
from src.application.common.command import Command
from src.application.common.result import Result
from src.infrastructure.clinic.settings_provider import update_clinic_settings


class UpdateClinicSettingsUseCase(BaseUseCase):
    """Updates clinic branding and contact information.

    Only provided fields are updated; others keep their current values.
    Settings are persisted to clinic_settings.json.
    """

    async def authorize(self, command: Command) -> None:
        """Requires admin role — enforced by route middleware."""
        pass

    async def execute(self, command: Command) -> Result:
        """Update clinic settings.

        Args:
            command: Command with optional overrides:
                - name: Clinic name
                - specialty: Clinic specialty
                - logo_emoji: Emoji logo
                - phone: Contact phone
                - address: Clinic address
                - doctor_name: Doctor name

        Returns:
            Result with updated settings dict.
        """
        overrides = command.data or {}
        # Only accept known fields
        valid_fields = {
            "name", "specialty", "logo_emoji",
            "phone", "address", "doctor_name",
        }
        filtered = {k: v for k, v in overrides.items() if k in valid_fields and v is not None}

        if not filtered:
            return Result.fail(
                error="No valid settings fields provided",
                code="INVALID_SETTINGS",
            )

        updated = update_clinic_settings(filtered)

        return Result.ok(
            data=updated.to_dict(),
            message="Clinic settings updated",
        )
