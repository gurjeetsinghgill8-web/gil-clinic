"""SQLAlchemy model for clinic leads (BLOCK 4 · GRW-02).

Why this exists
---------------
The marketplace already showed a "📢 Invite to GHOS Live Queue" button on every
non-partner clinic — and it did nothing but show a toast. So the single most
valuable sales signal the product produces (a real patient asking for a clinic
that is not on the network yet) was thrown away at the exact moment it was
created.

A lead here is that signal, captured: which clinic, where, how many times people
asked, and where it stands in the outreach pipeline. It is deliberately per
clinic rather than per patient — nobody's identity is recorded, only demand.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.infrastructure.database import Base

# ── Pipeline stages, in order ───────────────────────────────────────────────

STATUS_NEW = "NEW"
STATUS_CONTACTED = "CONTACTED"
STATUS_INTERESTED = "INTERESTED"
STATUS_ONBOARDED = "ONBOARDED"
STATUS_DECLINED = "DECLINED"

PIPELINE_ORDER: tuple[str, ...] = (
    STATUS_NEW,
    STATUS_CONTACTED,
    STATUS_INTERESTED,
    STATUS_ONBOARDED,
    STATUS_DECLINED,
)

STATUS_LABEL: dict[str, str] = {
    STATUS_NEW: "🆕 Naya",
    STATUS_CONTACTED: "📞 Baat hui",
    STATUS_INTERESTED: "🌟 Interested",
    STATUS_ONBOARDED: "✅ Onboarded",
    STATUS_DECLINED: "❌ Nahi chahiye",
}

#: How the lead arrived.
SOURCE_PATIENT_INVITE = "patient_invite"
SOURCE_MARKETPLACE_VIEW = "marketplace_view"
SOURCE_ADMIN = "admin"
SOURCE_CRAWL = "crawl"


class ClinicLeadModel(Base):
    """One clinic that patients asked for (or that admin is chasing)."""

    __tablename__ = "clinic_leads"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ── Which clinic ───────────────────────────────────────────────────────
    #: Nullable: a lead can come from a patient naming a clinic we do not have.
    clinic_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    clinic_name: Mapped[str] = mapped_column(
        String(200), nullable=False, default="", server_default=""
    )
    city: Mapped[str] = mapped_column(
        String(100), nullable=False, default="", server_default=""
    )
    state: Mapped[str] = mapped_column(
        String(100), nullable=False, default="", server_default=""
    )
    specialty: Mapped[str] = mapped_column(
        String(100), nullable=False, default="", server_default=""
    )
    phone: Mapped[str] = mapped_column(
        String(20), nullable=False, default="", server_default=""
    )

    # ── Demand signal ──────────────────────────────────────────────────────
    #: How many times patients asked for this clinic. The strongest argument
    #: in the sales conversation, and it is free to collect.
    request_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    #: Plain-language reasons patients gave ("seene me dard", "ECG chahiye").
    #: Repeated as a short list so the pitch quotes real demand, not a guess.
    demand_notes: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=""
    )
    source: Mapped[str] = mapped_column(
        String(30), nullable=False, default=SOURCE_PATIENT_INVITE,
        server_default="patient_invite",
    )

    # ── Pipeline ───────────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=STATUS_NEW, server_default="NEW"
    )
    note: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    last_contacted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    onboarded_clinic_id: Mapped[str] = mapped_column(
        String(36), nullable=False, default="", server_default=""
    )
    updated_by: Mapped[str] = mapped_column(
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

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<ClinicLead {self.clinic_name or self.clinic_id} "
            f"status={self.status} asks={self.request_count}>"
        )
