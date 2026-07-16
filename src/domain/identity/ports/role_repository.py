"""Role repository interface (port).

Defines the contract for retrieving Role entities.
Implemented by SqlAlchemyRoleRepository in the infrastructure layer.

Roles are reference data — they are defined at seed time and rarely change.
"""

from __future__ import annotations

from typing import Protocol

from src.domain.identity.entities.role import Role


class RoleRepository(Protocol):
    """Interface for Role entity persistence.

    Roles are loaded at startup and cached. They are reference data,
    not aggregates — they don't have complex lifecycle management.
    """

    async def save(self, role: Role) -> None:
        """Persist a new or updated role.

        Args:
            role: Role to save.
        """
        ...

    async def get_by_code(self, code: str) -> Role | None:
        """Get a role by its code.

        Args:
            code: Role code (e.g., "DOCTOR", "NURSE").

        Returns:
            Role if found, None otherwise.
        """
        ...

    async def list_all(self) -> list[Role]:
        """List all roles.

        Returns:
            List of all Role entities.
        """
        ...

    async def exists_by_code(self, code: str) -> bool:
        """Check if a role code exists.

        Args:
            code: Role code to check.

        Returns:
            True if role exists.
        """
        ...
