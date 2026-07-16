"""SQLAlchemy repository for Role entity.

Roles use string primary keys (code), not UUIDs.
Specification pattern is still supported for filtering.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from src.domain.identity.entities.role import Role
from src.infrastructure.identity.models.permission_model import PermissionModel
from src.infrastructure.identity.models.role_model import RoleModel
from src.infrastructure.persistence.identity.mappers.role_mapper import (
    RoleMapper,
)
from src.infrastructure.persistence.identity.repositories.base_repository import (
    BaseRepository,
)
from src.infrastructure.persistence.identity.specifications.base_specification import (
    Specification,
)
from src.infrastructure.persistence.identity.specifications.user_specifications import (
    NotDeletedSpecification,
)


class SqlAlchemyRoleRepository(BaseRepository[Role, RoleModel]):
    """Repository for Role entity.

    Roles use string primary keys (role code like 'ADMIN', 'DOCTOR').
    Includes permission management via the join table.
    """

    def __init__(self, session) -> None:
        super().__init__(session)
        self._mapper = RoleMapper()

    @property
    def _model_class(self) -> type[RoleModel]:
        return RoleModel

    def _to_domain(self, model: RoleModel) -> Role:
        return self._mapper.to_domain(model)

    def _apply_to_model(self, model: RoleModel, entity: Role) -> None:
        self._mapper.apply_to_model(model, entity)

    def _default_eager_loads(self, query):
        """Eager load permissions to avoid N+1."""
        return query.options(joinedload(RoleModel.permissions))

    # ------------------------------------------------------------------
    # Role-specific queries
    # ------------------------------------------------------------------

    async def get_by_code(self, code: str) -> Role | None:
        """Get a role by its unique code.

        Args:
            code: Role code (e.g., 'DOCTOR', 'NURSE').

        Returns:
            Role domain entity if found, None otherwise.
        """
        # Role doesn't use soft-delete (roles are reference data)
        query = (
            select(RoleModel)
            .where(RoleModel.code == code)
            .options(joinedload(RoleModel.permissions))
        )
        result = await self.session.execute(query)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def list_all(self) -> list[Role]:
        """List all roles with their permissions.

        Returns:
            List of all Role domain entities.
        """
        query = select(RoleModel).options(joinedload(RoleModel.permissions))
        result = await self.session.execute(query)
        models = list(result.scalars().unique().all())
        return [self._to_domain(m) for m in models]

    async def list_by_hierarchy_level(self, min_level: int = 0) -> list[Role]:
        """List roles with hierarchy level >= min_level.

        Args:
            min_level: Minimum hierarchy level (default 0 = all).

        Returns:
            List of matching Role domain entities.
        """
        query = (
            select(RoleModel)
            .where(RoleModel.hierarchy_level >= min_level)
            .options(joinedload(RoleModel.permissions))
        )
        result = await self.session.execute(query)
        models = list(result.scalars().unique().all())
        return [self._to_domain(m) for m in models]

    async def exists_by_code(self, code: str) -> bool:
        """Check if a role code exists.

        Args:
            code: Role code to check.

        Returns:
            True if role exists.
        """
        query = select(RoleModel.code).where(RoleModel.code == code)
        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None

    # ------------------------------------------------------------------
    # Permission management
    # ------------------------------------------------------------------

    async def add_permission(
        self, role_code: str, resource: str, action: str, is_granted: bool = True
    ) -> bool:
        """Add a permission to a role.

        Args:
            role_code: Role code to assign permission to.
            resource: Resource name (e.g., 'patients').
            action: Action name (e.g., 'read').
            is_granted: Whether permission is granted (default True).

        Returns:
            True if permission was added.
        """
        existing = await self.get_by_code(role_code)
        if not existing:
            return False

        permission = PermissionModel(
            role_code=role_code,
            resource=resource,
            action=action,
            is_granted=is_granted,
        )
        self.session.add(permission)
        await self.session.flush()
        return True

    async def remove_permission(
        self, role_code: str, resource: str, action: str
    ) -> bool:
        """Remove a permission from a role.

        Args:
            role_code: Role code to remove permission from.
            resource: Resource name.
            action: Action name.

        Returns:
            True if permission was removed.
        """
        from sqlalchemy import delete

        stmt = delete(PermissionModel).where(
            PermissionModel.role_code == role_code,
            PermissionModel.resource == resource,
            PermissionModel.action == action,
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount > 0

    async def get_permissions(
        self, role_code: str
    ) -> list[tuple[str, str, bool]]:
        """Get all permissions for a role.

        Args:
            role_code: Role code.

        Returns:
            List of (resource, action, is_granted) tuples.
        """
        query = select(PermissionModel).where(
            PermissionModel.role_code == role_code
        )
        result = await self.session.execute(query)
        models = list(result.scalars().all())
        return [
            (p.resource, p.action, p.is_granted) for p in models
        ]
