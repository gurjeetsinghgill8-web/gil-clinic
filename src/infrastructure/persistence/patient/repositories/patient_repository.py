"""SQLAlchemy repository for Patient aggregate.

Implements PatientRepository port protocol from domain layer.
Uses Specification pattern for filtering.
Supports OCC via version field in BaseRepository.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from src.domain.patient.entities.patient import Patient
from src.infrastructure.patient.models.patient_model import PatientModel
from src.infrastructure.persistence.patient.mappers.patient_mapper import (
    PatientMapper,
)
from src.infrastructure.persistence.identity.repositories.base_repository import (
    BaseRepository,
)
from src.infrastructure.persistence.identity.specifications.base_specification import (
    Specification,
)
from src.infrastructure.persistence.patient.specifications.patient_specifications import (
    ByPatientIdSpecification,
    ByPhoneHashSpecification,
    ByQrHashSpecification,
    ByStatusSpecification,
    ActivePatientsSpecification,
    NameSearchSpecification,
    NotMergedSpecification,
)


class SqlAlchemyPatientRepository(BaseRepository[Patient, PatientModel]):
    """Repository for Patient aggregate with OCC and Specification support."""

    def __init__(self, session) -> None:
        super().__init__(session)
        self._mapper = PatientMapper()

    @property
    def _model_class(self) -> type[PatientModel]:
        return PatientModel

    def _to_domain(self, model: PatientModel) -> Patient:
        return self._mapper.to_domain(model)

    def _apply_to_model(self, model: PatientModel, entity: Patient) -> None:
        """Update an existing model from a domain entity.

        For Patient, we use the mapper's apply_to_model for updates.
        For new entities, we build a full model via to_model and merge.
        """
        self._mapper.apply_to_model(model, entity)

    # ------------------------------------------------------------------
    # PatientRepository port implementations
    # ------------------------------------------------------------------

    async def get_by_id(self, patient_uuid: str) -> Patient | None:
        """Get a patient by their internal UUID.

        Args:
            patient_uuid: UUID string of the patient.

        Returns:
            Patient if found, None otherwise.
        """
        from uuid import UUID
        try:
            uid = UUID(patient_uuid)
        except (ValueError, TypeError):
            return None
        result = await self.session.execute(
            select(PatientModel).where(PatientModel.id == uid)
        )
        model = result.scalar_one_or_none()
        if not model:
            return None
        return self._to_domain(model)

    async def get_by_patient_id(self, patient_id: str) -> Patient | None:
        """Get a patient by their human-readable ID."""
        spec = ByPatientIdSpecification(patient_id) & NotMergedSpecification()
        return await self.find_one(spec)

    async def get_by_phone_hash(self, phone_hash: str) -> Patient | None:
        """Get a patient by phone hash."""
        spec = ByPhoneHashSpecification(phone_hash) & NotMergedSpecification()
        return await self.find_one(spec)

    async def get_by_qr_hash(self, qr_hash: str) -> Patient | None:
        """Get a patient by QR identity hash."""
        spec = ByQrHashSpecification(qr_hash) & NotMergedSpecification()
        return await self.find_one(spec)

    async def exists_by_phone_hash(self, phone_hash: str) -> bool:
        """Check if a phone number is already registered."""
        return await self._check_duplicate(
            PatientModel.phone_hash, phone_hash
        )

    async def list_active(
        self,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Patient]:
        """List active patients with pagination."""
        spec = ActivePatientsSpecification() & NotMergedSpecification()
        return await self.find_many(spec, offset=offset, limit=limit)

    async def list_by_status(
        self,
        status: str,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Patient]:
        """List patients by lifecycle status."""
        spec = ByStatusSpecification(status) & NotMergedSpecification()
        return await self.find_many(spec, offset=offset, limit=limit)

    async def search_by_name(
        self,
        query: str,
        offset: int = 0,
        limit: int = 20,
    ) -> list[Patient]:
        """Search patients by name (ILIKE search)."""
        spec = NameSearchSpecification(query) & NotMergedSpecification()
        return await self.find_many(spec, offset=offset, limit=limit)

    async def count(self, status: str | None = None) -> int:
        """Count patients, optionally filtered by status."""
        if status:
            spec = ByStatusSpecification(status)
            return await self._count(spec)
        return await self._count()

    async def delete(self, patient_uuid: str) -> bool:
        """Hard-delete a patient record (admin only)."""
        from uuid import UUID
        try:
            uid = UUID(patient_uuid)
        except (ValueError, TypeError):
            return False

        result = await self.session.execute(
            select(PatientModel).where(PatientModel.id == uid)
        )
        model = result.scalar_one_or_none()
        if not model:
            return False
        await self.session.delete(model)
        await self.session.commit()
        return True

    async def get_next_sequence_number(self, date_prefix: str) -> int:
        """Get the next daily sequence number for patient ID generation.

        Counts patients registered today with the given date prefix.
        """
        query = select(func.count(PatientModel.id)).where(
            PatientModel.patient_id.like(f"{date_prefix}%")
        )
        result = await self.session.execute(query)
        count = result.scalar() or 0
        return count + 1

    async def save(self, patient: Patient) -> None:
        """Persist a new or updated patient.

        Handles both insert and update with OCC.

        Args:
            patient: Patient aggregate to save.
        """
        # Try to find existing entity first (handles case where domain
        # version > 1 due to touch() during initial setup)
        result = await self.session.execute(
            select(PatientModel).where(PatientModel.id == patient.id)
        )
        model = result.scalar_one_or_none()

        if model is None:
            # New entity — insert (regardless of version)
            model = self._mapper.to_model(patient)
            self.session.add(model)
        else:
            # Existing entity — update with OCC
            if model.version != patient.version - 1:
                from src.infrastructure.persistence.identity.exceptions.persistence_exceptions import (
                    ConcurrentModificationError,
                )
                raise ConcurrentModificationError(
                    entity_type="PatientModel",
                    entity_id=str(patient.id),
                    expected_version=patient.version - 1,
                    actual_version=model.version,
                )
            self._mapper.apply_to_model(model, patient)
            model.version = patient.version
