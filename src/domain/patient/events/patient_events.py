"""Domain events for the Patient Engine.

All PATIENT.* event types.

Patient publishes events only — never makes direct calls to other engines.
Events follow CloudEvents 1.0 specification (same pattern as Identity Engine).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class PatientEvent:
    """Base class for all Patient domain events.

    Attributes:
        event_name: Fully qualified event name (e.g., 'PATIENT.REGISTERED').
        aggregate_id: UUID of the patient aggregate.
        timestamp: When the event occurred (UTC).
        payload: Event-specific data.
    """

    event_name: str
    aggregate_id: str
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to CloudEvents-compatible dict."""
        return {
            "specversion": "1.0",
            "type": self.event_name,
            "source": "/api/v1/patient",
            "subject": self.aggregate_id,
            "time": self.timestamp.isoformat(),
            "datacontenttype": "application/json",
            "data": {
                "aggregateId": self.aggregate_id,
                **self.payload,
            },
        }


# =============================================================================
# Event Factory Functions
# =============================================================================


def patient_registered(
    patient_id: str,
    name: str,
    phone_hash: str,
    source: str = "reception",
) -> PatientEvent:
    """Patient has been registered in the system."""
    return PatientEvent(
        event_name="PATIENT.REGISTERED",
        aggregate_id=patient_id,
        payload={
            "patientId": patient_id,
            "name": name,
            "phoneHash": phone_hash,
            "source": source,
        },
    )


def patient_qr_generated(
    patient_id: str,
    qr_hash: str,
) -> PatientEvent:
    """A new QR identity has been generated for the patient."""
    return PatientEvent(
        event_name="PATIENT.QR_GENERATED",
        aggregate_id=patient_id,
        payload={
            "patientId": patient_id,
            "qrHash": qr_hash,
        },
    )


def patient_visited(
    patient_id: str,
    visit_number: int,
) -> PatientEvent:
    """Patient has started a new visit."""
    return PatientEvent(
        event_name="PATIENT.VISITED",
        aggregate_id=patient_id,
        payload={
            "patientId": patient_id,
            "visitNumber": visit_number,
        },
    )


def patient_device_registered(
    patient_id: str,
    device_id: str,
    platform: str,
) -> PatientEvent:
    """A new device has been registered for PWA notifications."""
    return PatientEvent(
        event_name="PATIENT.DEVICE_REGISTERED",
        aggregate_id=patient_id,
        payload={
            "patientId": patient_id,
            "deviceId": device_id,
            "platform": platform,
        },
    )


def patient_device_removed(
    patient_id: str,
    device_id: str,
) -> PatientEvent:
    """A device has been deregistered."""
    return PatientEvent(
        event_name="PATIENT.DEVICE_REMOVED",
        aggregate_id=patient_id,
        payload={
            "patientId": patient_id,
            "deviceId": device_id,
        },
    )


def patient_status_changed(
    patient_id: str,
    old_status: str,
    new_status: str,
    reason: str | None = None,
) -> PatientEvent:
    """Patient lifecycle status has changed (blocked, merged, etc.)."""
    payload: dict[str, Any] = {
        "patientId": patient_id,
        "oldStatus": old_status,
        "newStatus": new_status,
    }
    if reason:
        payload["reason"] = reason
    return PatientEvent(
        event_name="PATIENT.STATUS_CHANGED",
        aggregate_id=patient_id,
        payload=payload,
    )


def patient_notification_preferences_updated(
    patient_id: str,
    channels: list[str],
) -> PatientEvent:
    """Patient updated their notification preferences."""
    return PatientEvent(
        event_name="PATIENT.NOTIFICATION_PREFERENCES_UPDATED",
        aggregate_id=patient_id,
        payload={
            "patientId": patient_id,
            "enabledChannels": channels,
        },
    )


def patient_medical_history_updated(
    patient_id: str,
    condition: str,
) -> PatientEvent:
    """A medical history entry was added for the patient."""
    return PatientEvent(
        event_name="PATIENT.MEDICAL_HISTORY_UPDATED",
        aggregate_id=patient_id,
        payload={
            "patientId": patient_id,
            "condition": condition,
        },
    )


def patient_inquiry_sent(
    patient_id: str,
    inquiry_text: str,
) -> PatientEvent:
    """Patient sent an inquiry via the PWA."""
    return PatientEvent(
        event_name="PATIENT.INQUIRY_SENT",
        aggregate_id=patient_id,
        payload={
            "patientId": patient_id,
            "inquiryText": inquiry_text,
        },
    )


def patient_merged(
    patient_id: str,
    merged_into_patient_id: str,
) -> PatientEvent:
    """Patient record was merged into another (duplicate resolution)."""
    return PatientEvent(
        event_name="PATIENT.MERGED",
        aggregate_id=patient_id,
        payload={
            "patientId": patient_id,
            "mergedIntoPatientId": merged_into_patient_id,
        },
    )


# =============================================================================
# All exported event types
# =============================================================================

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
