"""UpdatePatientUseCase — update patient demographics, contact, and status.

Supports:
1. Update demographics (name, age, gender, DOB, blood group)
2. Update contact (email, address)
3. Update emergency contact
4. Block patient
5. Reactivate patient
6. Merge duplicate records
7. Set/clear reception inquiry

Dependencies:
- PatientRepository
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from src.application.common.base_use_case import BaseUseCase
from src.application.common.command import Command
from src.application.common.result import Result
from src.application.common.exceptions import (
    NotFoundError,
    ConflictError,
    ValidationError,
)
from src.application.patient.dtos.responses import (
    UpdatePatientRequest,
    PatientResponse,
    PatientStatusChangeResponse,
    MergeResponse,
    BlockPatientRequest,
    MergePatientsRequest,
    SetInquiryRequest,
    InquiryResponse,
)
from src.domain.patient.value_objects.demographics import Demographics
from src.domain.patient.value_objects.emergency_contact import EmergencyContact
from src.domain.patient.events.patient_events import (
    patient_status_changed,
    patient_merged,
    patient_inquiry_sent,
)
from src.domain.patient.services.patient_domain_service import (
    PatientDomainService,
)

if TYPE_CHECKING:
    from src.domain.patient.ports.patient_repository import PatientRepository
    from src.domain.identity.ports.event_publisher import EventPublisher


class UpdatePatientUseCase(BaseUseCase):
    """Use case for updating patient records."""

    def __init__(
        self,
        patient_repo: PatientRepository,
        event_publisher: EventPublisher,
    ) -> None:
        super().__init__()
        self._patient_repo = patient_repo
        self._event_publisher = event_publisher
        self._domain_service = PatientDomainService()

    async def authorize(self, command: Command) -> None:
        """Update requires staff authentication — enforced by route middleware."""
        pass

    async def execute(self, command: Command) -> Result:
        """Execute patient update.

        Determines the operation type from the command data.

        Args:
            command: Command with operation type and parameters.

        Returns:
            Result with appropriate response DTO.
        """
        dto = command.data
        operation = getattr(dto, "operation", "update")

        try:
            if operation == "update":
                return await self._update_patient(dto)
            elif operation == "block":
                return await self._block_patient(dto)
            elif operation == "reactivate":
                return await self._reactivate_patient(dto)
            elif operation == "merge":
                return await self._merge_patients(dto)
            elif operation == "set_inquiry":
                return await self._set_inquiry(dto)
            elif operation == "clear_inquiry":
                return await self._clear_inquiry(dto)
            else:
                raise ValidationError(
                    message=f"Unknown operation: {operation}",
                    details={"operation": operation},
                )

        except (NotFoundError, ConflictError, ValidationError) as exc:
            return Result.fail(
                error=str(exc),
                code=exc.code,
                details=exc.details,
            )

    async def _update_patient(self, dto: UpdatePatientRequest) -> Result:
        """Update patient demographics, contact, and emergency contact."""
        # Load patient
        patient = await self._patient_repo.get_by_patient_id(dto.patient_id)
        if not patient:
            raise NotFoundError(
                message=f"Patient with ID '{dto.patient_id}' not found.",
                details={"patient_id": dto.patient_id},
            )

        # Update demographics if any field provided
        if dto.name or dto.age or dto.gender or dto.blood_group:
            new_name = dto.name or patient.demographics.name
            new_age = dto.age or patient.demographics.age
            new_gender = dto.gender.value if dto.gender else patient.demographics.gender
            new_dob = dto.date_of_birth or patient.demographics.date_of_birth
            new_blood = dto.blood_group or patient.demographics.blood_group

            new_demographics = Demographics.create(
                name=new_name,
                age=new_age,
                gender=new_gender,
                date_of_birth=new_dob,
                blood_group=new_blood,
            )
            object.__setattr__(patient, "demographics", new_demographics)

        # Update contact if any field provided
        if dto.email or dto.address:
            new_email = dto.email if dto.email is not None else patient.contact.email
            new_address = dto.address if dto.address is not None else patient.contact.address
            from src.domain.patient.value_objects.contact_info import ContactInfo
            new_contact = ContactInfo.create(
                phone=patient.contact.phone,
                phone_hash=patient.contact.phone_hash,
                email=new_email,
                address=new_address,
            )
            object.__setattr__(patient, "contact", new_contact)

        # Update emergency contact if provided
        if dto.emergency_contact_name is not None:
            if dto.emergency_contact_name:
                patient.emergency_contact = EmergencyContact.create(
                    name=dto.emergency_contact_name,
                    relationship=dto.emergency_contact_relationship or "unknown",
                    phone=dto.emergency_contact_phone or "",
                )
            else:
                patient.emergency_contact = None

        patient.touch()
        await self._patient_repo.save(patient)

        return Result.ok(
            data=PatientResponse(
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
            ),
            message="Patient updated successfully",
        )

    async def _block_patient(self, dto: BlockPatientRequest) -> Result:
        """Block a patient."""
        patient = await self._patient_repo.get_by_patient_id(dto.patient_id)
        if not patient:
            raise NotFoundError(
                message=f"Patient with ID '{dto.patient_id}' not found.",
                details={"patient_id": dto.patient_id},
            )

        old_status = patient.status.status.value
        patient.mark_blocked(reason=dto.reason)
        await self._patient_repo.save(patient)

        self._event_publisher.publish(
            patient_status_changed(
                patient_id=str(patient.id),
                old_status=old_status,
                new_status="blocked",
                reason=dto.reason,
            )
        )

        return Result.ok(
            data=PatientStatusChangeResponse(
                patient_id=patient.patient_id,
                old_status=old_status,
                new_status="blocked",
                message=f"Patient '{patient.demographics.name}' has been blocked.",
            ),
        )

    async def _reactivate_patient(self, dto: Any) -> Result:
        """Reactivate a patient (from inactive or blocked)."""
        patient_id = getattr(dto, "patient_id", dto)
        patient = await self._patient_repo.get_by_patient_id(patient_id)
        if not patient:
            raise NotFoundError(
                message=f"Patient with ID '{patient_id}' not found.",
                details={"patient_id": patient_id},
            )

        old_status = patient.status.status.value
        patient.reactivate()
        await self._patient_repo.save(patient)

        self._event_publisher.publish(
            patient_status_changed(
                patient_id=str(patient.id),
                old_status=old_status,
                new_status="active",
            )
        )

        return Result.ok(
            data=PatientStatusChangeResponse(
                patient_id=patient.patient_id,
                old_status=old_status,
                new_status="active",
                message=f"Patient '{patient.demographics.name}' reactivated.",
            ),
        )

    async def _merge_patients(self, dto: MergePatientsRequest) -> Result:
        """Merge duplicate patient records."""
        source = await self._patient_repo.get_by_patient_id(dto.source_patient_id)
        target = await self._patient_repo.get_by_patient_id(dto.target_patient_id)

        if not source:
            raise NotFoundError(
                message=f"Source patient '{dto.source_patient_id}' not found.",
            )
        if not target:
            raise NotFoundError(
                message=f"Target patient '{dto.target_patient_id}' not found.",
            )

        can_merge, reason = self._domain_service.can_merge_patients(source, target)
        if not can_merge:
            raise ConflictError(
                message=reason or "Cannot merge these patients.",
                details={
                    "source": dto.source_patient_id,
                    "target": dto.target_patient_id,
                },
            )

        source.mark_merged(target.patient_id)
        await self._patient_repo.save(source)

        self._event_publisher.publish(
            patient_merged(
                patient_id=str(source.id),
                merged_into_patient_id=target.patient_id,
            )
        )

        return Result.ok(
            data=MergeResponse(
                source_patient_id=dto.source_patient_id,
                target_patient_id=dto.target_patient_id,
                message=f"Patient '{dto.source_patient_id}' merged into '{dto.target_patient_id}'.",
            ),
        )

    async def _set_inquiry(self, dto: SetInquiryRequest) -> Result:
        """Set a patient inquiry (from patient PWA)."""
        patient = await self._patient_repo.get_by_patient_id(dto.patient_id)
        if not patient:
            raise NotFoundError(
                message=f"Patient with ID '{dto.patient_id}' not found.",
                details={"patient_id": dto.patient_id},
            )

        patient.set_inquiry(dto.inquiry_text)
        await self._patient_repo.save(patient)

        self._event_publisher.publish(
            patient_inquiry_sent(
                patient_id=str(patient.id),
                inquiry_text=dto.inquiry_text,
            )
        )

        return Result.ok(
            data=InquiryResponse(
                patient_id=patient.patient_id,
                inquiry_text=dto.inquiry_text,
            ),
        )

    async def _clear_inquiry(self, dto: Any) -> Result:
        """Clear a patient inquiry (staff responded)."""
        patient_id = getattr(dto, "patient_id", dto)
        patient = await self._patient_repo.get_by_patient_id(patient_id)
        if not patient:
            raise NotFoundError(
                message=f"Patient with ID '{patient_id}' not found.",
                details={"patient_id": patient_id},
            )

        patient.clear_inquiry()
        await self._patient_repo.save(patient)

        return Result.ok(
            data=InquiryResponse(
                patient_id=patient.patient_id,
                inquiry_text="(cleared)",
                message="Inquiry cleared.",
            ),
        )
