"""Event serializer for the Patient Engine.

Converts PatientEvents to CloudEvents 1.0 JSON for outbox persistence.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.domain.patient.events.patient_events import PatientEvent


class PatientEventSerializer:
    """Serializes PatientEvents to/from CloudEvents 1.0 format."""

    @staticmethod
    def serialize(event: PatientEvent) -> dict[str, Any]:
        """Serialize a PatientEvent to a CloudEvents-compatible dict.

        Args:
            event: The domain event to serialize.

        Returns:
            CloudEvents 1.0 format dict.
        """
        return event.to_dict()

    @staticmethod
    def deserialize(data: dict[str, Any]) -> PatientEvent:
        """Deserialize a CloudEvents dict back to a PatientEvent.

        Args:
            data: CloudEvents 1.0 format dict.

        Returns:
            Reconstructed PatientEvent.
        """
        event_data = data.get("data", {})
        return PatientEvent(
            event_name=data.get("type", "UNKNOWN"),
            aggregate_id=data.get("subject", ""),
            timestamp=datetime.fromisoformat(data.get("time", datetime.now(timezone.utc).isoformat())),
            payload={
                k: v for k, v in event_data.items()
                if k != "aggregateId"
            },
        )

    @staticmethod
    def to_cloudevent(event: PatientEvent) -> dict[str, Any]:
        """Same as serialize, alias for clarity."""
        return event.to_dict()
