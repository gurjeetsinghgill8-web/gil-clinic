"""Persistence layer for all engines.

Contains the complete persistence infrastructure:
- Database: Engine, session factory, connection management
- Models: SQLAlchemy ORM models with audit, soft-delete, OCC
- Repositories: Generic + engine-specific repository implementations
- Mappers: Domain entity ↔ SQLAlchemy model conversion
- Specifications: Reusable query filters
- Queries: Read-optimized query objects
- Pagination: Offset and cursor-based pagination
- Unit of Work: Atomic transaction management
- Exceptions: Typed persistence errors
"""
