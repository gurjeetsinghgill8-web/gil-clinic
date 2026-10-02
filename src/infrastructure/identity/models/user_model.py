"""SQLAlchemy model for identity.users table.

Includes:
- OCC: version field for optimistic concurrency control
- Audit: created_by, updated_by
- Soft-delete: is_deleted, deleted_at
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.domain.base_entity import uuid7
from src.shared.infrastructure.database import Base


class UserModel(Base):
    """SQLAlchemy model for identity.users table.

    Maps to the User aggregate root in the domain layer.
    """

    __tablename__ = "users"
    __table_args__ = (
        Index("idx_users_role", "role_code"),
        Index("idx_users_department", "department"),
        Index("idx_users_phone_hash", "phone_hash"),
        Index("idx_users_active", "is_active"),
        {"schema": "identity"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    username: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    full_name: Mapped[str] = mapped_column(String(512), nullable=False)
    role_code: Mapped[str] = mapped_column(
        String(20), ForeignKey("identity.roles.code"), nullable=False
    )
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pin_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str] = mapped_column(String(512), nullable=False)
    phone_hash: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    email: Mapped[str | None] = mapped_column(String(512), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    login_attempts: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    last_login: Mapped[datetime | None] = mapped_column(
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
    sessions = relationship(
        "SessionModel", back_populates="user", cascade="all, delete-orphan"
    )
    refresh_tokens = relationship(
        "RefreshTokenModel",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    otp_codes = relationship(
        "OtpCodeModel", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<UserModel id={self.id} "
            f"username={self.username} "
            f"v={self.version}>"
        )
