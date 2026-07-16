"""SQLAlchemy model for identity.otp_codes table."""

from __future__ import annotations

import uuid

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.domain.base_entity import uuid7
from src.shared.infrastructure.database import Base


class OtpCodeModel(Base):
    """SQLAlchemy model for identity.otp_codes table.

    Ephemeral storage for OTP hashes.
    Entries are cleaned up after expiry (5 minutes) or on successful verification.
    """

    __tablename__ = "otp_codes"
    __table_args__ = (
        Index("idx_otp_user", "user_id"),
        Index("idx_otp_expired", "expires_at"),
        {"schema": "identity"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("identity.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    code_hash: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    attempts: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    # --- OCC, audit, soft-delete ---
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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

    # Relationships
    user = relationship("UserModel", back_populates="otp_codes")

    def __repr__(self) -> str:
        return (
            f"<OtpCodeModel id={self.id} "
            f"user_id={self.user_id} "
            f"attempts={self.attempts} "
            f"v={self.version}>"
        )
