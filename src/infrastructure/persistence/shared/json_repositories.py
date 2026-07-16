"""JSON-backed repository implementations.

Implements the domain repository protocols (PatientRepository, QueueRepository,
AuditRepository) using local JSON file storage.

Each repository method mirrors the SQLAlchemy repository but reads/writes
to JSON files via local_json_db.py. This allows the app to run without
any database — perfect for development, demo, or offline-first scenarios.

Usage:
    # When DB is unavailable, auto-fallback:
    from src.infrastructure.persistence.shared.json_repositories import (
        JsonPatientRepository,
        JsonQueueRepository,
    )
    repo = JsonPatientRepository()
    patient = await repo.get_by_phone_hash(phone_hash)
"""

from __future__ import annotations

import uuid as _uuid
from datetime import date, datetime, timezone
from typing import Any, Optional

from src.domain.patient.entities.patient import Patient
from src.domain.patient.value_objects.contact_info import ContactInfo
from src.domain.patient.value_objects.demographics import Demographics
from src.domain.patient.value_objects.device_registration import DeviceRegistration
from src.domain.patient.value_objects.emergency_contact import EmergencyContact
from src.domain.patient.value_objects.medical_history import MedicalHistoryEntry
from src.domain.patient.value_objects.notification_preference import (
    NotificationPreference,
)
from src.domain.patient.value_objects.patient_status import (
    PatientLifecycleStatus,
    PatientStatus,
)
from src.domain.patient.value_objects.qr_identity import QRIdentity
from src.domain.queue.entities.queue_entry import QueueEntry
from src.domain.queue.value_objects.queue_status import QueueStatus
from src.infrastructure.persistence.shared.local_json_db import (
    load_patients,
    save_patients,
    load_queue_entries,
    save_queue_entries,
    load_audit_log,
    save_audit_log,
    load_meta,
    save_meta,
    get_next_sequence,
    get_next_token_number as _json_get_next_token,
    load_all_patients,
    load_all_queue_entries,
    check_json_health,
)


# =========================================================================
# Helpers
# =========================================================================


def _serialize_datetime(dt: datetime | None) -> str | None:
    """Serialize a datetime to ISO string for JSON storage.

    Args:
        dt: Datetime to serialize.

    Returns:
        ISO string or None.
    """
    return dt.isoformat() if dt else None


def _deserialize_datetime(val: str | None) -> datetime | None:
    """Deserialize an ISO string back to a datetime.

    Args:
        val: ISO string.

    Returns:
        Datetime or None.
    """
    if not val:
        return None
    try:
        return datetime.fromisoformat(val)
    except (ValueError, TypeError):
        return None


def _today_prefix() -> str:
    """Get today's date prefix for patient/token IDs.

    Returns:
        Date string like '20260714'.
    """
    return date.today().strftime("%Y%m%d")


# =========================================================================
# JsonPatientRepository
# =========================================================================


