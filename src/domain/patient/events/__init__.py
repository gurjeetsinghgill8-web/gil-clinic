"""Domain events: PatientEvent types."""

from src.domain.patient.events.patient_events import (
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

__all__ = [
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
]
