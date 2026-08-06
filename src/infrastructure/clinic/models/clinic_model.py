"""SQLAlchemy model for clinics table — multi-tenant core.

Each clinic = one doctor's practice. Stores:
- Doctor/clinic details
- Auto-generated credentials (username, password hash, PINs)
- License dates and status
- All patient data is scoped to clinic_id
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.infrastructure.database import Base


class ClinicModel(Base):
    """Multi-tenant clinic registry.

    Each row represents one doctor's clinic with full isolation.
    """

    __tablename__ = "clinics"

    # ── Identity ──────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinic_name: Mapped[str] = mapped_column(
        String(200), nullable=False
    )
    clinic_code: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, index=True
    )  # e.g., "CLINIC-001"

    # ── Doctor Details ────────────────────────────────────────────────────
    doctor_name: Mapped[str] = mapped_column(
        String(200), nullable=False
    )
    doctor_phone: Mapped[str] = mapped_column(
        String(20), nullable=False, default=""
    )
    doctor_email: Mapped[str] = mapped_column(
        String(200), nullable=False, default=""
    )
    doctor_degree: Mapped[str] = mapped_column(
        String(500), nullable=False, default=""
    )
    doctor_reg_no: Mapped[str] = mapped_column(
        String(100), nullable=False, default=""
    )
    specialty: Mapped[str] = mapped_column(
        String(100), nullable=False, default="General Physician"
    )

    # ── Clinic Address ────────────────────────────────────────────────────
    address: Mapped[str] = mapped_column(
        Text, nullable=False, default=""
    )
    city: Mapped[str] = mapped_column(
        String(100), nullable=False, default=""
    )
    state: Mapped[str] = mapped_column(
        String(100), nullable=False, default=""
    )

    # ── Auth Credentials (auto-generated) ─────────────────────────────────
    clinic_username: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=True
    )  # e.g., "GURJ-CLINIC-001"
    clinic_password_hash: Mapped[str] = mapped_column(
        String(255), nullable=True
    )  # bcrypt hashed, 8-char random
    doctor_opd_pin: Mapped[str] = mapped_column(
        String(20), nullable=True
    )  # 4-digit PIN for doctor OPD portal
    dietician_pin: Mapped[str] = mapped_column(
        String(20), nullable=True
    )  # 4-digit PIN for dietician
    staff_default_pin: Mapped[str] = mapped_column(
        String(20), nullable=False, default="1234"
    )  # default for ECG/Echo/TMT/etc

    # ── License ───────────────────────────────────────────────────────────
    license_start_date: Mapped[str] = mapped_column(
        String(20), nullable=False, default=""
    )
    license_expiry_date: Mapped[str] = mapped_column(
        String(20), nullable=False, default=""
    )
    license_duration_months: Mapped[int] = mapped_column(
        Integer, nullable=False, default=2
    )  # 2, 3, or 4 months
    is_license_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    # ── Meta ──────────────────────────────────────────────────────────────
    created_by: Mapped[str] = mapped_column(
        String(100), nullable=False, default=""
    )  # which admin created
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<ClinicModel id={self.id} "
            f"code={self.clinic_code} "
            f"doctor={self.doctor_name}>"
        )