class JsonPatientRepository:
    """JSON-backed PatientRepository implementation.

    Implements the same protocol as SqlAlchemyPatientRepository.
    All data is stored as JSON files in cardioqueue_data/.
    """

    def __init__(self) -> None:
        self._today = _today_prefix()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def save(self, patient: Patient) -> None:
        """Persist a patient to JSON storage.

        Handles both insert (version==1) and update (version>1).

        Args:
            patient: Patient aggregate to save.
        """
        patients = load_patients()
        existing_idx = None
        for i, p in enumerate(patients):
            if p.get("patient_id") == patient.patient_id:
                existing_idx = i
                break

        patient_dict = _patient_to_dict(patient)

        if existing_idx is not None:
            # Update existing — increment version
            existing = patients[existing_idx]
            patient_dict["version"] = existing.get("version", 0) + 1
            patient_dict["updated_at"] = _serialize_datetime(
                datetime.now(timezone.utc)
            )
            patients[existing_idx] = patient_dict
        else:
            # New insert
            patient_dict["version"] = 1
            patient_dict["created_at"] = _serialize_datetime(
                datetime.now(timezone.utc)
            )
            patient_dict["updated_at"] = patient_dict["created_at"]
            patients.append(patient_dict)

        save_patients(patients)

    async def delete(self, patient_uuid: str) -> bool:
        """Hard-delete a patient record.

        Args:
            patient_uuid: UUID of the patient to delete.

        Returns:
            True if deleted, False if not found.
        """
        patients = load_patients()
        for i, p in enumerate(patients):
            if p.get("id") == patient_uuid or p.get("patient_id") == patient_uuid:
                patients.pop(i)
                save_patients(patients)
                return True
        # Also check other date folders
        all_patients = load_all_patients()
        for i, p in enumerate(all_patients):
            if p.get("id") == patient_uuid or p.get("patient_id") == patient_uuid:
                return True  # Found but belongs to different day — skip delete
        return False

    # ------------------------------------------------------------------
    # Read (single)
    # ------------------------------------------------------------------

    async def get_by_id(self, patient_uuid: str) -> Patient | None:
        """Get a patient by internal UUID.

        Args:
            patient_uuid: UUID string.

        Returns:
            Patient if found, None otherwise.
        """
        # Check today first
        for p in load_patients():
            if p.get("id") == patient_uuid:
                return _patient_from_dict(p)
        # Check all dates
        for folder in _list_date_folders():
            for p in load_patients(folder):
                if p.get("id") == patient_uuid:
                    return _patient_from_dict(p)
        return None

    async def get_by_patient_id(self, patient_id: str) -> Patient | None:
        """Get a patient by human-readable ID.

        Args:
            patient_id: ID like 'CQ-20260714-001'.

        Returns:
            Patient if found, None otherwise.
        """
        for p in load_patients():
            if p.get("patient_id") == patient_id:
                return _patient_from_dict(p)
        for folder in _list_date_folders():
            for p in load_patients(folder):
                if p.get("patient_id") == patient_id:
                    return _patient_from_dict(p)
        return None

    async def get_by_phone_hash(self, phone_hash: str) -> Patient | None:
        """Get a patient by phone hash.

        Args:
            phone_hash: SHA-256 hash of phone number.

        Returns:
            Patient if found, None otherwise.
        """
        for p in load_patients():
            if p.get("phone_hash") == phone_hash:
                return _patient_from_dict(p)
        for folder in _list_date_folders():
            for p in load_patients(folder):
                if p.get("phone_hash") == phone_hash:
                    return _patient_from_dict(p)
        return None

    async def get_by_qr_hash(self, qr_hash: str) -> Patient | None:
        """Get a patient by QR identity hash.

        Args:
            qr_hash: SHA-256 hash of QR payload.

        Returns:
            Patient if found, None otherwise.
        """
        for p in load_patients():
            qr = p.get("qr_identity") or {}
            if qr.get("qr_hash") == qr_hash or p.get("qr_hash") == qr_hash:
                return _patient_from_dict(p)
        for folder in _list_date_folders():
            for p in load_patients(folder):
                qr = p.get("qr_identity") or {}
                if qr.get("qr_hash") == qr_hash or p.get("qr_hash") == qr_hash:
                    return _patient_from_dict(p)
        return None

    async def exists_by_phone_hash(self, phone_hash: str) -> bool:
        """Check if a phone number is already registered.

        Args:
            phone_hash: SHA-256 hash of phone number.

        Returns:
            True if phone exists.
        """
        return await self.get_by_phone_hash(phone_hash) is not None

    # ------------------------------------------------------------------
    # Read (list)
    # ------------------------------------------------------------------

    async def list_active(
        self, offset: int = 0, limit: int = 100
    ) -> list[Patient]:
        """List active patients with pagination.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to return.

        Returns:
            List of Patient aggregates.
        """
        all_patients = []
        for p in load_all_patients():
            if p.get("status") in ("active", None):
                p_obj = _patient_from_dict(p)
                if p_obj and p_obj.status.can_visit:
                    all_patients.append(p_obj)
        return all_patients[offset : offset + limit]

    async def list_by_status(
        self, status: str, offset: int = 0, limit: int = 100
    ) -> list[Patient]:
        """List patients by lifecycle status.

        Args:
            status: Status filter ('active', 'inactive', 'blocked', 'merged').
            offset: Number of records to skip.
            limit: Maximum records to return.

        Returns:
            List of matching Patient aggregates.
        """
        result = []
        for p in load_all_patients():
            if p.get("status") == status:
                p_obj = _patient_from_dict(p)
                if p_obj:
                    result.append(p_obj)
        return result[offset : offset + limit]

    async def search_by_name(
        self, query: str, offset: int = 0, limit: int = 20
    ) -> list[Patient]:
        """Search patients by name (case-insensitive substring match).

        Args:
            query: Name search string.
            offset: Number of records to skip.
            limit: Maximum records to return.

        Returns:
            List of matching Patient aggregates.
        """
        q = query.lower()
        result = []
        for p in load_all_patients():
            name = (p.get("name") or "").lower()
            if q in name:
                p_obj = _patient_from_dict(p)
                if p_obj:
                    result.append(p_obj)
        return result[offset : offset + limit]

    async def count(self, status: str | None = None) -> int:
        """Count patients, optionally filtered by status.

        Args:
            status: Optional status filter.

        Returns:
            Total count of matching patients.
        """
        count = 0
        for p in load_all_patients():
            if status is None or p.get("status") == status:
                count += 1
        return count

    async def get_next_sequence_number(self, date_prefix: str) -> int:
        """Get the next daily sequence number for patient ID generation.

        Args:
            date_prefix: Date prefix like '20260714'.

        Returns:
            Next sequence number (1-based).
        """
        return get_next_sequence("patient_sequence", date_prefix)


