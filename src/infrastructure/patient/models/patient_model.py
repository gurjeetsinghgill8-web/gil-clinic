"""SQLAlchemy model for patient.patients table.

Includes:
- OCC: version field for optimistic concurrency control
- JSON columns for value objects (demographics, contact, devices, etc.)
- QR hash index for fast PWA login lookup
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, func
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.domain.base_entity import uuid7
from src.shared.infrastructure.database import Base


class PatientModel(Base):
    """SQLAlchemy model for patient.patients table.

    Maps to the Patient aggregate root in the domain layer.
    Nested value objects (Demographics, ContactInfo, etc.) are stored as JSONB.
    """

    __tablename__ = "patients"
    __table_args__ = (
        Index("idx_patients_patient_id", "patient_id", unique=True),
        Index("idx_patients_phone_hash", "phone_hash"),
        Index("idx_patients_qr_hash", "qr_hash"),
        Index("idx_patients_name", "name"),
        Index("idx_patients_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    patient_id: Mapped[str] = mapped_column(
        String(30), unique=True, nullable=False, index=True
    )
    # Demographics (JSONB for nested value object)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    gender: Mapped[str] = mapped_column(String(10), nullable=False)
    date_of_birth: Mapped[str | None] = mapped_column(String(20), nullable=True)
    blood_group: Mapped[str | None] = mapped_column(String(5), nullable=True)

    # Contact (phone_hash for lookup, phone encrypted at rest)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    phone_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Emergency Contact (JSON)
    emergency_contact: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )

    # QR Identity (JSON)
    qr_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    qr_identity: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Status
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )
    status_reason: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )

    # Devices (JSON array)
    registered_devices: Mapped[list | None] = mapped_column(
        JSON, nullable=True, default=list
    )

    # Notification Preferences (JSON)
    notification_preferences: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )

    # Medical History (JSON array)
    medical_history: Mapped[list | None] = mapped_column(
        JSON, nullable=True, default=list
    )

    # Visit tracking
    last_visit_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    total_visits: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    # Merge tracking
    merged_into_patient_id: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )

    # Reception inquiry
    reception_inquiry: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    # OCC + Audit
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<PatientModel id={self.patient_id} name={self.name} status={self.status}>"
