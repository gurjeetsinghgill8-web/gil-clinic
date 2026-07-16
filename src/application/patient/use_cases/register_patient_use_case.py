"""RegisterPatientUseCase — register a new patient.

Orchestrates:
1. Validate input (name, phone, age, gender)
2. Check for duplicate phone via phone_hash
3. Generate patient_id (CQ-YYYYMMDD-NNN)
4. Create ContactInfo, Demographics, EmergencyContact VOs
5. Create Patient aggregate via Patient.register()
6. Generate QR identity for PWA login
7. Save patient to repository
8. Publish PATIENT.REGISTERED event
9. Return RegisterPatientResponse

Dependencies:
- PatientRepository, PatientIdGenerator, QRCodeGenerator
- EventPublisher
"""

from __future__ import annotations

from hashlib import sha256
from typing import TYPE_CHECKING

from src.application.common.base_use_case import BaseUseCase
from src.application.common.command import Command
from src.application.common.result import Result
from src.application.common.exceptions import (
    ConflictError,
    ValidationError,
)
from src.application.patient.dtos.responses import (
    RegisterPatientRequest,
    RegisterPatientResponse,
)
from src.domain.patient.entities.patient import Patient
from src.domain.patient.value_objects.contact_info import ContactInfo
from src.domain.patient.value_objects.demographics import Demographics
from src.domain.patient.value_objects.emergency_contact import EmergencyContact
from src.domain.patient.events.patient_events import patient_registered

if TYPE_CHECKING:
    from src.domain.patient.ports.patient_repository import PatientRepository
    from src.domain.patient.ports.patient_id_generator import PatientIdGenerator
    from src.domain.patient.ports.qr_code_generator import QRCodeGenerator
    from src.domain.patient.ports.patient_notifier import PatientNotifier
    from src.domain.identity.ports.event_publisher import EventPublisher


class RegisterPatientUseCase(BaseUseCase):
    """Use case for registering a new patient."""

    def __init__(
        self,
        patient_repo: PatientRepository,
        patient_id_generator: PatientIdGenerator,
        qr_code_generator: QRCodeGenerator,
        event_publisher: EventPublisher,
        patient_notifier: PatientNotifier | None = None,
    ) -> None:
        super().__init__()
        self._patient_repo = patient_repo
        self._patient_id_generator = patient_id_generator
        self._qr_code_generator = qr_code_generator
        self._event_publisher = event_publisher
        self._patient_notifier = patient_notifier

    async def authorize(self, command: Command) -> None:
        """Registration requires staff authentication — enforced by route middleware."""
        pass

    async def validate(self, command: Command) -> None:
        """Validate registration input."""
        dto: RegisterPatientRequest = command.data

        if not dto.name.strip():
            raise ValidationError(
                message="Patient name is required.",
                details={"field": "name"},
            )

        if dto.emergency_contact_name and not dto.emergency_contact_phone:
            raise ValidationError(
                message="Emergency contact phone is required when name is provided.",
                details={"field": "emergency_contact_phone"},
            )

    async def execute(self, command: Command) -> Result:
        """Execute patient registration.

        Args:
            command: Command with RegisterPatientRequest as data.

        Returns:
            Result with RegisterPatientResponse or error.
        """
        dto: RegisterPatientRequest = command.data

        try:
            # 1. Check for duplicate phone
            phone_hash = sha256(dto.phone.encode()).hexdigest()
            exists = await self._patient_repo.exists_by_phone_hash(phone_hash)
            if exists:
                raise ConflictError(
                    message=f"A patient with phone {dto.phone} is already registered.",
                    details={"phone": dto.phone},
                )

            # 2. Generate patient ID
            patient_id = await self._patient_id_generator.generate_patient_id()

            # 3. Create value objects
            demographics = Demographics.create(
                name=dto.name.strip(),
                age=dto.age,
                gender=dto.gender.value,
                date_of_birth=dto.date_of_birth,
                blood_group=dto.blood_group,
            )
            contact = ContactInfo.create(
                phone=dto.phone,
                phone_hash=phone_hash,
                email=dto.email,
                address=dto.address,
            )

            # 4. Create emergency contact if provided
            emergency_contact = None
            if dto.emergency_contact_name:
                emergency_contact = EmergencyContact.create(
                    name=dto.emergency_contact_name,
                    relationship=dto.emergency_contact_relationship or "unknown",
                    phone=dto.emergency_contact_phone or "",
                )

            # 5. Create patient aggregate
            patient = Patient.register(
                patient_id=patient_id,
                demographics=demographics,
                contact=contact,
                emergency_contact=emergency_contact,
            )

            # 6. Generate QR identity
            qr_identity = await self._qr_code_generator.generate_patient_qr(
                patient_id=str(patient.id),
                patient_uuid=str(patient.id),
            )
            if qr_identity:
                patient.assign_qr_identity(qr_identity)

            # 7. Save patient
            await self._patient_repo.save(patient)

            # 8. Publish event
            self._event_publisher.publish(
                patient_registered(
                    patient_id=str(patient.id),
                    name=dto.name,
                    phone_hash=phone_hash,
                    source=dto.source,
                )
            )

            return Result.ok(
                data=RegisterPatientResponse(
                    id=str(patient.id),
                    patient_id=patient.patient_id,
                    name=patient.demographics.name,
                    phone=patient.contact.phone,
                    qr_identity={
                        "hash": qr_identity.qr_hash[:16] + "...",
                        "generated_at": qr_identity.generated_at.isoformat(),
                    } if qr_identity else None,
                ),
                message=f"Patient '{dto.name}' registered successfully as {patient_id}",
            )

        except (ConflictError, ValidationError) as exc:
            return Result.fail(
                error=str(exc),
                code=exc.code,
                details=exc.details,
            )
