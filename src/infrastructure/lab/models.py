"""External lab network model — lab_orders table.

Doctor order karta hai → external lab process karta hai → result patient ke
phone par shareable link (/lab/<token>) se dikh jaata hai.

External lab ka real API partner ke saath aayega; abhi order lifecycle + result
+ patient delivery LOCAL me fully working hai (ABDM scaffold jaisa — external
call stubbed, crash nahi hota).
"""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.infrastructure.database import Base


class LabOrderModel(Base):
    """Ek lab order — doctor → external lab → result → patient."""

    __tablename__ = "lab_orders"
    __table_args__ = (
        Index("idx_lab_orders_patient", "patient_id", "created_at"),
        Index("idx_lab_orders_token", "report_token", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clinic_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    doctor_id: Mapped[str] = mapped_column(String(100), nullable=False, default="chief")

    patient_id: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    patient_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    phone: Mapped[str] = mapped_column(String(20), nullable=False, default="")

    # Order
    tests: Mapped[str] = mapped_column(Text, nullable=False, default="")  # newline-separated
    sample_type: Mapped[str] = mapped_column(String(20), nullable=False, default="blood")
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default="routine")
    external_lab: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    external_order_ref: Mapped[str] = mapped_column(String(100), nullable=False, default="")

    # Lifecycle: ordered → sent → sample_collected → in_progress → reported → delivered
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ordered")

    # Result (JSON array once reported)
    result_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    reported_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Patient-facing shareable token
    report_token: Mapped[str] = mapped_column(String(80), nullable=False, default="", unique=True)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<LabOrder {self.patient_id} {self.status}>"
