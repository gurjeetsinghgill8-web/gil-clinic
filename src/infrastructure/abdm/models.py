"""ABDM compliance models — ABHA links, consent artefacts, DHIS transactions.

Three tables (main_v2 startup `Base.metadata.create_all()` inhe bana deta hai):

    abha_links          — patient ↔ 14-digit ABHA health ID linkage
    consent_artefacts   — patient ka data-share consent (DPDP + ABDM Consent Mgr)
    abdm_transactions   — har ABDM transaction ka log (DHIS incentive claim ke liye)
"""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.infrastructure.database import Base


class AbhaLinkModel(Base):
    """Patient ka ABHA (Ayushman Bharat Health Account) linkage."""

    __tablename__ = "abha_links"
    __table_args__ = (
        Index("idx_abha_links_patient", "patient_id", unique=True),
        Index("idx_abha_links_number", "abha_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clinic_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    patient_id: Mapped[str] = mapped_column(String(30), nullable=False)
    abha_number: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    abha_address: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    #: pending | linked | failed
    linked_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AbhaLink {self.patient_id} {self.status}>"


class ConsentArtefactModel(Base):
    """Patient ka data-share consent (ABDM Consent Manager + DPDP Act 2023)."""

    __tablename__ = "consent_artefacts"
    __table_args__ = (
        Index("idx_consent_patient", "patient_id", "granted_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clinic_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    patient_id: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    hip_id: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    hiu_id: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    data_types: Mapped[str] = mapped_column(Text, nullable=False, default="")  # comma list
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="granted")
    #: granted | revoked | expired
    granted_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ConsentArtefact {self.patient_id} {self.status}>"


class AbdmTransactionModel(Base):
    """Har ABDM transaction ka log — DHIS (Digital Health Incentive Scheme)
    claim ke liye. NHA har transaction (ABHA create, record link, token, scan)
    par facility ko incentive deta hai; ye table wahi audit trail hai."""

    __tablename__ = "abdm_transactions"
    __table_args__ = (
        Index("idx_abdm_txn_patient", "patient_id", "created_at"),
        Index("idx_abdm_txn_type", "txn_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clinic_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    patient_id: Mapped[str] = mapped_column(String(30), nullable=False, default="", index=True)
    txn_type: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    #: abha_create | record_link | token_generate | scan_share | consent_grant
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    #: pending | success | failed
    request_id: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AbdmTransaction {self.txn_type} {self.status}>"
