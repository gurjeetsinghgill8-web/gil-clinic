"""Patient domain value objects."""

from src.domain.patient.value_objects.contact_info import ContactInfo
from src.domain.patient.value_objects.demographics import Demographics
from src.domain.patient.value_objects.device_registration import DeviceRegistration
from src.domain.patient.value_objects.emergency_contact import EmergencyContact
from src.domain.patient.value_objects.medical_history import MedicalHistoryEntry
from src.domain.patient.value_objects.notification_preference import NotificationPreference
from src.domain.patient.value_objects.patient_status import PatientLifecycleStatus, PatientStatus
from src.domain.patient.value_objects.qr_identity import QRIdentity

__all__ = [
    "ContactInfo",
    "Demographics",
    "DeviceRegistration",
    "EmergencyContact",
    "MedicalHistoryEntry",
    "NotificationPreference",
    "PatientLifecycleStatus",
    "PatientStatus",
    "QRIdentity",
]
