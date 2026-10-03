"""SQLAlchemy model for verified clinic reviews (Part F · F-07).

Each row is one review of one clinic, tied to a visit that actually completed.
The ``queue_entry_id`` / ``visit_id`` pair is what makes it verifiable: the
review cannot exist without a real token behind it, which is what stops the
rating from being a marketing number.

Uniqueness is one review per visit — enforced in the route (and by the
``visit_id`` index) rather than by a DB constraint, because SQLite and
PostgreSQL handle partial/conditional unique indexes differently and the app
must run on both.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.infrastructure.database import Base


class ClinicReviewModel(Base):
    """One verified review of one clinic."""

    __tablename__ = "clinic_reviews"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ── Tenancy + who ──────────────────────────────────────────────────────
    clinic_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doctor_id: Mapped[str] = mapped_column(
        String(100), nullable=False, default="chief", server_default="chief"
    )
    patient_id: Mapped[str] = mapped_column(String(30), nullable=False, index=True)

    # ── The proof of visit ─────────────────────────────────────────────────
    #: The queue entry this review is about. One review per visit.
    queue_entry_id: Mapped[str] = mapped_column(
        String(36), nullable=False, default="", server_default=""
    )
    visit_id: Mapped[str] = mapped_column(
        String(100), nullable=False, default="", server_default="", index=True
    )
    service_code: Mapped[str] = mapped_column(
        String(20), nullable=False, default="OPD", server_default="OPD"
    )
    #: Status the visit held when the review was accepted (COMPLETED etc.).
    visit_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="", server_default=""
    )

    # ── The review ─────────────────────────────────────────────────────────
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # ── Moderation ─────────────────────────────────────────────────────────
    #: False = hidden by staff. Hidden reviews never count toward the score.
    is_visible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    hidden_reason: Mapped[str] = mapped_column(
        String(200), nullable=False, default="", server_default=""
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<ClinicReview clinic={self.clinic_id} "
            f"visit={self.visit_id} rating={self.rating}>"
        )
