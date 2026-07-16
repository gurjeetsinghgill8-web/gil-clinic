"""Simple patient lookup for Queue Lite — uses AsyncSession.

Queue Lite needs basic patient lookups but the async PatientRepository
from the Patient Engine expects a heavier repository. This module provides
lightweight lookups that work with Queue Lite's AsyncSession.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.patient.entities.patient import Patient
from src.infrastructure.patient.models.patient_model import PatientModel
from src.infrastructure.persistence.patient.mappers.patient_mapper import (
    PatientMapper,
)


class QueuePatientLookup:
    """Lightweight patient lookup using AsyncSession.

    Provides just enough read access for Queue Lite operations
    (validate patient exists, get patient details).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._mapper = PatientMapper()

    async def get_by_patient_id(self, patient_id: str) -> Patient | None:
        """Lookup a patient by their human-readable patient_id.

        Args:
            patient_id: Human-readable ID (e.g., 'CQ-20260714-001').

        Returns:
            Patient domain entity or None.
        """
        stmt = select(PatientModel).where(
            PatientModel.patient_id == patient_id
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._mapper.to_domain(model)

    async def save(self, patient: Patient) -> None:
        """Save a patient (insert or update).

        Args:
            patient: Patient domain entity to persist.
        """
        model = await self._session.get(PatientModel, patient.id)
        if model is None:
            model = self._mapper.to_model(patient)
            self._session.add(model)
        else:
            self._mapper.apply_to_model(model, patient)
            model.version = patient.version
        await self._session.flush()

    async def get_by_uuid(self, patient_uuid: str) -> Patient | None:
        """Lookup a patient by their UUID (id field).

        Args:
            patient_uuid: UUID of the patient.

        Returns:
            Patient domain entity or None.
        """
        import uuid
        try:
            uid = uuid.UUID(patient_uuid)
        except ValueError:
            return None
        model = await self._session.get(PatientModel, uid)
        if model is None:
            return None
        return self._mapper.to_domain(model)

    async def get_by_id(self, patient_uuid: str) -> Patient | None:
        """Lookup a patient by their UUID (alias for get_by_uuid).

        Args:
            patient_uuid: UUID of the patient.

        Returns:
            Patient domain entity or None.
        """
        return await self.get_by_uuid(patient_uuid)

    async def exists_by_patient_id(self, patient_id: str) -> bool:
        """Check if a patient exists by their patient_id.

        Args:
            patient_id: Human-readable patient ID.

        Returns:
            True if patient exists.
        """
        result = await self.get_by_patient_id(patient_id)
        return result is not None
