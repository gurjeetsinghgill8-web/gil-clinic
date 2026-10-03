"""SQLAlchemy model for appointment slots (master blueprint Part B · B5).

Why slots exist at all in a live-queue product
----------------------------------------------
The whole product argues *"live queue > khaali appointment slot"* — because a
slot pretends every patient takes the same 20 minutes, while a new cardiac case
takes 20 and a follow-up takes 6.

But some patients genuinely need a **fixed time**: a working patient who can
only come at 2:30, a follow-up that must happen after a lab report, a patient
coming from another city. For them the answer is a slot that ALSO tells them
what the queue looks like at that moment:

    2:30 PM slot · us waqt tak queue clear hone ka anumaan 🟢 high

So a slot here is a *capacity reservation*, not a promise of a fixed wait. It
reserves one place in the same live OPD queue — the patient still gets a real
token and a real EWT, and still sees the doctor in queue order on the day.

Deliberate deviation from the blueprint
---------------------------------------
The blueprint's SQL has a ``booked INT DEFAULT 0`` column. This model does NOT
store it: the number of bookings is derived from ``queue_entries.slot_id``,
which is the actual truth. A denormalised counter drifts the first time a
booking is cancelled or a patient is marked NO_SHOW — and a slot that claims
"2 booked" while three patients hold tokens is exactly the kind of lie this
product exists to remove.
"""

from __future__ import annotations

import uuid
from datetime import date as date_type
from datetime import datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.infrastructure.database import Base


class AppointmentSlotModel(Base):
    """One bookable time window for one doctor on one day.

    ``start_time`` / ``end_time`` are stored as ``"HH:MM"`` strings, the same
    representation the clinic-hours fields and the EWT engine already use, so
    nothing in the app has to convert between a ``TIME`` column and a string.
    """

    __tablename__ = "appointment_slots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ── Tenancy + partition (same keys the queue engine partitions on) ──────
    clinic_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doctor_id: Mapped[str] = mapped_column(
        String(100), nullable=False, default="chief", server_default="chief"
    )
    service_code: Mapped[str] = mapped_column(
        String(20), nullable=False, default="OPD", server_default="OPD"
    )

    # ── The window ─────────────────────────────────────────────────────────
    slot_date: Mapped[date_type] = mapped_column(Date, nullable=False, index=True)
    start_time: Mapped[str] = mapped_column(String(5), nullable=False)  # "14:30"
    end_time: Mapped[str] = mapped_column(String(5), nullable=False)    # "14:50"

    #: How many patients may hold a slot in this window. 1 = exclusive.
    capacity: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )

    # ── Meta ───────────────────────────────────────────────────────────────
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    note: Mapped[str] = mapped_column(
        String(200), nullable=False, default="", server_default=""
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
            f"<AppointmentSlot {self.slot_date} "
            f"{self.start_time}-{self.end_time} cap={self.capacity}>"
        )

    @property
    def window_label(self) -> str:
        """``"14:30 – 14:50"`` for the grid."""
        return f"{self.start_time} – {self.end_time}"
