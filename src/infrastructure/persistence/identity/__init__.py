"""Identity Engine — Persistence Layer.

Contains:
- database/: SQLAlchemy engine and session configuration
- models/: ORM models for all 7 identity tables
- repositories/: Repository implementations for all 5 aggregate types
- mappers/: Domain-to-model conversion for each entity
- specifications/: Reusable query filters
- queries/: Read-optimized query objects with pagination
- unit_of_work/: Transaction management
- pagination/: Offset and cursor pagination
- exceptions/: Typed persistence errors
"""
