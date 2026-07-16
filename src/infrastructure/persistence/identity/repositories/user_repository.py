"""SQLAlchemy repository for User aggregate.

Implements UserRepository port protocol from domain layer.
Uses Specification pattern for filtering.
Supports OCC via version field in BaseRepository.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from src.domain.identity.entities.user import User
from src.infrastructure.identity.models.user_model import UserModel
from src.infrastructure.persistence.identity.mappers.user_mapper import (
    UserMapper,
)
from src.infrastructure.persistence.identity.repositories.base_repository import (
    BaseRepository,
)
from src.infrastructure.persistence.identity.specifications.base_specification import (
    Specification,
)
from src.infrastructure.persistence.identity.specifications.user_specifications import (
    ActiveUsersSpecification,
    ByPhoneHashSpecification,
    ByRoleSpecification,
    ByUsernameSpecification,
    NotDeletedSpecification,
    UsernameSearchSpecification,
)


class SqlAlchemyUserRepository(BaseRepository[User, UserModel]):
    """Repository for User aggregate with OCC and Specification support."""

    def __init__(self, session) -> None:
        super().__init__(session)
        self._mapper = UserMapper()

    @property
    def _model_class(self) -> type[UserModel]:
        return UserModel

    def _to_domain(self, model: UserModel) -> User:
        return self._mapper.to_domain(model)

    def _apply_to_model(self, model: UserModel, entity: User) -> None:
        self._mapper.apply_to_model(model, entity)

    def _default_eager_loads(self, query):
        """Eager load sessions and refresh_tokens to avoid N+1."""
        return query.options(
            joinedload(UserModel.sessions),
            joinedload(UserModel.refresh_tokens),
            joinedload(UserModel.otp_codes),
        )

    # ------------------------------------------------------------------
    # UserRepository port implementations
    # ------------------------------------------------------------------

    async def get_by_username(self, username: str) -> User | None:
        """Get a user by their unique username."""
        spec = ByUsernameSpecification(username) & NotDeletedSpecification()
        return await self.find_one(spec)

    async def get_by_phone_hash(self, phone_hash: str) -> User | None:
        """Get a user by phone hash."""
        spec = ByPhoneHashSpecification(phone_hash) & NotDeletedSpecification()
        return await self.find_one(spec)

    async def exists_by_username(self, username: str) -> bool:
        """Check if a username is already taken."""
        return await self._check_duplicate(
            UserModel.username, username
        )

    async def exists_by_phone_hash(self, phone_hash: str) -> bool:
        """Check if a phone number is already registered."""
        return await self._check_duplicate(
            UserModel.phone_hash, phone_hash
        )

    async def list_active(self) -> list[User]:
        """List all active (not deactivated, not soft-deleted) users."""
        spec = ActiveUsersSpecification() & NotDeletedSpecification()
        return await self.find(spec)

    async def list_by_role(self, role_code: str) -> list[User]:
        """List users by role code."""
        spec = (
            ByRoleSpecification(role_code)
            & ActiveUsersSpecification()
            & NotDeletedSpecification()
        )
        return await self.find(spec)

    async def count_admins(self) -> int:
        """Count active admin users."""
        spec = (
            ByRoleSpecification("ADMIN")
            & ActiveUsersSpecification()
            & NotDeletedSpecification()
        )
        return await self.count(spec)

    async def search_by_username(
        self, query: str, limit: int = 20
    ) -> list[User]:
        """Search users by username (ILIKE partial match)."""
        spec = UsernameSearchSpecification(query) & NotDeletedSpecification()
        return await self.find(spec)
