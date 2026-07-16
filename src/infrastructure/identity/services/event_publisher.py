"""In-memory event publisher stub for development.

This is a lightweight implementation that publishes events to an in-memory
subscriber list. In production, this would be replaced with a Redis/AMPQ publisher.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Event:
    """Domain event container."""
    event_type: str
    payload: dict[str, Any]
    aggregate_id: str | None = None


class InMemoryEventPublisher:
    """Simple in-memory event publisher for development.

    Collects events in-memory and notifies registered subscribers synchronously.
    Accepts either an event object (with .event_name, .payload, .aggregate_id)
    or the legacy (event_type, payload, aggregate_id) positional format.
    """

    def __init__(self) -> None:
        self._events: list[Event] = []
        self._subscribers: dict[str, list[callable]] = {}

    def subscribe(self, event_type: str, handler: callable) -> None:
        """Register a handler for a given event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    def publish(self, event_or_type: Any, payload: dict[str, Any] | None = None, aggregate_id: str | None = None) -> None:
        """Publish an event to all registered subscribers.

        Accepts either:
        - An event object with .event_name, .payload, .aggregate_id attributes (e.g., PatientEvent)
        - Legacy (event_type: str, payload: dict, aggregate_id: str) positional args
        """
        # Check if first arg is an event object (has .event_name)
        if hasattr(event_or_type, 'event_name'):
            event_type = event_or_type.event_name
            payload = event_or_type.payload or {}
            agg_id = event_or_type.aggregate_id
        elif hasattr(event_or_type, 'to_dict'):
            # CloudEvents format
            d = event_or_type.to_dict()
            event_type = d.get("type", "UNKNOWN")
            payload = d.get("data", {})
            agg_id = event_or_type.aggregate_id
        else:
            # Legacy: first arg is event_type string
            event_type = event_or_type
            payload = payload or {}
            agg_id = aggregate_id

        event = Event(event_type=event_type, payload=payload, aggregate_id=agg_id)
        self._events.append(event)
        # Notify subscribers
        for handler in self._subscribers.get(event_type, []):
            handler(event)

    async def publish_async(self, event_or_type: Any, payload: dict[str, Any] | None = None, aggregate_id: str | None = None) -> None:
        """Async version of publish."""
        self.publish(event_or_type, payload, aggregate_id)

    @property
    def events(self) -> list[Event]:
        """Get all published events."""
        return list(self._events)

    def clear(self) -> None:
        """Clear all events and subscribers."""
        self._events.clear()
        self._subscribers.clear()
