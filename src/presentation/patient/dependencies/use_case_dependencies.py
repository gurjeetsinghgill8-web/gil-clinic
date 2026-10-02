"""Dependency injection for Patient Engine use cases.

Provides factory functions that instantiate patient use cases with their
required infrastructure dependencies (repositories, services, event publisher).
"""

from __future__ import annotations

from typing import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.patient.use_cases.register_patient_use_case import (
    RegisterPatientUseCase,
)
from src.application.patient.use_cases.lookup_patient_use_case import (
    LookupPatientUseCase,
)
from src.application.patient.use_cases.update_patient_use_case import (
    UpdatePatientUseCase,
)
from src.application.patient.use_cases.device_registration_use_case import (
    DeviceRegistrationUseCase,
)
from src.application.patient.use_cases.visit_tracking_use_case import (
    VisitTrackingUseCase,
)
from src.application.patient.use_cases.medical_history_use_case import (
    MedicalHistoryUseCase,
)
from src.infrastructure.patient.services.patient_id_generator import (
    PatientIdGeneratorService,
)
from src.infrastructure.patient.services.qr_code_generator import (
    PatientQRCodeGenerator,
)
from src.infrastructure.persistence.patient.repositories.patient_repository import (
    SqlAlchemyPatientRepository,
)
from src.shared.infrastructure.database import get_session

# ------------------------------------------------------------------
# Repositories (request-scoped)
# ------------------------------------------------------------------


async def get_patient_repo(
    session: AsyncSession = Depends(get_session),
) -> SqlAlchemyPatientRepository:
    """Get a PatientRepository instance bound to the session."""
    return SqlAlchemyPatientRepository(session)


# ------------------------------------------------------------------
# Services (singletons)
# ------------------------------------------------------------------


_patient_qr_generator: PatientQRCodeGenerator | None = None


def get_qr_code_generator() -> PatientQRCodeGenerator:
    """Get the QR code generator singleton."""
    global _patient_qr_generator
    if _patient_qr_generator is None:
        _patient_qr_generator = PatientQRCodeGenerator()
    return _patient_qr_generator


def get_event_publisher():
    """Get the event publisher.

    Uses the same event publisher from the Identity Engine.
    """
    from src.infrastructure.identity.services.event_publisher import (
        InMemoryEventPublisher,
    )
    return InMemoryEventPublisher()


# ------------------------------------------------------------------
# Use Case Factories
# ------------------------------------------------------------------


async def get_register_patient_use_case(
    patient_repo: SqlAlchemyPatientRepository = Depends(get_patient_repo),
    qr_code_generator: PatientQRCodeGenerator = Depends(get_qr_code_generator),
) -> RegisterPatientUseCase:
    """Factory for RegisterPatientUseCase."""
    return RegisterPatientUseCase(
        patient_repo=patient_repo,
        patient_id_generator=PatientIdGeneratorService(patient_repo),
        qr_code_generator=qr_code_generator,
        event_publisher=get_event_publisher(),
    )


async def get_lookup_patient_use_case(
    patient_repo: SqlAlchemyPatientRepository = Depends(get_patient_repo),
) -> LookupPatientUseCase:
    """Factory for LookupPatientUseCase."""
    return LookupPatientUseCase(
        patient_repo=patient_repo,
    )


async def get_update_patient_use_case(
    patient_repo: SqlAlchemyPatientRepository = Depends(get_patient_repo),
) -> UpdatePatientUseCase:
    """Factory for UpdatePatientUseCase."""
    return UpdatePatientUseCase(
        patient_repo=patient_repo,
        event_publisher=get_event_publisher(),
    )


async def get_device_registration_use_case(
    patient_repo: SqlAlchemyPatientRepository = Depends(get_patient_repo),
) -> DeviceRegistrationUseCase:
    """Factory for DeviceRegistrationUseCase."""
    return DeviceRegistrationUseCase(
        patient_repo=patient_repo,
        event_publisher=get_event_publisher(),
    )


async def get_visit_tracking_use_case(
    patient_repo: SqlAlchemyPatientRepository = Depends(get_patient_repo),
) -> VisitTrackingUseCase:
    """Factory for VisitTrackingUseCase."""
    return VisitTrackingUseCase(
        patient_repo=patient_repo,
        event_publisher=get_event_publisher(),
    )


async def get_medical_history_use_case(
    patient_repo: SqlAlchemyPatientRepository = Depends(get_patient_repo),
) -> MedicalHistoryUseCase:
    """Factory for MedicalHistoryUseCase."""
    return MedicalHistoryUseCase(
        patient_repo=patient_repo,
        event_publisher=get_event_publisher(),
    )
