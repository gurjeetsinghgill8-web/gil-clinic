"""Permission value object for the Identity Engine.

Permissions are immutable value objects that define:
- Resource: what is being accessed (e.g., "patients", "queue", "*")
- Action: what operation (e.g., "read", "write", "*")
- is_granted: whether access is granted or denied

Permissions use structural equality — two permissions are equal if they
have the same resource, action, and is_granted.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Permission:
    """Immutable permission value object.

    Attributes:
        resource: Resource name ("patients", "queue", "*" for all).
        action: Action name ("read", "write", "*" for all).
        is_granted: True = allow, False = deny.
    """

    resource: str
    action: str
    is_granted: bool = True

    def matches(self, resource: str, action: str) -> bool:
        """Check if this permission matches a specific resource+action.

        Supports wildcard matching on both resource and action.

        Args:
            resource: Resource to check.
            action: Action to check.

        Returns:
            True if this permission covers the given resource+action.
        """
        if not self.is_granted:
            return False
        if self.resource == "*" or self.action == "*":
            return True
        return self.resource == resource and self.action == action

    def __repr__(self) -> str:
        grant = "GRANT" if self.is_granted else "DENY"
        return f"<Permission {grant} {self.resource}:{self.action}>"
