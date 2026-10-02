"""Outbox pattern event publisher — re-exported from shared persistence layer.

Writes domain events to the outbox table in the same transaction as the
domain operation. A background relay reads PENDING events and publishes
them to Redis pub/sub channels.

This re-export exists so that identity engine consumers can import
from infrastructure.identity.events rather than coupling to the
internal persistence package structure.

Usage:
    from src.infrastructure.identity.events.outbox_publisher import OutboxEventPublisher

    publisher = OutboxEventPublisher(session)
    publisher.publish("IDENTITY.USER.LOGIN", {"user_id": "..."})
"""

from src.infrastructure.persistence.shared.events.outbox_publisher import (
    OutboxEventPublisher,
)

__all__ = [
    "OutboxEventPublisher",
]
