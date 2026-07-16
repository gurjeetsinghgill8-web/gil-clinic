"""Persistence base classes: audit mixin, soft-delete, versioned model.

Provides reusable SQLAlchemy mixins for all engine models:
- TimestampMixin: created_at, updated_at
- AuditMixin: created_by, updated_by
- SoftDeleteMixin: deleted_at, is_deleted
- VersionedMixin: version for OCC
- PersistenceBase: Combines all mixins with UUIDv7 PK
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from src.shared.domain.base_entity import uuid7


class TimestampMixin:
    """Created/updated timestamp tracking for all models."""

    @declared_attr
    def created_at(cls) -> Mapped[datetime]:
        return mapped_column(
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False,
        )

    @declared_attr
    def updated_at(cls) -> Mapped[datetime]:
        return mapped_column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        )


class AuditMixin:
    """Audit trail fields — who created/updated each record.

    Requires the application to set created_by / updated_by
    from the authenticated user context.
    """

    @declared_attr
    def created_by(cls) -> Mapped[str | None]:
        return mapped_column(String(100), nullable=True)

    @declared_attr
    def updated_by(cls) -> Mapped[str | None]:
        return mapped_column(String(100), nullable=True)


class SoftDeleteMixin:
    """Soft delete support — records are marked, not physically deleted.

    All queries should include is_deleted = False by default.
    Hard delete is only for cleanup jobs (GDPR, data purging).
    """

    @declared_attr
    def is_deleted(cls) -> Mapped[bool]:
        return mapped_column(
            Boolean,
            default=False,
            nullable=False,
            index=True,
        )

    @declared_attr
    def deleted_at(cls) -> Mapped[datetime | None]:
        return mapped_column(DateTime(timezone=True), nullable=True)

    def soft_delete(self) -> None:
        """Mark the record as deleted."""
        self.is_deleted = True
        self.deleted_at = datetime.now(timezone.utc)

    def restore(self) -> None:
        """Restore a soft-deleted record."""
        self.is_deleted = False
        self.deleted_at = None


class VersionedMixin:
    """Optimistic Concurrency Control via version counter.

    On every UPDATE, the version is incremented.
    The WHERE clause includes the old version.
    If 0 rows match, a concurrent modification is detected.
    """

    @declared_attr
    def version(cls) -> Mapped[int]:
        return mapped_column(
            Integer,
            default=1,
            nullable=False,
        )


class PersistenceBase:
    """Combined base for all identity persistence models.

    Provides:
    - UUIDv7 primary key (id)
    - Created/updated timestamps
    - Created_by/updated_by audit fields
    - Soft delete support
    - OCC version counter
    """

    @declared_attr
    def id(cls):
        return mapped_column(
            UUID(as_uuid=True),
            primary_key=True,
            default=uuid7,
        )
