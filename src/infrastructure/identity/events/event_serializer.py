"""Domain event serializer for the Identity Engine.

Serializes IdentityEvent objects to JSON-compatible dicts (CloudEvents 1.0 format).
Handles UUID and datetime serialization.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any


class IdentityEventSerializer:
    """Serializes and deserializes identity domain events.

    Converts IdentityEvent objects to CloudEvents 1.0-compatible JSON
    for storage in the outbox table and transport via Redis pub/sub.

    Thread-safe and stateless.
    """

    def serialize(self, event: Any) -> str:
        """Serialize an identity event to JSON string.

        Args:
            event: IdentityEvent instance with to_dict() method.

        Returns:
            JSON string representation of the event.
        """
        if hasattr(event, "to_dict"):
            data = event.to_dict()
        else:
            data = {
                "event_name": getattr(event, "event_name", "unknown"),
                "aggregate_id": str(getattr(event, "aggregate_id", "")),
                "timestamp": (
                    getattr(event, "timestamp", datetime.utcnow()).isoformat()
                ),
                "payload": getattr(event, "payload", {}),
            }
        return json.dumps(data, default=str, ensure_ascii=False)

    def deserialize(self, data: dict[str, Any]) -> dict[str, Any]:
        """Deserialize a dict back to an event dict.

        Args:
            data: Dictionary representing an identity event.

        Returns:
            The same dict with type-corrected timestamps.
        """
        # Ensure timestamps are ISO strings
        if "timestamp" in data and not isinstance(data["timestamp"], str):
            data["timestamp"] = data["timestamp"].isoformat()
        if "time" in data and not isinstance(data["time"], str):
            data["time"] = data["time"].isoformat()
        return data

    def to_cloudevent(self, event: Any) -> dict[str, Any]:
        """Convert an identity event to a CloudEvents 1.0 dict.

        Args:
            event: IdentityEvent instance.

        Returns:
            CloudEvents-compatible dictionary.
        """
        if hasattr(event, "to_dict"):
            return event.to_dict()

        return {
            "specversion": "1.0",
            "type": getattr(event, "event_name", "IDENTITY.EVENT"),
            "source": "/ghos/identity",
            "subject": str(getattr(event, "aggregate_id", "")),
            "time": getattr(event, "timestamp", datetime.utcnow()).isoformat() + "Z",
            "datacontenttype": "application/json",
            "data": getattr(event, "payload", {}),
        }


serializer = IdentityEventSerializer()
