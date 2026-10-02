"""SQLAlchemy model for identity.refresh_tokens table."""

from __future__ import annotations

import uuid

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.domain.base_entity import uuid7
from src.shared.infrastructure.database import Base


class RefreshTokenModel(Base):
    """SQLAlchemy model for identity.refresh_tokens table.

    Maps to the RefreshToken aggregate (separate from User aggregate).
    Enables multi-device refresh tokens + token rotation.
    """

    __tablename__ = "refresh_tokens"
    __table_args__ = (
        Index("idx_refresh_user", "user_id"),
        Index("idx_refresh_hash", "token_hash"),
        Index("idx_refresh_active", "user_id", postgresql_where=text("is_revoked = false")),
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
    token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("identity.user_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    device_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    is_revoked: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    user = relationship("UserModel", back_populates="refresh_tokens")
    session = relationship("SessionModel", back_populates="refresh_tokens")

    def __repr__(self) -> str:
        return (
            f"<RefreshTokenModel id={self.id} "
            f"v={self.version}>"
        )
