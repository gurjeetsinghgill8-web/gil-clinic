"""Patient repository interface (port).

Defines the contract for persisting and retrieving Patient aggregates.
Implemented by SqlAlchemyPatientRepository in the infrastructure layer.
"""

from __future__ import annotations

from typing import Protocol

from src.domain.patient.entities.patient import Patient


class PatientRepository(Protocol):
    """Interface for Patient aggregate persistence.

    Domain layer defines this protocol. Infrastructure provides the implementation.
    """

    async def save(self, patient: Patient) -> None:
        """Persist a new or updated patient.

        Args:
            patient: Patient aggregate to save.
        """
        ...

    async def get_by_id(self, patient_uuid: str) -> Patient | None:
        """Get a patient by their internal UUID.

        Args:
            patient_uuid: UUID string.

        Returns:
            Patient if found, None otherwise.
        """
        ...

    async def get_by_patient_id(self, patient_id: str) -> Patient | None:
        """Get a patient by their human-readable ID (e.g., 'CQ-20260714-001').

        Args:
            patient_id: Human-readable patient ID.

        Returns:
            Patient if found, None otherwise.
        """
        ...

    async def get_by_phone_hash(self, phone_hash: str) -> Patient | None:
        """Get a patient by phone hash (for lookup on encrypted phone).

        Args:
            phone_hash: SHA-256 hash of phone number.

        Returns:
            Patient if found, None otherwise.
        """
        ...

    async def get_by_qr_hash(self, qr_hash: str) -> Patient | None:
        """Get a patient by their QR identity hash.

        Args:
            qr_hash: SHA-256 hash of QR payload.

        Returns:
            Patient if found, None otherwise.
        """
        ...

    async def exists_by_phone_hash(self, phone_hash: str) -> bool:
        """Check if a phone number is already registered.

        Args:
            phone_hash: SHA-256 hash of phone number.

        Returns:
            True if phone exists.
        """
        ...

    async def list_active(
        self,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Patient]:
        """List active patients with pagination.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to return.

        Returns:
            List of Patient aggregates.
        """
        ...

    async def list_by_status(
        self,
        status: str,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Patient]:
        """List patients by lifecycle status.

        Args:
            status: Status filter ('active', 'inactive', 'blocked', 'merged').
            offset: Number of records to skip.
            limit: Maximum records to return.

        Returns:
            List of matching Patient aggregates.
        """
        ...

    async def search_by_name(
        self,
        query: str,
        offset: int = 0,
        limit: int = 20,
    ) -> list[Patient]:
        """Search patients by name (fuzzy / LIKE search).

        Args:
            query: Name search string.
            offset: Number of records to skip.
            limit: Maximum records to return.

        Returns:
            List of matching Patient aggregates.
        """
        ...

    async def count(self, status: str | None = None) -> int:
        """Count patients, optionally filtered by status.

        Args:
            status: Optional status filter.

        Returns:
            Total count of matching patients.
        """
        ...

    async def delete(self, patient_uuid: str) -> bool:
        """Hard-delete a patient record (admin only).

        Args:
            patient_uuid: UUID of the patient to delete.

        Returns:
            True if deleted, False if not found.
        """
        ...

    async def get_next_sequence_number(self, date_prefix: str) -> int:
        """Get the next daily sequence number for patient ID generation.

        Args:
            date_prefix: Date prefix like '20260714'.

        Returns:
            Next sequence number (1-based).
        """
        ...
