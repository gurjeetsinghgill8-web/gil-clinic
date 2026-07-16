"""SQLAlchemy model for queue.queue_entries table."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.domain.base_entity import uuid7
from src.shared.infrastructure.database import Base


class QueueEntryModel(Base):
    __tablename__ = "queue_entries"
    __table_args__ = (
        Index("idx_queue_visit", "visit_id"),
        Index("idx_queue_patient", "patient_uuid"),
        Index("idx_queue_department_status", "department", "status"),
        Index("idx_queue_service_token", "service_code", "token_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    visit_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    patient_id: Mapped[str] = mapped_column(String(30), nullable=False)
    patient_uuid: Mapped[str] = mapped_column(String(36), nullable=False)
    patient_name: Mapped[str] = mapped_column(String(200), nullable=False)

    service_code: Mapped[str] = mapped_column(String(30), nullable=False)
    token_number: Mapped[int] = mapped_column(Integer, nullable=False)
    department: Mapped[str] = mapped_column(String(100), nullable=False, default="Cardiology")
    room: Mapped[str] = mapped_column(String(100), nullable=False, default="")

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="WAITING"
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_by: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    updated_by: Mapped[str] = mapped_column(String(100), nullable=False, default="")

    # Alert system
    pending_alert: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    alert_message: Mapped[str | None] = mapped_column(
        String(500), nullable=True, default=None
    )

    # Doctor's clinical / consultation notes
    notes: Mapped[str] = mapped_column(
        String(2000), nullable=False, default=""
    )

    called_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    report_ready_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )
