"""Patient domain package.

Domain layer — pure business logic with no I/O or infrastructure dependencies.
"""

from src.domain.patient.entities import Patient
from src.domain.patient.value_objects import (
    ContactInfo,
    Demographics,
    DeviceRegistration,
    EmergencyContact,
    MedicalHistoryEntry,
    NotificationPreference,
    PatientLifecycleStatus,
    PatientStatus,
    QRIdentity,
)
from src.domain.patient.events import (
    PatientEvent,
    patient_registered,
    patient_qr_generated,
    patient_visited,
    patient_device_registered,
    patient_device_removed,
    patient_status_changed,
    patient_notification_preferences_updated,
    patient_medical_history_updated,
    patient_inquiry_sent,
    patient_merged,
)
from src.domain.patient.ports import (
    PatientRepository,
    QRCodeGenerator,
    PatientNotifier,
    PatientIdGenerator,
)
from src.domain.patient.services import PatientDomainService

__all__ = [
    # Entities
    "Patient",
    # Value Objects
    "ContactInfo",
    "Demographics",
    "DeviceRegistration",
    "EmergencyContact",
    "MedicalHistoryEntry",
    "NotificationPreference",
    "PatientLifecycleStatus",
    "PatientStatus",
    "QRIdentity",
    # Events
    "PatientEvent",
    "patient_registered",
    "patient_qr_generated",
    "patient_visited",
    "patient_device_registered",
    "patient_device_removed",
    "patient_status_changed",
    "patient_notification_preferences_updated",
    "patient_medical_history_updated",
    "patient_inquiry_sent",
    "patient_merged",
    # Ports
    "PatientRepository",
    "QRCodeGenerator",
    "PatientNotifier",
    "PatientIdGenerator",
    # Services
    "PatientDomainService",
]
