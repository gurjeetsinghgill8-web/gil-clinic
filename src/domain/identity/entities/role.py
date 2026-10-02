"""Role entity for the Identity Engine.

Roles define a hierarchy level and a set of permissions.
The role with the highest hierarchy level has the most authority.

Hierarchy levels (from the seed data):
- ADMIN = 100
- MANAGER = 80
- DOCTOR = 60
- NURSE = 50
- RECEPTIONIST, TECHNICIAN, PHARMACIST, LAB_TECH, RADIOLOGIST = 40
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from src.shared.domain.base_entity import BaseEntity

if TYPE_CHECKING:
    from src.domain.identity.value_objects.permission import Permission


@dataclass
class Role(BaseEntity):
    """Role entity.

    Represents a job role in the hospital system with:
    - A unique code (e.g., "DOCTOR", "NURSE")
    - A display name
    - A hierarchy level (0-100, higher = more authority)
    - A set of permissions (role-based access control)

    Attributes:
        code: Unique role code (primary identifier, e.g., "DOCTOR").
        name: Human-readable display name.
        hierarchy_level: Numeric level (0-100).
        description: Optional description of the role.
        permissions: Set of Permission value objects assigned to this role.
    """

    code: str
    name: str
    hierarchy_level: int
    description: str | None = None
    permissions: set = field(default_factory=set)  # set[Permission]

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        code: str,
        name: str,
        hierarchy_level: int,
        description: str | None = None,
    ) -> Role:
        """Create a new Role.

        Args:
            code: Unique role code (e.g., "DOCTOR").
            name: Human-readable name.
            hierarchy_level: Numeric level (0-100).
            description: Optional description.

        Returns:
            A new Role instance.
        """
        return cls(
            code=code,
            name=name,
            hierarchy_level=hierarchy_level,
            description=description,
        )

    # ------------------------------------------------------------------
    # Permission Checks
    # ------------------------------------------------------------------

    def has_permission(self, resource: str, action: str) -> bool:
        """Check if this role has a specific permission.

        Args:
            resource: Resource name (e.g., "patients", "queue").
            action: Action name (e.g., "read", "write").

        Returns:
            True if the role has the permission and it is granted.
        """
        from src.domain.identity.value_objects.permission import Permission

        wildcard = Permission(resource="*", action="*", is_granted=True)

        for perm in self.permissions:
            if not perm.is_granted:
                continue
            # Exact match
            if perm.resource == resource and perm.action == action:
                return True
            # Wildcard resource or action
            if perm.resource == "*" or perm.action == "*":
                return True
            # Match exact permission
            if perm == wildcard:
                return True
        return False

    def has_resource_access(self, resource: str) -> bool:
        """Check if this role has any access to a resource.

        Args:
            resource: Resource name.

        Returns:
            True if any permission grants access to this resource.
        """
        for perm in self.permissions:
            if not perm.is_granted:
                continue
            if perm.resource == resource or perm.resource == "*":
                return True
        return False

    def add_permission(self, permission: Permission) -> None:
        """Assign a permission to this role.

        Args:
            permission: Permission value object to add.
        """
        self.permissions.add(permission)

    def remove_permission(self, permission: Permission) -> None:
        """Remove a permission from this role.

        Args:
            permission: Permission value object to remove.
        """
        self.permissions.discard(permission)

    # ------------------------------------------------------------------
    # Hierarchy
    # ------------------------------------------------------------------

    def is_higher_than(self, other: Role) -> bool:
        """Check if this role has a higher hierarchy level.

        Args:
            other: Another Role to compare against.

        Returns:
            True if this role's hierarchy > other's hierarchy.
        """
        return self.hierarchy_level > other.hierarchy_level

    def is_lower_than(self, other: Role) -> bool:
        """Check if this role has a lower hierarchy level.

        Args:
            other: Another Role to compare against.

        Returns:
            True if this role's hierarchy < other's hierarchy.
        """
        return self.hierarchy_level < other.hierarchy_level

    def can_manage(self, other: Role) -> bool:
        """Check if this role can manage another role.

        A role can manage another role only if:
        - This role's hierarchy is strictly higher
        - This role has admin-level permissions

        Args:
            other: The target role.

        Returns:
            True if this role can manage the target role.
        """
        return self.hierarchy_level > other.hierarchy_level

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def __hash__(self) -> int:
        return hash(self.code)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Role):
            return NotImplemented
        return self.code == other.code

    def __repr__(self) -> str:
        return (
            f"<Role code={self.code} "
            f"name={self.name} "
            f"level={self.hierarchy_level}>"
        )
