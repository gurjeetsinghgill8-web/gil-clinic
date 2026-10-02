"""Mapper: Role domain entity ↔ RoleModel SQLAlchemy model.

Also maps Permission value objects from PermissionModel.
"""

from __future__ import annotations

from src.domain.identity.entities.role import Role
from src.domain.identity.value_objects.permission import Permission
from src.infrastructure.identity.models.role_model import RoleModel
from src.infrastructure.identity.models.permission_model import PermissionModel


class RoleMapper:
    """Converts between Role domain entity and RoleModel.

    Also maps associated permissions.
    """

    @staticmethod
    def to_model(entity: Role) -> RoleModel:
        return RoleModel(
            code=entity.code,
            name=entity.name,
            hierarchy_level=entity.hierarchy_level,
            description=entity.description,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            version=entity.version,
        )

    @staticmethod
    def to_domain(model: RoleModel) -> Role:
        permissions = set()
        for perm_model in model.permissions:
            permissions.add(
                Permission(
                    resource=perm_model.resource,
                    action=perm_model.action,
                    is_granted=perm_model.is_granted,
                )
            )

        return Role(
            id=model.id,
            code=model.code,
            name=model.name,
            hierarchy_level=model.hierarchy_level,
            description=model.description,
            permissions=permissions,
            created_at=model.created_at,
            updated_at=model.updated_at,
            version=model.version,
        )

    @staticmethod
    def apply_to_model(model: RoleModel, entity: Role) -> None:
        model.name = entity.name
        model.hierarchy_level = entity.hierarchy_level
        model.description = entity.description
        model.updated_at = entity.updated_at
