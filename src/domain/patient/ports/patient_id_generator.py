"""Patient ID Generator port.

Generates human-readable patient IDs in the format: CQ-YYYYMMDD-NNN.
"""

from __future__ import annotations

from typing import Protocol


class PatientIdGenerator(Protocol):
    """Interface for generating human-readable patient IDs."""

    async def generate_patient_id(self) -> str:
        """Generate a new patient ID.

        Format: CQ-YYYYMMDD-NNN (e.g., 'CQ-20260714-001').

        Returns:
            A unique patient ID string.
        """
        ...

    async def get_today_count(self) -> int:
        """Get the number of patients registered today.

        Returns:
            Count of registrations today.
        """
        ...
