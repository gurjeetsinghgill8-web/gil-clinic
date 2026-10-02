"""User management request/response schemas.

Pydantic v2 models for user CRUD and role management.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CreateUserRequest(BaseModel):
    """Request body for creating a new staff user."""

    username: str = Field(
        ...,
        min_length=3,
        max_length=100,
        pattern=r"^[a-zA-Z0-9._-]+$",
        description="Unique username (alphanumeric, dots, hyphens, underscores).",
    )
    full_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Display name.",
    )
    role_code: str = Field(
        ...,
        description="Role code (e.g., 'DOCTOR', 'NURSE', 'RECEPTIONIST').",
    )
    department: str | None = Field(default=None)
    phone: str = Field(
        ...,
        min_length=10,
        max_length=15,
        description="Phone number (will be encrypted at rest).",
    )
    email: str | None = Field(default=None)
    pin: str | None = Field(
        default=None,
        min_length=4,
        max_length=6,
        description="Optional initial PIN (4-6 digits).",
    )


class UpdateUserRequest(BaseModel):
    """Request body for updating user details."""

    full_name: str | None = Field(default=None)
    department: str | None = Field(default=None)
    email: str | None = Field(default=None)
    phone: str | None = Field(default=None)
    is_active: bool | None = Field(default=None)


class UserResponse(BaseModel):
    """Response body for user queries."""

    id: str = Field(...)
    username: str = Field(...)
    full_name: str = Field(...)
    role_code: str = Field(...)
    department: str | None = Field(default=None)
    phone: str | None = Field(default=None)
    email: str | None = Field(default=None)
    is_active: bool = Field(default=True)
    is_locked: bool = Field(default=False)
    last_login: datetime | None = Field(default=None)
    created_at: datetime = Field(...)
    updated_at: datetime = Field(...)


class UserListResponse(BaseModel):
    """Response body for listing users."""

    users: list[UserResponse] = Field(...)
    total: int = Field(...)


# ------------------------------------------------------------------
# Role Assignment
# ------------------------------------------------------------------

class AssignRoleRequest(BaseModel):
    """Request body for assigning a role to a user."""

    actor_user_id: str = Field(
        ...,
        description="UUID of the admin performing the assignment.",
    )
    target_user_id: str = Field(
        ...,
        description="UUID of the user receiving the role.",
    )
    role_code: str = Field(
        ...,
        description="New role code (e.g., 'MANAGER').",
    )


class RoleAssignedResponse(BaseModel):
    """Response body for role assignment."""

    message: str = Field(default="Role assigned successfully.")
    user_id: str = Field(...)
    old_role: str | None = Field(default=None)
    new_role: str = Field(...)


# ------------------------------------------------------------------
# Account Unlock
# ------------------------------------------------------------------

class UnlockAccountRequest(BaseModel):
    """Request body for unlocking a locked account."""

    user_id: str = Field(
        ...,
        description="UUID of the user to unlock.",
    )
    unlocked_by: str = Field(
        default="admin",
        description="Who performed the unlock ('admin' or 'system').",
    )


class AccountUnlockedResponse(BaseModel):
    """Response body for account unlock."""

    message: str = Field(default="Account unlocked successfully.")
    user_id: str = Field(...)


class DeactivateUserRequest(BaseModel):
    """Request body for deactivating a user."""

    user_id: str = Field(...)
    reason: str = Field(default="No reason provided.")
