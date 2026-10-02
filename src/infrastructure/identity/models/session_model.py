"""SQLAlchemy model for identity.user_sessions table.

Includes OCC (version), audit (created_by, updated_by), soft-delete.
"""

from __future__ import annotations

import uuid

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.domain.base_entity import uuid7
from src.shared.infrastructure.database import Base


class SessionModel(Base):
    """SQLAlchemy model for identity.user_sessions table."""

    __tablename__ = "user_sessions"
    __table_args__ = (
        Index("idx_sessions_user", "user_id"),
        Index(
            "idx_sessions_active",
            "user_id",
            postgresql_where=text("revoked_at IS NULL"),
        ),
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
    device_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    device_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    last_activity: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    is_trusted: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    user = relationship("UserModel", back_populates="sessions")
    refresh_tokens = relationship(
        "RefreshTokenModel", back_populates="session"
    )

    def __repr__(self) -> str:
        return (
            f"<SessionModel id={self.id} "
            f"user_id={self.user_id} "
            f"v={self.version}>"
        )
