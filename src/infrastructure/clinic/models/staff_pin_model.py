"""Staff PIN Model — DB-driven PINs per clinic per role.

Replaces hardcoded STAFF_PINS dict with database storage.
Each clinic has its own set of PINs for each staff role.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.infrastructure.database import Base


class StaffPinModel(Base):
    """Per-clinic, per-role PIN storage.

    Each row = one role's PIN for one clinic.
    """

    __tablename__ = "clinic_staff_pins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[str] = mapped_column(
        String(36), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # "Reception", "ECG", "Echo", "TMT", "Doctor", "Manager", "Dietitian"
    pin: Mapped[str] = mapped_column(
        String(20), nullable=False, default="1234"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<StaffPin clinic={self.clinic_id} role={self.role}>"
