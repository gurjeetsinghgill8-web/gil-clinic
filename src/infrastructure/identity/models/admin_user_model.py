"""SQLAlchemy model for admin_users table.

Stores Super Admin and CEO credentials with bcrypt-hashed passwords.

Roles:
- super_admin: Technical team (Gurjeet) — ALL powers, 16-char auto-gen password
- ceo: CEO — add doctors, manage licenses, 12-char fixed password
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.infrastructure.database import Base


class AdminUserModel(Base):
    """Super Admin & CEO authentication model.

    Separate from the staff/clinic login system. These accounts
    manage the entire platform across all clinics.
    """

    __tablename__ = "admin_users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    username: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    password_hash: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="ceo"
    )  # "super_admin" or "ceo"
    display_name: Mapped[str] = mapped_column(
        String(200), nullable=False, default=""
    )
    email: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )

    # Security
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    login_attempts: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Audit
    last_login: Mapped[datetime | None] = mapped_column(
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

    def __repr__(self) -> str:
        return (
            f"<AdminUserModel id={self.id} "
            f"username={self.username} "
            f"role={self.role}>"
        )
