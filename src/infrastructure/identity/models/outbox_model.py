"""SQLAlchemy model for identity.outbox table.

Outbox pattern: events are written to DB in same transaction as domain operation,
then relayed to Redis by a background worker.
"""

from __future__ import annotations

import uuid

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.domain.base_entity import uuid7
from src.shared.infrastructure.database import Base


class OutboxModel(Base):
    """SQLAlchemy model for identity.outbox table.

    Stores pending domain events before they are published to Redis.
    The outbox relay reads PENDING events, publishes them, and marks as PUBLISHED.
    """

    __tablename__ = "outbox"
    __table_args__ = (
        Index("idx_outbox_status_created", "status", "created_at"),
        Index("idx_outbox_pending", "created_at", postgresql_where=text("status = 'PENDING'")),
        {"schema": "identity"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    event_type: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )
    payload: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), default="PENDING", nullable=False
    )
    retry_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    last_error: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # --- OCC, audit, soft-delete ---
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<OutboxModel id={self.id} "
            f"type={self.event_type} "
            f"status={self.status}>"
        )
