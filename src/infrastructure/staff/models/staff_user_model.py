"""
StaffUserModel — Multi-user staff authentication.

Stores receptionists, doctors, and admins with their own login credentials
and OPD assignments. Supports:
- Receptionist: login via phone + password
- Doctor: login via PIN
- Admin: full access

Each user can be assigned to specific OPDs (ECG, Echo, TMT, OPD, etc.)
to control what they see and manage.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.domain.base_entity import uuid7
from src.shared.infrastructure.database import Base


class StaffUserModel(Base):
    """Staff user account — receptionist, doctor, or admin."""

    __tablename__ = "staff_users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid7()))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=True, default="")
    password_hash: Mapped[str] = mapped_column(String(256), nullable=True, default="")
    pin: Mapped[str] = mapped_column(String(10), nullable=True, default="")
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="receptionist")
    assigned_opds: Mapped[str] = mapped_column(Text, nullable=True, default="[]")  # JSON list
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<StaffUser {self.name} ({self.role})>"
