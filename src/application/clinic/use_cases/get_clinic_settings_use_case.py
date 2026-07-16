"""Use case: Get current clinic settings."""

from __future__ import annotations

from src.application.common.base_use_case import BaseUseCase
from src.application.common.command import Command
from src.application.common.result import Result
from src.infrastructure.clinic.settings_provider import settings_to_dict


class GetClinicSettingsUseCase(BaseUseCase):
    """Returns the current clinic settings.

    No authorization needed — settings are public.
    """

    async def authorize(self, command: Command) -> None:
        pass

    async def execute(self, command: Command) -> Result:
        """Get current clinic settings.

        Args:
            command: Unused (settings are always the same).

        Returns:
            Result with clinic settings dict.
        """
        settings = settings_to_dict()
        return Result.ok(
            data=settings,
            message="Clinic settings retrieved",
        )
