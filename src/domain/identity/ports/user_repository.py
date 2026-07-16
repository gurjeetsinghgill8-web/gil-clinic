"""User repository interface (port).

Defines the contract for persisting and retrieving User aggregates.
Implemented by SqlAlchemyUserRepository in the infrastructure layer.
"""

from __future__ import annotations

from typing import Protocol

from src.domain.identity.entities.user import User


class UserRepository(Protocol):
    """Interface for User aggregate persistence.

    Domain layer defines this protocol. Infrastructure provides the implementation.
    """

    async def save(self, user: User) -> None:
        """Persist a new or updated user.

        Args:
            user: User aggregate to save.
        """
        ...

    async def get_by_id(self, user_id: str) -> User | None:
        """Get a user by their UUID.

        Args:
            user_id: UUID string.

        Returns:
            User if found, None otherwise.
        """
        ...

    async def get_by_username(self, username: str) -> User | None:
        """Get a user by their unique username.

        Args:
            username: Login username.

        Returns:
            User if found, None otherwise.
        """
        ...

    async def get_by_phone_hash(self, phone_hash: str) -> User | None:
        """Get a user by their phone hash (for lookups on encrypted phone).

        Args:
            phone_hash: SHA-256 hash of phone number.

        Returns:
            User if found, None otherwise.
        """
        ...

    async def exists_by_username(self, username: str) -> bool:
        """Check if a username is already taken.

        Args:
            username: Username to check.

        Returns:
            True if username exists.
        """
        ...

    async def exists_by_phone_hash(self, phone_hash: str) -> bool:
        """Check if a phone number is already registered.

        Args:
            phone_hash: SHA-256 hash of phone number.

        Returns:
            True if phone exists.
        """
        ...

    async def list_active(self) -> list[User]:
        """List all active users.

        Returns:
            List of active User aggregates.
        """
        ...

    async def list_by_role(self, role_code: str) -> list[User]:
        """List users by role.

        Args:
            role_code: Role code to filter by.

        Returns:
            List of matching User aggregates.
        """
        ...

    async def count_admins(self) -> int:
        """Count active users with ADMIN role.

        Returns:
            Number of active admin users.
        """
        ...
