"""SQLAlchemy model for cross-clinic referral slips (Part F · F-06).

The gap this fills
------------------
The network already had "📢 invite this doctor" (``clinic_leads``), which asks a
clinic to *join*. It had no way to actually send a patient from clinic A to
clinic B — the most common real clinical hand-off there is (a cardiology case
seen by a general physician, a scan that needs a bigger centre).

A referral here is a **signed slip**, not an email: clinic A creates it, the
slip carries a signed token that proves which clinic sent it and for whom, and
clinic B accepts it to materialise a real token in its own queue. Until it is
accepted, nothing exists in the receiver's queue — so a clinic cannot have
patients pushed into its queue by anyone who guesses a URL.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.infrastructure.database import Base

# ── Status vocabulary (plain strings so DB, JSON and templates agree) ───────

STATUS_PENDING = "PENDING"
STATUS_ACCEPTED = "ACCEPTED"
STATUS_DECLINED = "DECLINED"
STATUS_CANCELLED = "CANCELLED"

#: Urgency levels, in the order a clinic should triage them.
URGENCY_ROUTINE = "ROUTINE"
URGENCY_SOON = "SOON"
URGENCY_URGENT = "URGENT"

URGENCY_ORDER: dict[str, int] = {
    URGENCY_URGENT: 0,
    URGENCY_SOON: 1,
    URGENCY_ROUTINE: 2,
}

URGENCY_LABEL: dict[str, str] = {
    URGENCY_URGENT: "🔴 Turant",
    URGENCY_SOON: "🟡 Jaldi",
    URGENCY_ROUTINE: "🟢 Normal",
}


class ReferralModel(Base):
    """One patient hand-off from one clinic to another."""

    __tablename__ = "referrals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ── Who → whom ─────────────────────────────────────────────────────────
    from_clinic_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    from_doctor_id: Mapped[str] = mapped_column(
        String(100), nullable=False, default="chief", server_default="chief"
    )
    to_clinic_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    #: Nullable: a referral can be addressed to a clinic rather than a person.
    to_doctor_id: Mapped[str] = mapped_column(
        String(100), nullable=False, default="chief", server_default="chief"
    )

    # ── Patient (minimum needed to see them at the other end) ──────────────
    patient_id: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    patient_name: Mapped[str] = mapped_column(
        String(200), nullable=False, default="", server_default=""
    )
    patient_age: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    patient_phone: Mapped[str] = mapped_column(
        String(20), nullable=False, default="", server_default=""
    )

    # ── Clinical payload ───────────────────────────────────────────────────
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    #: Free-text note the sending doctor wants the receiver to read first.
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    urgency: Mapped[str] = mapped_column(
        String(20), nullable=False, default=URGENCY_ROUTINE, server_default="ROUTINE"
    )
    #: The sending clinic's own token, so the receiver can quote it back.
    source_token_label: Mapped[str] = mapped_column(
        String(20), nullable=False, default="", server_default=""
    )

    # ── Lifecycle ──────────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=STATUS_PENDING, server_default="PENDING"
    )
    #: Signed slip id (itsdangerous) — what the receiver's link carries.
    slip_token: Mapped[str] = mapped_column(
        String(255), nullable=False, default="", server_default=""
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    viewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    viewed_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    #: The queue entry created in the RECEIVING clinic on acceptance.
    accepted_entry_id: Mapped[str] = mapped_column(
        String(36), nullable=False, default="", server_default=""
    )
    accepted_token_label: Mapped[str] = mapped_column(
        String(20), nullable=False, default="", server_default=""
    )
    declined_reason: Mapped[str] = mapped_column(
        String(200), nullable=False, default="", server_default=""
    )
    #: Set when the slip has been consumed by a successful acceptance.
    is_open: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )

    created_by: Mapped[str] = mapped_column(
        String(100), nullable=False, default="", server_default=""
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
            f"<Referral {self.from_clinic_id}->{self.to_clinic_id} "
            f"patient={self.patient_id} status={self.status}>"
        )
