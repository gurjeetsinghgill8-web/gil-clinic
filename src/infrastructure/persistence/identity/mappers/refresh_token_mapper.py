"""Mapper: RefreshToken domain entity ↔ RefreshTokenModel SQLAlchemy model."""

from __future__ import annotations

from src.domain.identity.entities.refresh_token import RefreshToken
from src.infrastructure.identity.models.refresh_token_model import (
    RefreshTokenModel,
)


class RefreshTokenMapper:
    """Converts between RefreshToken domain entity and RefreshTokenModel."""

    @staticmethod
    def to_model(entity: RefreshToken) -> RefreshTokenModel:
        return RefreshTokenModel(
            id=entity.id,
            user_id=entity.user_id,
            token_hash=entity.token_hash,
            session_id=entity.session_id,
            device_id=entity.device_id,
            is_revoked=entity.is_revoked,
            expires_at=entity.expires_at,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            revoked_at=entity.revoked_at,
            version=entity.version,
        )

    @staticmethod
    def to_domain(model: RefreshTokenModel) -> RefreshToken:
        return RefreshToken(
            id=model.id,
            user_id=model.user_id,
            token_hash=model.token_hash,
            session_id=model.session_id,
            device_id=model.device_id,
            is_revoked=model.is_revoked,
            expires_at=model.expires_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
            revoked_at=model.revoked_at,
            version=model.version,
        )

    @staticmethod
    def apply_to_model(model: RefreshTokenModel, entity: RefreshToken) -> None:
        model.is_revoked = entity.is_revoked
        model.expires_at = entity.expires_at
        model.updated_at = entity.updated_at
        model.revoked_at = entity.revoked_at
