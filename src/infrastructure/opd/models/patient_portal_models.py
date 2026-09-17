"""
Patient Portal models (Smart OPD) — patient khud apni readings bhare + doctor ko
read-only share kare.

Teen tables (`main_v2.py` startup par `Base.metadata.create_all()` inhe apne aap
bana deta hai; SQLite ke liye auto column migrator bhi pehle se hai):

  patient_readings       — har value ek row (BP / sugar / pulse / weight / temp…)
  patient_portal_links   — patient ka secret portal link (`/my/<token>`)
  patient_shares         — read-only doctor snapshot (`/s/<token>`, 7 din)
  patient_requests       — (Phase 4) appointment/follow-up request + doctor reply
"""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import (
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.domain.base_entity import uuid7
from src.shared.infrastructure.database import Base


class PatientReadingModel(Base):
    """Ek self-reported (ya clinic) reading — per-metric row.

    Structured rakhne ka fayda: ek hi BP aage graph, doctor ke Patient Monitor
    tab, PDF/HTML/CSV report aur (baad me) prescription ke average me kaam aata hai.
    """

    __tablename__ = "patient_readings"
    __table_args__ = (
        Index("idx_patient_readings_patient_time", "patient_id", "date_time"),
        Index("idx_patient_readings_patient_code", "patient_id", "code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    clinic_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    patient_id: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(40), nullable=False, default="custom")
    label: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    unit: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    #: Reading ka waqt (save ka nahi) — ISO string, patient khud set karta hai
    date_time: Mapped[str] = mapped_column(String(40), nullable=False, default="", index=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="patient")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ok")
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def to_dict(self) -> dict:
        return {
            "reading_id": str(self.id),
            "patient_id": self.patient_id,
            "code": self.code,
            "label": self.label,
            "unit": self.unit,
            "value": self.value,
            "date_time": self.date_time,
            "source": self.source,
            "status": self.status,
            "note": self.note or "",
        }

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PatientReading {self.patient_id} {self.code}={self.value}>"


class PatientPortalLinkModel(Base):
    """Patient ka secret portal link (`/my/<token>`) — WhatsApp par bhejne ke liye.

    Token DB me random hai (revocable): doctor `active=0` karke band kar sakta hai
    aur naya bana sakta hai.
    """

    __tablename__ = "patient_portal_links"
    __table_args__ = (
        Index("idx_portal_links_token", "token", unique=True),
        Index("idx_portal_links_patient", "patient_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    token: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    patient_id: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    patient_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    phone: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    phone_last4: Mapped[str] = mapped_column(String(4), nullable=False, default="")
    active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    expires_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    use_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PatientPortalLink {self.patient_id} active={self.active}>"


class PatientShareModel(Base):
    """Read-only snapshot — patient ne khud kisi doctor ko bheja (`/s/<token>`).

    Snapshot (live query nahi) is liye ki jis doctor ke paas login nahi hai wo bhi
    ek secret token se sirf ek frozen copy dekh sake — aur 7 din baad apne aap band.
    """

    __tablename__ = "patient_shares"
    __table_args__ = (
        Index("idx_patient_shares_token", "token", unique=True),
        Index("idx_patient_shares_patient", "patient_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    token: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    patient_id: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    patient_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    #: readings + patient info ka JSON snapshot (jaisa us waqt tha waisa hi rehta hai)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PatientShare {self.patient_id} exp={self.expires_at}>"


class PatientRequestModel(Base):
    """(Phase 4) Patient ki appointment / follow-up request + doctor ka reply."""

    __tablename__ = "patient_requests"
    __table_args__ = (Index("idx_patient_requests_patient", "patient_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    patient_id: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    patient_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    phone: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="requested")
    reply_date: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    reply_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PatientRequest {self.patient_id} {self.status}>"
