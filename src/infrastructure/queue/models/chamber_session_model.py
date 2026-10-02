"""Chamber sessions — the doctor's OPD "gate" (Part D · E-01).

The bug this fixes
------------------
A clinic's board says "9:00 AM", but the doctor reaches the chamber at 9:40.
Between 9:00 and 9:40 the patient app used to show "Wait: 15 mins" — a number
that was simply false, because nobody was inside the room.

Rule: the EWT countdown stays OFF until the doctor presses **START OPD**. Until
then every patient sees "Doctor arrival pending — aapka number safe hai", which
is honest and calm instead of a fake countdown.

Bonus the table gives us for free: ``opened_at − scheduled_time`` is the doctor's
real late-arrival history, which the owner can see on the analytics screen.

Table is created automatically by ``Base.metadata.create_all()`` on startup.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.infrastructure.database import Base


class ChamberSessionModel(Base):
    """One row per (clinic, doctor, day) — opened when OPD actually starts."""

    __tablename__ = "chamber_sessions"
    __table_args__ = (
        Index("idx_chamber_clinic_doctor_date", "clinic_id", "doctor_id", "session_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinic_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True)
    doctor_id: Mapped[str] = mapped_column(String(100), nullable=False, default="chief")

    session_date: Mapped[date] = mapped_column(Date, nullable=False)

    #: Advertised OPD time for this day (e.g. "09:00"), used to measure lateness.
    scheduled_time: Mapped[str] = mapped_column(String(5), nullable=False, default="")

    #: ▶ START OPD — the moment the countdown may begin.
    opened_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    #: ⏹ END OPD
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    opened_by: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    note: Mapped[str] = mapped_column(String(200), nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # ── Helpers (pure, so tests can use them without a DB) ──────────────────

    @property
    def is_open(self) -> bool:
        """Chamber counts as open only between START OPD and END OPD."""
        return self.opened_at is not None and self.closed_at is None

    @property
    def late_arrival_minutes(self) -> int:
        """How late the doctor opened the chamber vs the advertised time."""
        if self.opened_at is None or not self.scheduled_time:
            return 0
        try:
            hour, minute = (int(p) for p in self.scheduled_time.split(":")[:2])
        except (ValueError, AttributeError):
            return 0
        opened = self.opened_at
        if opened.tzinfo is None:
            opened = opened.replace(tzinfo=timezone.utc)
        scheduled = opened.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return max(0, int((opened - scheduled).total_seconds() // 60))

    def __repr__(self) -> str:  # pragma: no cover
        state = "OPEN" if self.is_open else "CLOSED"
        return f"<ChamberSession {self.clinic_id}/{self.doctor_id} {self.session_date} {state}>"


def today_utc() -> date:
    """Session date helper — kept here so callers share one definition."""
    return datetime.now(timezone.utc).date()
