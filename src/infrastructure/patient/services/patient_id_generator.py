"""PatientIdGenerator implementation.

Generates human-readable patient IDs in the format: CQ-YYYYMMDD-NNN.
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.domain.patient.ports.patient_id_generator import (
    PatientIdGenerator as PatientIdGeneratorPort,
)


class PatientIdGeneratorService:
    """Generates sequential patient IDs.

    Format: CQ-YYYYMMDD-NNN (e.g., 'CQ-20260714-001').
    Uses the patient repository to determine daily sequence numbers.
    """

    def __init__(self, patient_repo) -> None:
        self._patient_repo = patient_repo

    async def generate_patient_id(self) -> str:
        """Generate a new patient ID.

        Returns:
            A unique patient ID string like 'CQ-20260714-001'.
        """
        today = datetime.now(timezone.utc)
        date_prefix = today.strftime("CQ-%Y%m%d")
        seq = await self._patient_repo.get_next_sequence_number(
            date_prefix.ljust(20, "0")[:20]
        )
        # Actually use today's formatted date
        date_str = today.strftime("%Y%m%d")
        patient_id_prefix = f"CQ-{date_str}"
        seq = await self._patient_repo.get_next_sequence_number(patient_id_prefix)
        return f"{patient_id_prefix}-{seq:03d}"

    async def get_today_count(self) -> int:
        """Get the number of patients registered today."""
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        prefix = f"CQ-{today}"
        return await self._patient_repo.get_next_sequence_number(prefix) - 1
