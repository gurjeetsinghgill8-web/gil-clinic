"""LookupPatientUseCase — find patients by various criteria.

Provides read-only lookup operations:
1. By patient_id (human-readable CQ-XXXX)
2. By phone_hash
3. By QR hash (PWA login)
4. Search by name (fuzzy)
5. List active patients (paginated)

Dependencies:
- PatientRepository
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.application.common.base_use_case import BaseUseCase
from src.application.common.command import Query
from src.application.common.result import Result
from src.application.common.exceptions import NotFoundError
from src.application.patient.dtos.responses import (
    PatientResponse,
    PatientListResponse,
)
from src.domain.patient.value_objects.patient_status import PatientLifecycleStatus

if TYPE_CHECKING:
    from src.domain.patient.ports.patient_repository import PatientRepository


class LookupPatientUseCase(BaseUseCase):
    """Use case for patient lookup and search."""

    def __init__(
        self,
        patient_repo: PatientRepository,
    ) -> None:
        super().__init__()
        self._patient_repo = patient_repo

    async def authorize(self, command: Command) -> None:
        """Lookup requires authentication — enforced by route middleware."""
        pass

    async def execute(self, command: Command) -> Result:
        """Execute patient lookup.

        Supports lookup by patient_id, phone_hash, qr_hash, or name search.
        Determines which field to use based on query parameters.

        Args:
            command: Query with lookup parameters.

        Returns:
            Result with PatientResponse or PatientListResponse.
        """
        params = command.data  # dict-like with query parameters

        try:
            # By human-readable patient ID
            if patient_id := params.get("patient_id"):
                patient = await self._patient_repo.get_by_patient_id(patient_id)
                if not patient:
                    raise NotFoundError(
                        message=f"Patient with ID '{patient_id}' not found.",
                        details={"patient_id": patient_id},
                    )
                return Result.ok(
                    data=self._to_response(patient),
                )

            # By phone hash
            if phone_hash := params.get("phone_hash"):
                patient = await self._patient_repo.get_by_phone_hash(phone_hash)
                if not patient:
                    raise NotFoundError(
                        message="Patient not found with the given phone number.",
                    )
                return Result.ok(
                    data=self._to_response(patient),
                )

            # By QR hash
            if qr_hash := params.get("qr_hash"):
                patient = await self._patient_repo.get_by_qr_hash(qr_hash)
                if not patient:
                    raise NotFoundError(
                        message="Patient not found for the given QR code.",
                    )
                return Result.ok(
                    data=self._to_response(patient),
                )

            # Search by name
            if query := params.get("query"):
                offset = params.get("offset", 0)
                limit = params.get("limit", 20)
                patients = await self._patient_repo.search_by_name(
                    query, offset=offset, limit=limit
                )
                total = await self._patient_repo.count()
                return Result.ok(
                    data=PatientListResponse(
                        patients=[self._to_response(p) for p in patients],
                        total=total,
                        offset=offset,
                        limit=limit,
                    ),
                )

            # List all active patients (paginated)
            offset = params.get("offset", 0)
            limit = params.get("limit", 100)
            status = params.get("status")
            if status:
                patients = await self._patient_repo.list_by_status(
                    status, offset=offset, limit=limit
                )
            else:
                patients = await self._patient_repo.list_active(
                    offset=offset, limit=limit
                )
            total = await self._patient_repo.count(status=status)

            return Result.ok(
                data=PatientListResponse(
                    patients=[self._to_response(p) for p in patients],
                    total=total,
                    offset=offset,
                    limit=limit,
                ),
            )

        except NotFoundError as exc:
            return Result.fail(
                error=str(exc),
                code=exc.code,
                details=exc.details,
            )

    @staticmethod
    def _to_response(patient) -> PatientResponse:
        """Map Patient aggregate to API response DTO."""
        return PatientResponse(
            id=str(patient.id),
            patient_id=patient.patient_id,
            name=patient.demographics.name,
            age=patient.demographics.age,
            gender=patient.demographics.gender,
            phone=patient.contact.phone,
            email=patient.contact.email,
            address=patient.contact.address,
            date_of_birth=patient.demographics.date_of_birth.isoformat()
            if patient.demographics.date_of_birth else None,
            blood_group=patient.demographics.blood_group,
            status=patient.status.status.value,
            emergency_contact_name=patient.emergency_contact.name
            if patient.emergency_contact else None,
            emergency_contact_relationship=patient.emergency_contact.relationship
            if patient.emergency_contact else None,
            emergency_contact_phone=patient.emergency_contact.phone
            if patient.emergency_contact else None,
            total_visits=patient.total_visits,
            last_visit_at=patient.last_visit_at.isoformat()
            if patient.last_visit_at else None,
            has_qr_identity=patient.has_qr_identity(),
            device_count=patient.device_count,
            reception_inquiry=patient.reception_inquiry,
            created_at=patient.created_at.isoformat(),
            updated_at=patient.updated_at.isoformat(),
        )
