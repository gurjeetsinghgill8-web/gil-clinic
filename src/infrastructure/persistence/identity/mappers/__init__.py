"""Mappers: domain entity ↔ SQLAlchemy model conversion.

Mappers are pure conversion functions — no side effects, no business logic.
They handle:
- Domain entity → SQLAlchemy model (for persistence)
- SQLAlchemy model → Domain entity (for application use)
"""
