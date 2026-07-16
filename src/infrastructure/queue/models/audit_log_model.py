"""SQLAlchemy model for queue.audit_log table.

Immutable append-only log recording every queue action.
Each entry captures who did what, to which resource, and what changed.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.domain.base_entity import uuid7
from src.shared.infrastructure.database import Base


class AuditLogModel(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("idx_audit_resource", "resource_type", "resource_id"),
        Index("idx_audit_actor", "actor"),
        Index("idx_audit_created", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    actor: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    resource_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="queue_entry"
    )
    resource_id: Mapped[str] = mapped_column(
        String(36), nullable=False
    )
    old_status: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )
    new_status: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )
    details: Mapped[dict | None] = mapped_column(
        JSON(), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
