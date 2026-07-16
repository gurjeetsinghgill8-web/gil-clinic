"""Typed persistence exceptions for database operations.

These exceptions are NEVER raised to the domain or application layer.
They are caught by the UnitOfWork and mapped to ApplicationException
with appropriate error codes.
"""

from __future__ import annotations


class PersistenceError(Exception):
    """Base exception for all persistence errors."""

    def __init__(
        self,
        message: str = "Database operation failed",
        details: dict | None = None,
    ) -> None:
        self.details = details or {}
        super().__init__(message)


class ConcurrentModificationError(PersistenceError):
    """Optimistic locking failure.

    Raised when an update affects 0 rows because the version
    field doesn't match. Another transaction modified the record
    between read and write.
    """

    def __init__(
        self,
        entity_type: str,
        entity_id: str,
        expected_version: int,
    ) -> None:
        super().__init__(
            message=(
                f"{entity_type} {entity_id} was modified by another transaction. "
                f"Expected version {expected_version}. "
                "Please retry the operation."
            ),
            details={
                "entity_type": entity_type,
                "entity_id": entity_id,
                "expected_version": expected_version,
            },
        )


class EntityNotFoundError(PersistenceError):
    """Entity not found in database."""

    def __init__(
        self,
        entity_type: str,
        entity_id: str,
    ) -> None:
        super().__init__(
            message=f"{entity_type} not found: {entity_id}",
            details={
                "entity_type": entity_type,
                "entity_id": entity_id,
            },
        )


class DuplicateEntityError(PersistenceError):
    """Unique constraint violation."""

    def __init__(
        self,
        entity_type: str,
        field: str,
        value: str,
    ) -> None:
        super().__init__(
            message=f"{entity_type} with {field}={value} already exists",
            details={
                "entity_type": entity_type,
                "field": field,
                "value": value,
            },
        )


class BatchOperationError(PersistenceError):
    """Error during batch operation. Partial success possible."""

    def __init__(
        self,
        operation: str,
        succeeded: int,
        failed: int,
        errors: list[str] | None = None,
    ) -> None:
        self.succeeded = succeeded
        self.failed = failed
        super().__init__(
            message=(
                f"Batch {operation}: {succeeded} succeeded, "
                f"{failed} failed"
            ),
            details={
                "operation": operation,
                "succeeded": succeeded,
                "failed": failed,
                "errors": errors or [],
            },
        )
