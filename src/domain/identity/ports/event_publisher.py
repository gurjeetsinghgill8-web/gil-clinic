"""Port: Event publisher interface.

Domain layer defines this protocol. Infrastructure provides OutboxPublisher.
Identity ONLY publishes events — never makes direct calls to other engines.
"""

from __future__ import annotations

from typing import Any, Protocol


class EventPublisher(Protocol):
    """Interface for publishing domain events.

    Events are written to the outbox table in the same DB transaction as the
    domain operation. A background relay reads PENDING events and publishes
    them to Redis pub/sub channels.

    Identity publishes events only — it never calls other engines directly.
    """

    def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        """Publish a domain event.

        Args:
            event_type: Event name (e.g., "IDENTITY.USER.LOGIN").
            payload: Event payload dict with relevant data.
        """
        ...
