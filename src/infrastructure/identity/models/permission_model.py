"""SQLAlchemy model for identity.permissions table."""

from __future__ import annotations

import uuid

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.domain.base_entity import uuid7
from src.shared.infrastructure.database import Base


class PermissionModel(Base):
    """SQLAlchemy model for identity.permissions table.

    Maps role to {resource, action} permission tuples.
    Used for RBAC permission checks on every API call.
    """

    __tablename__ = "permissions"
    __table_args__ = (
        UniqueConstraint(
            "role_code", "resource", "action", name="uq_permission_role_resource_action"
        ),
        {"schema": "identity"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    role_code: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("identity.roles.code", ondelete="CASCADE"),
        nullable=False,
    )
    resource: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    is_granted: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    role = relationship("RoleModel", back_populates="permissions")

    def __repr__(self) -> str:
        return (
            f"<PermissionModel role={self.role_code} "
            f"resource={self.resource} "
            f"action={self.action} "
            f"granted={self.is_granted}>"
        )
