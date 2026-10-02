"""Patient Domain Service.

Encapsulates business logic that spans multiple Patient operations.
Pure domain logic — no I/O, no infrastructure dependencies.
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.domain.patient.entities.patient import Patient, INACTIVITY_DAYS


class PatientDomainService:
    """Domain service for cross-cutting patient business rules."""

    @staticmethod
    def should_mark_inactive(patient: Patient) -> bool:
        """Check if a patient should be marked as inactive.

        A patient is inactive if they haven't visited in INACTIVITY_DAYS days
        and they currently have an 'active' status.

        Args:
            patient: The patient to evaluate.

        Returns:
            True if the patient should be moved to inactive status.
        """
        if not patient.status.is_active:
            return False
        if not patient.last_visit_at:
            return False
        delta = datetime.now(timezone.utc) - patient.last_visit_at
        return delta.days >= INACTIVITY_DAYS

    @staticmethod
    def can_merge_patients(source: Patient, target: Patient) -> tuple[bool, str | None]:
        """Check if two patient records can be merged.

        Rules:
        - Source must not already be merged.
        - Target must not be blocked.
        - Both must have the same phone hash (same person).

        Args:
            source: The patient record being merged (will become inactive).
            target: The surviving patient record.

        Returns:
            Tuple of (can_merge, reason). If can_merge is False, reason explains why.
        """
        if source.merged_into_patient_id:
            return False, "Source patient is already merged"
        if not target.can_register_visit:
            return False, "Target patient cannot accept visits (blocked or merged)"
        if source.contact.phone_hash != target.contact.phone_hash:
            return False, "Patients do not share the same phone number"
        return True, None

    @staticmethod
    def generate_search_tokens(name: str) -> list[str]:
        """Generate search tokens from a patient name for fuzzy matching.

        Args:
            name: Full patient name.

        Returns:
            List of search tokens (lowercased, parts of the name).
        """
        parts = name.lower().split()
        tokens = []
        for part in parts:
            tokens.append(part)
            # Add prefix tokens for partial matching
            for i in range(3, len(part)):
                tokens.append(part[:i])
        return list(set(tokens))
