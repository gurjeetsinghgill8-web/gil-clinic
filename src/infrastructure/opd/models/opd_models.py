"""OPD SQLAlchemy models — Complete: Prescription, DrugHistory, Template,
License, Settings, SpecialtyUpgrade, PendingScan.

Mirrors the Bharat AI Clinic master file schema but uses SQLAlchemy async ORM.
All 7 tables from the master file are represented here.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.domain.base_entity import uuid7
from src.shared.infrastructure.database import Base


class OpdPrescriptionModel(Base):
    """Patient OPD prescription record — linked to queue patients via patient_id.

    Mirrors the master file's `patients` table but stores prescription-specific data.
    One patient can have many prescriptions (follow-ups).
    """

    __tablename__ = "opd_prescriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    # Link to queue system's patient_id (e.g. "CQ-20260720-001")
    patient_id: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    patient_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    phone: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    visit_id: Mapped[str] = mapped_column(String(50), nullable=True, index=True)

    # Doctor info
    doctor_id: Mapped[str] = mapped_column(String(100), nullable=False, default="chief")
    specialty: Mapped[str] = mapped_column(String(100), nullable=False, default="General Physician")

    # Clinical data
    vitals: Mapped[str] = mapped_column(Text, nullable=False, default="")
    complaints: Mapped[str] = mapped_column(Text, nullable=False, default="")
    diagnosis: Mapped[str] = mapped_column(Text, nullable=False, default="")
    medicines: Mapped[str] = mapped_column(Text, nullable=False, default="")
    investigations: Mapped[str] = mapped_column(Text, nullable=False, default="")
    advice: Mapped[str] = mapped_column(Text, nullable=False, default="")
    follow_up: Mapped[str] = mapped_column(String(200), nullable=False, default="")

    # Fee & billing
    fee: Mapped[str] = mapped_column(String(20), nullable=False, default="0")

    # Metadata
    is_followup: Mapped[bool] = mapped_column(default=False)
    previous_rx_id = Column(String(36), nullable=True)

    # AI generated
    ai_generated: Mapped[bool] = mapped_column(default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class DrugHistoryModel(Base):
    """Drug names for autocomplete — per doctor.

    Tracks usage frequency so most-used drugs appear first.
    Mirrors master file's `drug_history` table.
    """

    __tablename__ = "opd_drug_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doctor_id: Mapped[str] = mapped_column(String(100), nullable=False, default="chief", index=True)
    drug_name: Mapped[str] = mapped_column(String(200), nullable=False)
    dose: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    use_count: Mapped[int] = mapped_column(Integer, default=1)
    last_used: Mapped[str] = mapped_column(String(30), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class TemplateModel(Base):
    """Rx and Lab templates — per doctor.

    Mirrors master file's `templates` table.
    """

    __tablename__ = "opd_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doctor_id: Mapped[str] = mapped_column(String(100), nullable=False, default="chief", index=True)
    category: Mapped[str] = mapped_column(String(20), nullable=False, default="Rx")  # Rx or Lab
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        # Unique constraint per doctor
        None,
    )


class LicenseModel(Base):
    """Multi-doctor license system — PIN-based auth for licensed doctors.

    Mirrors master file's `licenses` table.
    """

    __tablename__ = "opd_licenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doctor_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    doctor_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    doctor_email: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    doctor_phone: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    pin: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    clinic_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    specialty: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    expiry_date: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    is_active: Mapped[int] = mapped_column(Integer, default=1)
    created_date: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class SettingsModel(Base):
    """Doctor/clinic settings — per doctor.

    Mirrors master file's `settings` table.
    """

    __tablename__ = "opd_settings"

    doctor_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    clinic_name: Mapped[str] = mapped_column(String(200), nullable=False, default="My Clinic")
    doc_name: Mapped[str] = mapped_column(String(200), nullable=False, default="Doctor")
    doc_subtitle: Mapped[str] = mapped_column(String(200), nullable=False, default="MBBS")
    doc_degree: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    doc_reg_no: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    doc_email: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    doc_phone: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    clinic_address: Mapped[str] = mapped_column(Text, nullable=False, default="")
    doc_extra_quals: Mapped[str] = mapped_column(Text, nullable=False, default="")
    groq_api_key: Mapped[str] = mapped_column(String(200), nullable=False, default="")

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class SpecialtyUpgradeModel(Base):
    """AI specialty consultation upgrade — GP vs Specialist comparison.

    Mirrors master file's `specialty_upgrades` table.
    """

    __tablename__ = "opd_specialty_upgrades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doctor_id: Mapped[str] = mapped_column(String(100), nullable=False, default="chief", index=True)
    date: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    patient_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    vitals: Mapped[str] = mapped_column(Text, nullable=False, default="")
    original_rx: Mapped[str] = mapped_column(Text, nullable=False, default="")
    specialty: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    upgraded_rx: Mapped[str] = mapped_column(Text, nullable=False, default="")
    evidence: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_starred: Mapped[int] = mapped_column(Integer, default=0)
    star_note: Mapped[str] = mapped_column(Text, nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class PendingScanModel(Base):
    """Batch prescription scan queue — uploaded images awaiting AI OCR.

    Mirrors master file's `pending_scans` table.
    """

    __tablename__ = "opd_pending_scans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doctor_id: Mapped[str] = mapped_column(String(100), nullable=False, default="chief", index=True)
    uploaded_at: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    image_b64: Mapped[str] = mapped_column(Text, nullable=False, default="")
    patient_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    phone: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    vitals: Mapped[str] = mapped_column(Text, nullable=False, default="")
    fee: Mapped[str] = mapped_column(String(20), nullable=False, default="0")
    complaints: Mapped[str] = mapped_column(Text, nullable=False, default="")
    medicines: Mapped[str] = mapped_column(Text, nullable=False, default="")
    investigations: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending, approved, skipped

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
