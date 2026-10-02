"""Mapper: Patient domain entity ↔ PatientModel SQLAlchemy model.

Handles conversion between domain Patient aggregate and the SQLAlchemy
PatientModel. Nested value objects (Demographics, ContactInfo, etc.) are
flattened into top-level columns for query performance, with JSONB columns
for variable/optional data (devices, medical history, notification prefs).
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from src.domain.patient.entities.patient import Patient
from src.domain.patient.value_objects.contact_info import ContactInfo
from src.domain.patient.value_objects.demographics import Demographics
from src.domain.patient.value_objects.device_registration import (
    DeviceRegistration,
)
from src.domain.patient.value_objects.emergency_contact import EmergencyContact
from src.domain.patient.value_objects.medical_history import (
    MedicalHistoryEntry,
)
from src.domain.patient.value_objects.notification_preference import (
    NotificationPreference,
)
from src.domain.patient.value_objects.patient_status import (
    PatientLifecycleStatus,
    PatientStatus,
)
from src.domain.patient.value_objects.qr_identity import QRIdentity
from src.infrastructure.patient.models.patient_model import PatientModel


class PatientMapper:
    """Converts between Patient domain entity and PatientModel.

    Handles:
    - Domain → Model: Flatten value objects, serialize JSONB columns
    - Model → Domain: Reconstruct value objects from flattened fields
    """

    @staticmethod
    def to_model(entity: Patient) -> PatientModel:
        """Convert a domain Patient to a SQLAlchemy PatientModel.

        Args:
            entity: Domain Patient entity.

        Returns:
            PatientModel ready for persistence.
        """
        return PatientModel(
            id=entity.id,
            patient_id=entity.patient_id,
            name=entity.demographics.name,
            age=entity.demographics.age,
            gender=entity.demographics.gender,
            date_of_birth=entity.demographics.date_of_birth.isoformat()
            if entity.demographics.date_of_birth else None,
            blood_group=entity.demographics.blood_group,
            phone=entity.contact.phone,
            phone_hash=entity.contact.phone_hash,
            email=entity.contact.email,
            address=entity.contact.address,
            emergency_contact={
                "name": entity.emergency_contact.name,
                "relationship": entity.emergency_contact.relationship,
                "phone": entity.emergency_contact.phone,
            } if entity.emergency_contact else None,
            qr_hash=entity.qr_identity.qr_hash if entity.qr_identity else None,
            qr_identity={
                "qr_hash": entity.qr_identity.qr_hash,
                "qr_payload": entity.qr_identity.qr_payload,
                "generated_at": entity.qr_identity.generated_at.isoformat(),
                "expires_at": entity.qr_identity.expires_at.isoformat()
                if entity.qr_identity.expires_at else None,
            } if entity.qr_identity else None,
            status=entity.status.status.value,
            status_reason=entity.status.reason,
            registered_devices=[
                {
                    "device_id": d.device_id,
                    "device_name": d.device_name,
                    "push_token": d.push_token,
                    "platform": d.platform,
                    "user_agent": d.user_agent,
                    "ip_address": d.ip_address,
                    "registered_at": d.registered_at.isoformat(),
                    "last_seen_at": d.last_seen_at.isoformat(),
                }
                for d in entity.registered_devices
            ] if entity.registered_devices else [],
            notification_preferences={
                "push_enabled": entity.notification_preferences.push_enabled,
                "sms_enabled": entity.notification_preferences.sms_enabled,
                "whatsapp_enabled": entity.notification_preferences.whatsapp_enabled,
                "email_enabled": entity.notification_preferences.email_enabled,
                "sound_enabled": entity.notification_preferences.sound_enabled,
                "vibration_enabled": entity.notification_preferences.vibration_enabled,
            },
            medical_history=[
                {
                    "condition": e.condition,
                    "diagnosed_at": e.diagnosed_at,
                    "notes": e.notes,
                    "is_active": e.is_active,
                    "recorded_at": e.recorded_at.isoformat(),
                }
                for e in entity.medical_history
            ] if entity.medical_history else [],
            last_visit_at=entity.last_visit_at,
            total_visits=entity.total_visits,
            merged_into_patient_id=entity.merged_into_patient_id,
            reception_inquiry=entity.reception_inquiry,
            version=entity.version,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    @staticmethod
    def to_domain(model: PatientModel) -> Patient:
        """Convert a SQLAlchemy PatientModel to a domain Patient.

        Args:
            model: PatientModel from database.

        Returns:
            Domain Patient entity with all value objects reconstructed.
        """
        # Reconstruct Demographics
        dob = None
        if model.date_of_birth:
            try:
                dob = date.fromisoformat(model.date_of_birth)
            except (ValueError, TypeError):
                pass

        demographics = Demographics.create(
            name=model.name,
            age=model.age,
            gender=model.gender,
            date_of_birth=dob,
            blood_group=model.blood_group,
        )

        # Reconstruct ContactInfo
        contact = ContactInfo.create(
            phone=model.phone,
            phone_hash=model.phone_hash,
            email=model.email,
            address=model.address,
        )

        # Reconstruct PatientStatus
        try:
            status_enum = PatientLifecycleStatus(model.status)
        except ValueError:
            status_enum = PatientLifecycleStatus.ACTIVE
        status = PatientStatus(
            status=status_enum,
            reason=model.status_reason,
        )

        # Reconstruct QRIdentity
        qr_identity = None
        if model.qr_identity and model.qr_hash:
            qr_data = model.qr_identity
            qr_expires = None
            if qr_data.get("expires_at"):
                try:
                    qr_expires = datetime.fromisoformat(qr_data["expires_at"])
                except (ValueError, TypeError):
                    pass
            qr_identity = QRIdentity(
                qr_hash=qr_data.get("qr_hash", model.qr_hash),
                qr_payload=qr_data.get("qr_payload", ""),
                generated_at=datetime.fromisoformat(qr_data["generated_at"])
                if qr_data.get("generated_at") else datetime.now(timezone.utc),
                expires_at=qr_expires,
            )

        # Reconstruct EmergencyContact
        emergency_contact = None
        if model.emergency_contact:
            ec = model.emergency_contact
            emergency_contact = EmergencyContact(
                name=ec.get("name", ""),
                relationship=ec.get("relationship", ""),
                phone=ec.get("phone", ""),
            )

        # Reconstruct DeviceRegistrations
        devices = []
        if model.registered_devices:
            for d in model.registered_devices:
                devices.append(DeviceRegistration(
                    device_id=d.get("device_id", ""),
                    device_name=d.get("device_name"),
                    push_token=d.get("push_token"),
                    platform=d.get("platform", "web"),
                    user_agent=d.get("user_agent"),
                    ip_address=d.get("ip_address"),
                    registered_at=datetime.fromisoformat(d["registered_at"])
                    if d.get("registered_at") else datetime.now(timezone.utc),
                    last_seen_at=datetime.fromisoformat(d["last_seen_at"])
                    if d.get("last_seen_at") else datetime.now(timezone.utc),
                ))

        # Reconstruct NotificationPreference
        prefs = model.notification_preferences or {}
        notification_prefs = NotificationPreference(
            push_enabled=prefs.get("push_enabled", True),
            sms_enabled=prefs.get("sms_enabled", False),
            whatsapp_enabled=prefs.get("whatsapp_enabled", False),
            email_enabled=prefs.get("email_enabled", False),
            sound_enabled=prefs.get("sound_enabled", True),
            vibration_enabled=prefs.get("vibration_enabled", True),
        )

        # Reconstruct MedicalHistory
        medical_history = []
        if model.medical_history:
            for e in model.medical_history:
                medical_history.append(MedicalHistoryEntry(
                    condition=e.get("condition", ""),
                    diagnosed_at=e.get("diagnosed_at"),
                    notes=e.get("notes"),
                    is_active=e.get("is_active", True),
                    recorded_at=datetime.fromisoformat(e["recorded_at"])
                    if e.get("recorded_at") else datetime.now(timezone.utc),
                ))

        # Build Patient with all reconstructed VOs
        patient = Patient(
            id=model.id,
            patient_id=model.patient_id,
            demographics=demographics,
            contact=contact,
            status=status,
            qr_identity=qr_identity,
            registered_devices=devices,
            notification_preferences=notification_prefs,
            emergency_contact=emergency_contact,
            medical_history=medical_history,
            last_visit_at=model.last_visit_at,
            total_visits=model.total_visits or 0,
            merged_into_patient_id=model.merged_into_patient_id,
            reception_inquiry=model.reception_inquiry,
            version=model.version,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
        return patient

    @staticmethod
    def apply_to_model(model: PatientModel, entity: Patient) -> None:
        """Update an existing PatientModel with domain entity data.

        Args:
            model: Existing PatientModel to update.
            entity: Domain Patient entity with new data.
        """
        model.name = entity.demographics.name
        model.age = entity.demographics.age
        model.gender = entity.demographics.gender
        model.date_of_birth = entity.demographics.date_of_birth.isoformat() if entity.demographics.date_of_birth else None
        model.blood_group = entity.demographics.blood_group
        model.phone = entity.contact.phone
        model.phone_hash = entity.contact.phone_hash
        model.email = entity.contact.email
        model.address = entity.contact.address
        model.status = entity.status.status.value
        model.status_reason = entity.status.reason
        model.last_visit_at = entity.last_visit_at
        model.total_visits = entity.total_visits
        model.merged_into_patient_id = entity.merged_into_patient_id
        model.reception_inquiry = entity.reception_inquiry
        model.version = entity.version
