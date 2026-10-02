"""Outbox pattern event publisher.

Writes domain events to the outbox table in the same transaction as the
domain operation. A background relay reads PENDING events and publishes
them to Redis pub/sub channels.

This ensures:
1. Atomicity — events are persisted atomically with aggregates
2. Reliability — events survive crashes (can be replayed)
3. Ordering — events are published in the order they were created
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.identity.models.outbox_model import OutboxModel


class OutboxEventPublisher:
    """Event publisher that writes to the outbox table.

    Events are flushed to the DB but not committed until the
    UnitOfWork commits. This ensures atomicity of aggregate + events.

    Usage:
        publisher = OutboxEventPublisher(session)
        publisher.publish("IDENTITY.USER.LOGIN", {"user_id": "..."})
        await session.commit()  # Events committed atomically
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._events: list[OutboxModel] = []

    def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        """Queue a domain event to be written to the outbox.

        Args:
            event_type: Event name (e.g., "IDENTITY.USER.LOGIN").
            payload: Event payload dict with relevant data.
        """
        outbox_entry = OutboxModel(
            event_type=event_type,
            payload=json.dumps(payload, default=str),
            status="PENDING",
            retry_count=0,
        )
        self._session.add(outbox_entry)
        self._events.append(outbox_entry)

    @property
    def pending_events(self) -> list[OutboxModel]:
        """Get the list of events queued in this transaction."""
        return list(self._events)

    def clear(self) -> None:
        """Clear the event queue without publishing."""
        self._events.clear()
