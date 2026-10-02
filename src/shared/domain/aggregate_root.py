"""Base aggregate root with domain event collection.

All aggregate roots across all engines inherit from this.
Provides event collection and clearing for the outbox pattern.
"""

from __future__ import annotations

from dataclasses import field
from typing import TYPE_CHECKING, Generic, TypeVar

from src.shared.domain.base_entity import BaseEntity

if TYPE_CHECKING:
    from collections.abc import Sequence

TEvent = TypeVar("TEvent")


class AggregateRoot(BaseEntity, Generic[TEvent]):
    """Base class for all aggregate roots.

    Extends BaseEntity with:
    - Domain event collection (add/clear)
    - Events are published after the aggregate is saved
    """

    _events: list[TEvent] = field(default_factory=list, repr=False)

    def add_event(self, event: TEvent) -> None:
        """Register a domain event to be published later."""
        self._events.append(event)

    def clear_events(self) -> list[TEvent]:
        """Retrieve and clear all pending domain events."""
        events = list(self._events)
        self._events.clear()
        return events

    @property
    def has_pending_events(self) -> bool:
        """Check if there are un-published domain events."""
        return len(self._events) > 0
