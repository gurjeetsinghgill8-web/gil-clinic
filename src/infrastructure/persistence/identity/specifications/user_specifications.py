"""Specifications for User entity queries.

Encapsulates reusable query filters for the User aggregate.
Combined with & (AND), | (OR), ~ (NOT) via base Specification class.

Usage:
    spec = ActiveUsersSpecification() & ByRoleSpecification("DOCTOR")
    users = await repo.find(spec)
"""

from __future__ import annotations

from sqlalchemy import ColumnElement

from src.infrastructure.identity.models.user_model import UserModel
from src.infrastructure.persistence.identity.specifications.base_specification import (
    Specification,
)


class ActiveUsersSpecification(Specification):
    """Filter for active (not deactivated, not soft-deleted) users."""

    def apply(self) -> ColumnElement:
        return UserModel.is_active == True  # noqa: E712


class InactiveUsersSpecification(Specification):
    """Filter for deactivated users."""

    def apply(self) -> ColumnElement:
        return UserModel.is_active == False  # noqa: E712


class LockedUsersSpecification(Specification):
    """Filter for users whose account is currently locked."""

    def apply(self) -> ColumnElement:
        from sqlalchemy import func
        return UserModel.locked_until > func.now()


class ByRoleSpecification(Specification):
    """Filter by role code.

    Args:
        role_code: Role code to filter by (e.g., "DOCTOR").
    """

    def __init__(self, role_code: str) -> None:
        self.role_code = role_code

    def apply(self) -> ColumnElement:
        return UserModel.role_code == self.role_code


class ByDepartmentSpecification(Specification):
    """Filter by department.

    Args:
        department: Department name to filter by.
    """

    def __init__(self, department: str) -> None:
        self.department = department

    def apply(self) -> ColumnElement:
        return UserModel.department == self.department


class ByUsernameSpecification(Specification):
    """Find user by exact username.

    Args:
        username: Exact username to match.
    """

    def __init__(self, username: str) -> None:
        self.username = username

    def apply(self) -> ColumnElement:
        return UserModel.username == self.username


class UsernameSearchSpecification(Specification):
    """Search users by username (ILIKE).

    Args:
        query: Search string (case-insensitive partial match).
    """

    def __init__(self, query: str) -> None:
        self.query = query

    def apply(self) -> ColumnElement:
        return UserModel.username.ilike(f"%{self.query}%")


class ByPhoneHashSpecification(Specification):
    """Find user by phone hash.

    Args:
        phone_hash: SHA-256 hash of the phone number.
    """

    def __init__(self, phone_hash: str) -> None:
        self.phone_hash = phone_hash

    def apply(self) -> ColumnElement:
        return UserModel.phone_hash == self.phone_hash


class NotDeletedSpecification(Specification):
    """Filter out soft-deleted records."""

    def apply(self) -> ColumnElement:
        return UserModel.is_deleted == False  # noqa: E712
