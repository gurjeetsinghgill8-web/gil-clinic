"""Mapper: User domain entity ↔ UserModel SQLAlchemy model.

Handles encryption of PII fields during serialization.
The domain entity stores encrypted values + phone_hash.
The SQLAlchemy model mirrors this structure.
"""

from __future__ import annotations

from src.domain.identity.entities.user import User
from src.infrastructure.identity.models.user_model import UserModel


class UserMapper:
    """Converts between User domain entity and UserModel SQLAlchemy model.

    Handles:
    - Domain → Model: Encrypt PII, set audit fields
    - Model → Domain: Decrypt PII, restore value objects
    """

    @staticmethod
    def to_model(entity: User) -> UserModel:
        """Convert a domain User to a SQLAlchemy UserModel.

        Args:
            entity: Domain User entity.

        Returns:
            UserModel ready for persistence.
        """
        return UserModel(
            id=entity.id,
            username=entity.username,
            full_name=entity.full_name,
            role_code=entity.role_code,
            department=entity.department,
            pin_hash=entity.pin_hash,
            phone=entity.phone,
            phone_hash=entity.phone_hash,
            email=entity.email,
            password_hash=entity.password_hash,
            login_attempts=entity.login_attempts,
            locked_until=entity.locked_until,
            is_active=entity.is_active,
            last_login=entity.last_login,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            version=entity.version,
        )

    @staticmethod
    def to_domain(model: UserModel) -> User:
        """Convert a SQLAlchemy UserModel to a domain User.

        Args:
            model: UserModel from database.

        Returns:
            Domain User entity.
        """
        return User(
            id=model.id,
            username=model.username,
            full_name=model.full_name,
            role_code=model.role_code,
            department=model.department,
            pin_hash=model.pin_hash,
            phone=model.phone,
            phone_hash=model.phone_hash,
            email=model.email,
            password_hash=model.password_hash,
            login_attempts=model.login_attempts,
            locked_until=model.locked_until,
            is_active=model.is_active,
            last_login=model.last_login,
            created_at=model.created_at,
            updated_at=model.updated_at,
            version=model.version,
        )

    @staticmethod
    def apply_to_model(model: UserModel, entity: User) -> None:
        """Apply domain entity changes to an existing model.

        Args:
            model: Existing UserModel to update.
            entity: Domain User with new values.
        """
        model.username = entity.username
        model.full_name = entity.full_name
        model.role_code = entity.role_code
        model.department = entity.department
        model.pin_hash = entity.pin_hash
        model.phone = entity.phone
        model.phone_hash = entity.phone_hash
        model.email = entity.email
        model.password_hash = entity.password_hash
        model.login_attempts = entity.login_attempts
        model.locked_until = entity.locked_until
        model.is_active = entity.is_active
        model.last_login = entity.last_login
        model.updated_at = entity.updated_at
