"""Patient aggregate root for the Patient Lifecycle Engine.

The Patient is the central aggregate in the patient bounded context.
It manages:
- Demographics and contact information
- QR identity for PWA login
- Registered devices for push notifications
- Notification preferences
- Medical history
- Patient status (active/inactive/blocked/merged)
- Visit history references

Patient publishes events — it never calls other aggregates directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from src.shared.domain.base_entity import BaseEntity
from src.domain.patient.value_objects.patient_status import PatientStatus
from src.domain.patient.value_objects.notification_preference import NotificationPreference

if TYPE_CHECKING:
    from src.domain.patient.value_objects.contact_info import ContactInfo
    from src.domain.patient.value_objects.demographics import Demographics
    from src.domain.patient.value_objects.device_registration import DeviceRegistration
    from src.domain.patient.value_objects.emergency_contact import EmergencyContact
    from src.domain.patient.value_objects.medical_history import MedicalHistoryEntry
    from src.domain.patient.value_objects.qr_identity import QRIdentity


INACTIVITY_DAYS: int = 90


@dataclass
class Patient(BaseEntity):
    """Patient aggregate root.

    Attributes:
        patient_id: Human-readable ID (e.g., 'CQ-20260714-001').
        demographics: Patient's name, age, gender, DOB, blood group.
        contact: Phone (encrypted + hashed), email (encrypted), address.
        status: Lifecycle status: active, inactive, blocked, merged.
        qr_identity: QR-based identity for PWA login.
        registered_devices: List of registered devices for notifications.
        notification_preferences: Per-channel notification settings.
        emergency_contact: Optional emergency contact person.
        medical_history: List of medical conditions.
        last_visit_at: Timestamp of the most recent visit.
        total_visits: Running count of visits.
        merged_into_patient_id: If merged, points to the surviving patient.
        reception_inquiry: Optional inquiry text set by patient via PWA.
    """

    patient_id: str
    demographics: Demographics
    contact: ContactInfo
    status: PatientStatus
    qr_identity: QRIdentity | None = None
    registered_devices: list = field(default_factory=list)  # list[DeviceRegistration]
    notification_preferences: NotificationPreference = field(
        default_factory=lambda: NotificationPreference.default()
    )
    emergency_contact: EmergencyContact | None = None
    medical_history: list = field(default_factory=list)  # list[MedicalHistoryEntry]
    last_visit_at: datetime | None = None
    total_visits: int = 0
    merged_into_patient_id: str | None = None
    reception_inquiry: str | None = None

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def register(
        cls,
        patient_id: str,
        demographics: Demographics,
        contact: ContactInfo,
        qr_identity: QRIdentity | None = None,
        emergency_contact: EmergencyContact | None = None,
    ) -> Patient:
        """Register a new patient.

        Args:
            patient_id: Auto-generated human-readable ID.
            demographics: Name, age, gender, etc.
            contact: Phone (hashed), email, address.
            qr_identity: Optional initial QR identity.
            emergency_contact: Optional emergency contact.

        Returns:
            A new active Patient instance.
        """
        # TODO: Publish PATIENT.REGISTERED domain event
        return cls(
            patient_id=patient_id,
            demographics=demographics,
            contact=contact,
            status=PatientStatus.active(),
            qr_identity=qr_identity,
            emergency_contact=emergency_contact,
        )

    # ------------------------------------------------------------------
    # QR Identity
    # ------------------------------------------------------------------

    def has_qr_identity(self) -> bool:
        """Check if QR identity is set."""
        return self.qr_identity is not None

    def assign_qr_identity(self, qr_identity: QRIdentity) -> None:
        """Assign or replace the patient's QR identity.

        Args:
            qr_identity: New QR identity to assign.
        """
        self.qr_identity = qr_identity
        self.touch()
        # TODO: Publish PATIENT.QR_GENERATED event

    def verify_qr_identity(self) -> bool:
        """Check if the current QR identity is valid (not expired).

        Returns:
            True if QR is valid.
        """
        if not self.qr_identity:
            return False
        return self.qr_identity.is_valid

    # ------------------------------------------------------------------
    # Device Registration (PWA)
    # ------------------------------------------------------------------

    def register_device(self, device: DeviceRegistration) -> None:
        """Register a device for push notifications / PWA login.

        Args:
            device: Device to register.
        """
        # Update existing device registration
        existing = [d for d in self.registered_devices if d.device_id == device.device_id]
        if existing:
            idx = self.registered_devices.index(existing[0])
            self.registered_devices[idx] = device.seen_now()
        else:
            self.registered_devices.append(device)
        self.touch()
        # TODO: Publish PATIENT.DEVICE_REGISTERED event

    def remove_device(self, device_id: str) -> bool:
        """Remove a registered device.

        Args:
            device_id: Device identifier to remove.

        Returns:
            True if device was found and removed.
        """
        before = len(self.registered_devices)
        self.registered_devices = [d for d in self.registered_devices if d.device_id != device_id]
        if len(self.registered_devices) < before:
            self.touch()
            # TODO: Publish PATIENT.DEVICE_REMOVED event
            return True
        return False

    def get_device(self, device_id: str) -> DeviceRegistration | None:
        """Get a registered device by ID."""
        for d in self.registered_devices:
            if d.device_id == device_id:
                return d
        return None

    @property
    def device_count(self) -> int:
        """Number of registered devices."""
        return len(self.registered_devices)

    # ------------------------------------------------------------------
    # Notification Preferences
    # ------------------------------------------------------------------

    def update_notification_preferences(self, prefs: NotificationPreference) -> None:
        """Update notification channel preferences.

        Args:
            prefs: New notification preferences.
        """
        self.notification_preferences = prefs
        self.touch()
        # TODO: Publish PATIENT.NOTIFICATION_PREFERENCES_UPDATED event

    # ------------------------------------------------------------------
    # Visit Tracking
    # ------------------------------------------------------------------

    def record_visit(self) -> None:
        """Record a visit (increments counter and updates timestamp)."""
        self.last_visit_at = datetime.now(timezone.utc)
        self.total_visits += 1
        self.touch()
        # TODO: Publish PATIENT.VISITED event

    @property
    def is_first_visit(self) -> bool:
        """Check if the patient has never visited."""
        return self.total_visits == 0

    @property
    def days_since_last_visit(self) -> int | None:
        """Days since the patient's last visit."""
        if not self.last_visit_at:
            return None
        delta = datetime.now(timezone.utc) - self.last_visit_at
        return delta.days

    # ------------------------------------------------------------------
    # Medical History
    # ------------------------------------------------------------------

    def add_medical_history(self, entry: MedicalHistoryEntry) -> None:
        """Add a medical history entry.

        Args:
            entry: History entry to add.
        """
        self.medical_history.append(entry)
        self.touch()
        # TODO: Publish PATIENT.MEDICAL_HISTORY_UPDATED event

    # ------------------------------------------------------------------
    # Status Management
    # ------------------------------------------------------------------

    def mark_inactive(self) -> None:
        """Mark the patient as inactive after prolonged inactivity."""
        self.status = PatientStatus.inactive()
        self.touch()

    def mark_blocked(self, reason: str) -> None:
        """Block the patient for policy violation.

        Args:
            reason: Why the patient was blocked.
        """
        self.status = PatientStatus.blocked(reason=reason)
        self.touch()
        # TODO: Publish PATIENT.BLOCKED event

    def mark_merged(self, target_patient_id: str) -> None:
        """Merge this patient record into another (duplicate resolution).

        Args:
            target_patient_id: ID of the surviving patient record.
        """
        self.status = PatientStatus.merged(reason=f"Merged into {target_patient_id}")
        self.merged_into_patient_id = target_patient_id
        self.touch()
        # TODO: Publish PATIENT.MERGED event

    def reactivate(self) -> None:
        """Reactivate a previously inactive patient."""
        self.status = PatientStatus.active()
        self.touch()
        # TODO: Publish PATIENT.REACTIVATED event

    @property
    def can_register_visit(self) -> bool:
        """Check if this patient can register for a new visit."""
        return self.status.can_visit

    # ------------------------------------------------------------------
    # Inquiry (set from patient PWA)
    # ------------------------------------------------------------------

    def set_inquiry(self, inquiry_text: str) -> None:
        """Set a reception inquiry (patient presses 'Ask Reception').

        Args:
            inquiry_text: The inquiry message.
        """
        self.reception_inquiry = inquiry_text
        self.touch()
        # TODO: Publish PATIENT.INQUIRY_SENT event

    def clear_inquiry(self) -> None:
        """Clear the current inquiry (staff has responded)."""
        self.reception_inquiry = None
        self.touch()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def display_name(self) -> str:
        """Short display name for UI."""
        return self.demographics.name

    @property
    def age_gender_display(self) -> str:
        """Age/gender string like '45/M'."""
        gender_short = self.demographics.gender[0].upper()
        return f"{self.demographics.age}/{gender_short}"

    def __repr__(self) -> str:
        return (
            f"<Patient id={self.patient_id} "
            f"name={self.demographics.name} "
            f"status={self.status.status.value} "
            f"visits={self.total_visits}>"
        )
