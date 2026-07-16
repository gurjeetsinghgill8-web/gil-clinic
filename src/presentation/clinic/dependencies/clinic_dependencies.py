"""Clinic Engine — FastAPI dependency injection.

Provides use case factories for clinic settings management.
"""

from __future__ import annotations

from src.application.clinic.use_cases.get_clinic_settings_use_case import (
    GetClinicSettingsUseCase,
)
from src.application.clinic.use_cases.update_clinic_settings_use_case import (
    UpdateClinicSettingsUseCase,
)


def get_clinic_settings_use_case() -> GetClinicSettingsUseCase:
    """Factory for GetClinicSettingsUseCase.

    No dependencies — settings are file/env backed.
    """
    return GetClinicSettingsUseCase()


def get_update_clinic_settings_use_case() -> UpdateClinicSettingsUseCase:
    """Factory for UpdateClinicSettingsUseCase.

    No dependencies — settings are file/env backed.
    """
    return UpdateClinicSettingsUseCase()
