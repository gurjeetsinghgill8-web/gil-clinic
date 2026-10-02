"""Experience Engine package.

Thin orchestration layer — never owns data, never has its own tables.
Reads from Patient Engine and (future) Queue Engine.
"""

from src.experience.application import (
    PatientLoginUseCase,
    get_patient_from_session,
    refresh_session,
    PatientStatusUseCase,
    TokenSlipUseCase,
    PatientInquiryUseCase,
)
from src.experience.presentation import (
    pwa_router as experience_pwa_router,
    api_router as experience_api_router,
)

__all__ = [
    "PatientLoginUseCase",
    "get_patient_from_session",
    "refresh_session",
    "PatientStatusUseCase",
    "TokenSlipUseCase",
    "PatientInquiryUseCase",
    "experience_pwa_router",
    "experience_api_router",
]
