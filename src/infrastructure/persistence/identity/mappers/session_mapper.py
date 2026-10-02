"""Mapper: Session domain entity ↔ SessionModel SQLAlchemy model."""

from __future__ import annotations

from src.domain.identity.entities.session import Session
from src.infrastructure.identity.models.session_model import SessionModel


class SessionMapper:
    """Converts between Session domain entity and SessionModel."""

    @staticmethod
    def to_model(entity: Session) -> SessionModel:
        return SessionModel(
            id=entity.id,
            user_id=entity.user_id,
            device_id=entity.device_id,
            device_name=entity.device_name,
            user_agent=entity.user_agent,
            ip_address=entity.ip_address,
            last_activity=entity.last_activity,
            is_trusted=entity.is_trusted,
            expires_at=entity.expires_at,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            revoked_at=entity.revoked_at,
            version=entity.version,
        )

    @staticmethod
    def to_domain(model: SessionModel) -> Session:
        return Session(
            id=model.id,
            user_id=model.user_id,
            device_id=model.device_id,
            device_name=model.device_name,
            user_agent=model.user_agent,
            ip_address=model.ip_address,
            last_activity=model.last_activity,
            is_trusted=model.is_trusted,
            expires_at=model.expires_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
            revoked_at=model.revoked_at,
            version=model.version,
        )

    @staticmethod
    def apply_to_model(model: SessionModel, entity: Session) -> None:
        model.device_id = entity.device_id
        model.device_name = entity.device_name
        model.user_agent = entity.user_agent
        model.ip_address = entity.ip_address
        model.last_activity = entity.last_activity
        model.is_trusted = entity.is_trusted
        model.expires_at = entity.expires_at
        model.updated_at = entity.updated_at
        model.revoked_at = entity.revoked_at