# =========================================================================
# JsonQueueRepository
# =========================================================================


class JsonQueueRepository:
    """JSON-backed QueueRepository implementation.

    Implements the same protocol as SqlAlchemyQueueRepository.
    Uses JSON file storage in cardioqueue_data/.
    """

    def __init__(self) -> None:
        self._today = _today_prefix()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def save(self, entry: QueueEntry) -> None:
        """Persist a queue entry to JSON storage.

        Args:
            entry: QueueEntry to save.
        """
        entries = load_queue_entries()
        existing_idx = None
        for i, e in enumerate(entries):
            if e.get("id") == str(entry.id):
                existing_idx = i
                break

        entry_dict = _queue_entry_to_dict(entry)

        if existing_idx is not None:
            existing = entries[existing_idx]
            entry_dict["version"] = existing.get("version", 0) + 1
            entry_dict["updated_at"] = _serialize_datetime(
                datetime.now(timezone.utc)
            )
            entries[existing_idx] = entry_dict
        else:
            entry_dict["version"] = 1
            entry_dict["created_at"] = _serialize_datetime(
                datetime.now(timezone.utc)
            )
            entry_dict["updated_at"] = entry_dict["created_at"]
            entries.append(entry_dict)

        save_queue_entries(entries)

    async def save_many(self, entries: list[QueueEntry]) -> None:
        """Persist multiple queue entries in batch.

        Args:
            entries: List of QueueEntry to save.
        """
        for entry in entries:
            await self.save(entry)

    async def delete(self, entry_id: str) -> None:
        """Delete a queue entry by ID.

        Args:
            entry_id: UUID of the entry to delete.
        """
        entries = load_queue_entries()
        for i, e in enumerate(entries):
            if e.get("id") == entry_id:
                entries.pop(i)
                save_queue_entries(entries)
                return

    # ------------------------------------------------------------------
    # Read (single)
    # ------------------------------------------------------------------

    async def get_by_id(self, entry_uuid: str) -> QueueEntry | None:
        """Get a queue entry by its UUID.

        Args:
            entry_uuid: UUID string.

        Returns:
            QueueEntry if found, None otherwise.
        """
        # Check today first
        for e in load_queue_entries():
            if e.get("id") == entry_uuid:
                return _queue_entry_from_dict(e)
        # Check older dates
        for folder in _list_date_folders():
            for e in load_queue_entries(folder):
                if e.get("id") == entry_uuid:
                    return _queue_entry_from_dict(e)
        return None

    async def get_active_by_patient(
        self, patient_uuid: str
    ) -> list[QueueEntry]:
        """Get all non-terminal queue entries for a patient.

        Args:
            patient_uuid: UUID of the patient.

        Returns:
            List of active QueueEntry objects.
        """
        terminal_statuses = {"CANCELLED", "NO_SHOW", "DELIVERED"}
        result = []
        for e in load_queue_entries():
            if (
                e.get("patient_uuid") == patient_uuid
                and e.get("status", "WAITING") not in terminal_statuses
            ):
                entry = _queue_entry_from_dict(e)
                if entry:
                    result.append(entry)
        result.sort(key=lambda x: x.display_order)
        return result

    async def list_by_department(
        self,
        department: str,
        status_filter: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[QueueEntry]:
        """List queue entries for a department.

        Args:
            department: Department name.
            status_filter: Optional status filter.
            offset: Number of records to skip.
            limit: Maximum records to return.

        Returns:
            List of QueueEntry objects.
        """
        result = []
        for e in load_queue_entries():
            if e.get("department") != department:
                continue
            if status_filter and e.get("status") != status_filter:
                continue
            entry = _queue_entry_from_dict(e)
            if entry:
                result.append(entry)

        # Sort by display order then token number
        result.sort(key=lambda x: (x.display_order, x.token_number))
        return result[offset : offset + limit]

    async def list_by_visit(self, visit_id: str) -> list[QueueEntry]:
        """List all queue entries for a specific visit.

        Args:
            visit_id: Visit ID.

        Returns:
            List of QueueEntry objects.
        """
        result = []
        for e in load_queue_entries():
            if e.get("visit_id") == visit_id:
                entry = _queue_entry_from_dict(e)
                if entry:
                    result.append(entry)
        result.sort(key=lambda x: x.display_order)
        return result

    async def get_next_token_number(
        self, service_code: str, date_prefix: str
    ) -> int:
        """Get the next sequential token number for a service today.

        Args:
            service_code: Service code (ECG, Echo, etc.).
            date_prefix: Date prefix like '20260714'.

        Returns:
            The next available token number (starts at 1).
        """
        return _json_get_next_token(service_code, date_prefix)

    async def get_queue_depth(self, service_code: str) -> int:
        """Count WAITING entries for a service.

        Args:
            service_code: Service code.

        Returns:
            Number of WAITING entries.
        """
        count = 0
        for e in load_queue_entries():
            if e.get("service_code") == service_code and e.get("status") == "WAITING":
                count += 1
        return count

    async def count_by_status(self, department: str, status: str) -> int:
        """Count entries in a given status for a department.

        Args:
            department: Department name.
            status: Status to count.

        Returns:
            Count of matching entries.
        """
        count = 0
        for e in load_queue_entries():
            if e.get("department") == department and e.get("status") == status:
                count += 1
        return count

    async def list_patient_queue(self, patient_uuid: str) -> list[QueueEntry]:
        """Get all queue entries for a patient.

        Args:
            patient_uuid: UUID of the patient.

        Returns:
            List of QueueEntry objects (newest first).
        """
        result = []
        # Load from today first
        for e in load_queue_entries():
            if e.get("patient_uuid") == patient_uuid:
                entry = _queue_entry_from_dict(e)
                if entry:
                    result.append(entry)
        # Check older dates
        for folder in _list_date_folders():
            for e in load_queue_entries(folder):
                if e.get("patient_uuid") == patient_uuid:
                    entry = _queue_entry_from_dict(e)
                    if entry:
                        result.append(entry)
        result.sort(key=lambda x: x.created_at, reverse=True)
        return result

    async def list_by_status(
        self, status: str, offset: int = 0, limit: int = 100
    ) -> list[QueueEntry]:
        """List queue entries by status across all departments.

        Args:
            status: Status filter.
            offset: Number of records to skip.
            limit: Maximum records to return.

        Returns:
            List of matching QueueEntry objects.
        """
        result = []
        today = date.today().isoformat()
        for e in load_queue_entries():
            if e.get("status") != status:
                continue
            entry = _queue_entry_from_dict(e)
            if entry:
                result.append(entry)
        result.sort(key=lambda x: x.created_at, reverse=True)
        return result[offset : offset + limit]

    # ------------------------------------------------------------------
    # Alert system
    # ------------------------------------------------------------------

    async def set_alert(self, entry_id: str, message: str) -> None:
        """Set pending_alert flag and message on a queue entry.

        Args:
            entry_id: UUID of the queue entry.
            message: Alert message to show to the patient.
        """
        entries = load_queue_entries()
        for e in entries:
            if e.get("id") == entry_id:
                e["pending_alert"] = True
                e["alert_message"] = message
                e["updated_at"] = _serialize_datetime(datetime.now(timezone.utc))
                save_queue_entries(entries)
                return

        # Check older date folders
        for folder in _list_date_folders():
            entries = load_queue_entries(folder)
            for e in entries:
                if e.get("id") == entry_id:
                    e["pending_alert"] = True
                    e["alert_message"] = message
                    e["updated_at"] = _serialize_datetime(
                        datetime.now(timezone.utc)
                    )
                    save_queue_entries(entries, folder)
                    return

        raise ValueError(f"Queue entry '{entry_id}' not found for alert")

    async def check_alert(self, entry_id: str) -> tuple[bool, str | None]:
        """Check if a queue entry has a pending alert.

        Args:
            entry_id: UUID of the queue entry.

        Returns:
            Tuple of (has_alert, alert_message).
        """
        for e in load_queue_entries():
            if e.get("id") == entry_id:
                return bool(e.get("pending_alert")), e.get("alert_message")
        for folder in _list_date_folders():
            for e in load_queue_entries(folder):
                if e.get("id") == entry_id:
                    return bool(e.get("pending_alert")), e.get("alert_message")
        return False, None

    async def clear_alert(self, entry_id: str) -> None:
        """Clear the pending_alert flag on a queue entry.

        Args:
            entry_id: UUID of the queue entry.
        """
        entries = load_queue_entries()
        for e in entries:
            if e.get("id") == entry_id:
                e["pending_alert"] = False
                e["alert_message"] = None
                e["updated_at"] = _serialize_datetime(datetime.now(timezone.utc))
                save_queue_entries(entries)
                return


# =========================================================================
# JsonAuditRepository
# =========================================================================


class JsonAuditRepository:
    """JSON-backed append-only audit repository.

    Implements the same interface as SqlAlchemyAuditRepository.
    Each save() appends to today's audit_log.json.
    """

    def __init__(self) -> None:
        self._today = _today_prefix()

    async def save(
        self,
        actor: str,
        action: str,
        resource_type: str = "queue_entry",
        resource_id: str = "",
        old_status: str | None = None,
        new_status: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Write a single audit log entry.

        Args:
            actor: Staff ID who performed the action.
            action: Action performed.
            resource_type: Type of resource affected.
            resource_id: ID of the resource.
            old_status: Previous status.
            new_status: New status.
            details: Additional context.
        """
        entries = load_audit_log()
        entry = {
            "id": str(_uuid.uuid4()),
            "actor": actor,
            "action": action,
            "resource_type": resource_type,
            "resource_id": str(resource_id) if resource_id else "",
            "old_status": old_status,
            "new_status": new_status,
            "details": details or {},
            "created_at": _serialize_datetime(datetime.now(timezone.utc)),
        }
        entries.append(entry)
        save_audit_log(entries)

    async def save_many(self, entries: list[dict[str, Any]]) -> None:
        """Bulk write audit log entries.

        Args:
            entries: List of audit entry dicts.
        """
        existing = load_audit_log()
        now = _serialize_datetime(datetime.now(timezone.utc))
        for e in entries:
            existing.append({
                "id": str(_uuid.uuid4()),
                "actor": e.get("actor", "system"),
                "action": e.get("action", "UNKNOWN"),
                "resource_type": e.get("resource_type", "queue_entry"),
                "resource_id": str(e.get("resource_id", "")),
                "old_status": e.get("old_status"),
                "new_status": e.get("new_status"),
                "details": e.get("details", {}),
                "created_at": e.get("created_at", now),
            })
        save_audit_log(existing)


# =========================================================================
# Serialization helpers
# =========================================================================


def _patient_to_dict(patient: Patient) -> dict[str, Any]:
    """Convert a Patient domain entity to a JSON-serializable dict.

    Args:
        patient: Patient aggregate to convert.

    Returns:
        Dict suitable for JSON storage.
    """
    return {
        "id": str(patient.id),
        "patient_id": patient.patient_id,
        "name": patient.demographics.name,
        "age": patient.demographics.age,
        "gender": patient.demographics.gender,
        "date_of_birth": patient.demographics.date_of_birth.isoformat()
        if patient.demographics.date_of_birth else None,
        "blood_group": patient.demographics.blood_group,
        "phone": patient.contact.phone,
        "phone_hash": patient.contact.phone_hash,
        "email": patient.contact.email,
        "address": patient.contact.address,
        "emergency_contact": {
            "name": patient.emergency_contact.name,
            "relationship": patient.emergency_contact.relationship,
            "phone": patient.emergency_contact.phone,
        } if patient.emergency_contact else None,
        "qr_hash": patient.qr_identity.qr_hash if patient.qr_identity else None,
        "qr_identity": {
            "qr_hash": patient.qr_identity.qr_hash,
            "qr_payload": patient.qr_identity.qr_payload,
            "generated_at": _serialize_datetime(patient.qr_identity.generated_at),
            "expires_at": _serialize_datetime(patient.qr_identity.expires_at),
        } if patient.qr_identity else None,
        "status": patient.status.status.value,
        "status_reason": patient.status.reason,
        "registered_devices": [
            {
                "device_id": d.device_id,
                "device_name": d.device_name,
                "push_token": d.push_token,
                "platform": d.platform,
                "user_agent": d.user_agent,
                "ip_address": d.ip_address,
                "registered_at": _serialize_datetime(d.registered_at),
                "last_seen_at": _serialize_datetime(d.last_seen_at),
            }
            for d in patient.registered_devices
        ] if patient.registered_devices else [],
        "notification_preferences": {
            "push_enabled": patient.notification_preferences.push_enabled,
            "sms_enabled": patient.notification_preferences.sms_enabled,
            "whatsapp_enabled": patient.notification_preferences.whatsapp_enabled,
            "email_enabled": patient.notification_preferences.email_enabled,
            "sound_enabled": patient.notification_preferences.sound_enabled,
            "vibration_enabled": patient.notification_preferences.vibration_enabled,
        },
        "medical_history": [
            {
                "condition": e.condition,
                "diagnosed_at": e.diagnosed_at,
                "notes": e.notes,
                "is_active": e.is_active,
                "recorded_at": _serialize_datetime(e.recorded_at),
            }
            for e in patient.medical_history
        ] if patient.medical_history else [],
        "last_visit_at": _serialize_datetime(patient.last_visit_at),
        "total_visits": patient.total_visits,
        "merged_into_patient_id": patient.merged_into_patient_id,
        "reception_inquiry": patient.reception_inquiry,
        "version": patient.version,
        "created_at": _serialize_datetime(patient.created_at),
        "updated_at": _serialize_datetime(patient.updated_at),
    }


def _patient_from_dict(data: dict[str, Any]) -> Patient | None:
    """Reconstruct a Patient domain entity from a JSON dict.

    Args:
        data: Dict loaded from JSON storage.

    Returns:
        Patient aggregate, or None if data is invalid.
    """
    if not data:
        return None

    # Demographics
    dob = None
    if data.get("date_of_birth"):
        try:
            dob = _deserialize_datetime(data["date_of_birth"]).date()
        except (ValueError, TypeError, AttributeError):
            pass

    demographics = Demographics.create(
        name=data.get("name", ""),
        age=data.get("age", 0),
        gender=data.get("gender", ""),
        date_of_birth=dob,
        blood_group=data.get("blood_group"),
    )

    # ContactInfo
    contact = ContactInfo.create(
        phone=data.get("phone", ""),
        phone_hash=data.get("phone_hash", ""),
        email=data.get("email"),
        address=data.get("address"),
    )

    # PatientStatus
    try:
        status_enum = PatientLifecycleStatus(data.get("status", "active"))
    except ValueError:
        status_enum = PatientLifecycleStatus.ACTIVE
    status = PatientStatus(status=status_enum, reason=data.get("status_reason"))

    # QRIdentity
    qr_identity = None
    qr_data = data.get("qr_identity")
    if qr_data and data.get("qr_hash"):
        qr_identity = QRIdentity(
            qr_hash=qr_data.get("qr_hash", data["qr_hash"]),
            qr_payload=qr_data.get("qr_payload", ""),
            generated_at=_deserialize_datetime(qr_data.get("generated_at"))
            or datetime.now(timezone.utc),
            expires_at=_deserialize_datetime(qr_data.get("expires_at")),
        )

    # EmergencyContact
    emergency_contact = None
    ec = data.get("emergency_contact")
    if ec:
        emergency_contact = EmergencyContact(
            name=ec.get("name", ""),
            relationship=ec.get("relationship", ""),
            phone=ec.get("phone", ""),
        )

    # DeviceRegistrations
    devices = []
    for d in data.get("registered_devices") or []:
        devices.append(DeviceRegistration(
            device_id=d.get("device_id", ""),
            device_name=d.get("device_name"),
            push_token=d.get("push_token"),
            platform=d.get("platform", "web"),
            user_agent=d.get("user_agent"),
            ip_address=d.get("ip_address"),
            registered_at=_deserialize_datetime(d.get("registered_at"))
            or datetime.now(timezone.utc),
            last_seen_at=_deserialize_datetime(d.get("last_seen_at"))
            or datetime.now(timezone.utc),
        ))

    # NotificationPreference
    prefs = data.get("notification_preferences") or {}
    notification_prefs = NotificationPreference(
        push_enabled=prefs.get("push_enabled", True),
        sms_enabled=prefs.get("sms_enabled", False),
        whatsapp_enabled=prefs.get("whatsapp_enabled", False),
        email_enabled=prefs.get("email_enabled", False),
        sound_enabled=prefs.get("sound_enabled", True),
        vibration_enabled=prefs.get("vibration_enabled", True),
    )

    # MedicalHistory
    medical_history = []
    for e in data.get("medical_history") or []:
        medical_history.append(MedicalHistoryEntry(
            condition=e.get("condition", ""),
            diagnosed_at=e.get("diagnosed_at"),
            notes=e.get("notes"),
            is_active=e.get("is_active", True),
            recorded_at=_deserialize_datetime(e.get("recorded_at"))
            or datetime.now(timezone.utc),
        ))

    # Build Patient
    id_val = data.get("id")
    if id_val and isinstance(id_val, str):
        try:
            id_uuid = _uuid.UUID(id_val)
        except (ValueError, TypeError):
            id_uuid = _uuid.uuid4()
    else:
        id_uuid = _uuid.uuid4()

    patient = Patient(
        id=id_uuid,
        patient_id=data.get("patient_id", ""),
        demographics=demographics,
        contact=contact,
        status=status,
        qr_identity=qr_identity,
        registered_devices=devices,
        notification_preferences=notification_prefs,
        emergency_contact=emergency_contact,
        medical_history=medical_history,
        last_visit_at=_deserialize_datetime(data.get("last_visit_at")),
        total_visits=data.get("total_visits", 0),
        merged_into_patient_id=data.get("merged_into_patient_id"),
        reception_inquiry=data.get("reception_inquiry"),
        version=data.get("version", 1),
        created_at=_deserialize_datetime(data.get("created_at"))
        or datetime.now(timezone.utc),
        updated_at=_deserialize_datetime(data.get("updated_at"))
        or datetime.now(timezone.utc),
    )
    return patient


def _queue_entry_to_dict(entry: QueueEntry) -> dict[str, Any]:
    """Convert a QueueEntry domain entity to a JSON-serializable dict.

    Args:
        entry: QueueEntry to convert.

    Returns:
        Dict suitable for JSON storage.
    """
    return {
        "id": str(entry.id),
        "visit_id": entry.visit_id,
        "patient_id": entry.patient_id,
        "patient_uuid": entry.patient_uuid,
        "patient_name": entry.patient_name,
        "service_code": entry.service_code,
        "token_number": entry.token_number,
        "department": entry.department,
        "room": entry.room,
        "status": entry.status.value if entry.status else "WAITING",
        "priority": entry.priority,
        "display_order": entry.display_order,
        "created_by": entry.created_by,
        "updated_by": entry.updated_by,
        "pending_alert": entry.pending_alert,
        "alert_message": entry.alert_message,
        "notes": entry.notes,
        "called_at": _serialize_datetime(entry.called_at),
        "started_at": _serialize_datetime(entry.started_at),
        "completed_at": _serialize_datetime(entry.completed_at),
        "report_ready_at": _serialize_datetime(entry.report_ready_at),
        "delivered_at": _serialize_datetime(entry.delivered_at),
        "version": entry.version,
        "created_at": _serialize_datetime(entry.created_at),
        "updated_at": _serialize_datetime(entry.updated_at),
    }


def _queue_entry_from_dict(data: dict[str, Any]) -> QueueEntry | None:
    """Reconstruct a QueueEntry domain entity from a JSON dict.

    Args:
        data: Dict loaded from JSON storage.

    Returns:
        QueueEntry aggregate, or None if data is invalid.
    """
    if not data:
        return None

    # Parse status
    try:
        status = QueueStatus(data.get("status", "WAITING"))
    except (ValueError, TypeError):
        status = QueueStatus.WAITING

    # Parse ID
    id_val = data.get("id")
    if id_val and isinstance(id_val, str):
        try:
            id_uuid = _uuid.UUID(id_val)
        except (ValueError, TypeError):
            id_uuid = _uuid.uuid4()
    else:
        id_uuid = _uuid.uuid4()

    entry = QueueEntry(
        id=id_uuid,
        visit_id=data.get("visit_id", ""),
        patient_id=data.get("patient_id", ""),
        patient_uuid=data.get("patient_uuid", ""),
        patient_name=data.get("patient_name", ""),
        service_code=data.get("service_code", ""),
        token_number=data.get("token_number", 1),
        department=data.get("department", "Cardiology"),
        room=data.get("room", ""),
        status=status,
        priority=data.get("priority", 0),
        display_order=data.get("display_order", 0),
        created_by=data.get("created_by", ""),
        updated_by=data.get("updated_by", ""),
        pending_alert=bool(data.get("pending_alert", False)),
        alert_message=data.get("alert_message"),
        notes=data.get("notes", ""),
        called_at=_deserialize_datetime(data.get("called_at")),
        started_at=_deserialize_datetime(data.get("started_at")),
        completed_at=_deserialize_datetime(data.get("completed_at")),
        report_ready_at=_deserialize_datetime(data.get("report_ready_at")),
        delivered_at=_deserialize_datetime(data.get("delivered_at")),
        version=data.get("version", 1),
        created_at=_deserialize_datetime(data.get("created_at"))
        or datetime.now(timezone.utc),
        updated_at=_deserialize_datetime(data.get("updated_at"))
        or datetime.now(timezone.utc),
    )
    return entry


# =========================================================================
# Internal helpers
# =========================================================================


def _list_date_folders() -> list[str]:
    """List all date-stamped data folders (newest first, excluding today).

    Returns:
        Sorted list of date folder names (newest first, today excluded).
    """
    import os

    data_dir = os.getenv("GHOS_JSON_DATA_DIR", "cardioqueue_data")
    today_str = date.today().isoformat()
    if not os.path.exists(data_dir):
        return []
    folders = [
        d for d in os.listdir(data_dir)
        if os.path.isdir(os.path.join(data_dir, d))
        and d.replace("-", "").isdigit()
        and d != today_str
    ]
    return sorted(folders, reverse=True)


def load_patients(date_str: str | None = None) -> list[dict]:
    """Load patients for a specific date (re-export for convenience).

    Args:
        date_str: Date string. Defaults to today.

    Returns:
        List of patient dicts.
    """
    from src.infrastructure.persistence.shared.local_json_db import (
        load_patients as _load,
    )
    return _load(date_str)


def load_queue_entries(date_str: str | None = None) -> list[dict]:
    """Load queue entries for a specific date (re-export).

    Args:
        date_str: Date string. Defaults to today.

    Returns:
        List of queue entry dicts.
    """
    from src.infrastructure.persistence.shared.local_json_db import (
        load_queue_entries as _load,
    )
    return _load(date_str)


def load_audit_log(date_str: str | None = None) -> list[dict]:
    """Load audit log for a specific date (re-export).

    Args:
        date_str: Date string. Defaults to today.

    Returns:
        List of audit log dicts.
    """
    from src.infrastructure.persistence.shared.local_json_db import (
        load_audit_log as _load,
    )
    return _load(date_str)
