"""Event infrastructure: OutboxPublisher, EventSerializer."""

from src.infrastructure.identity.events.event_serializer import (
    IdentityEventSerializer,
    serializer,
)
from src.infrastructure.identity.events.outbox_publisher import (
    OutboxEventPublisher,
)

__all__ = [
    "IdentityEventSerializer",
    "OutboxEventPublisher",
    "serializer",
]
