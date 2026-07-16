"""Shared event infrastructure for the persistence layer.

Provides:
- OutboxEventPublisher: writes domain events to the outbox table
- Event serializer: domain event ←→ JSON conversion
"""
