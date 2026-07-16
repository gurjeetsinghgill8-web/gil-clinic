"""Mapper: OtpCode domain entity ↔ OtpCodeModel SQLAlchemy model."""

from __future__ import annotations

from src.domain.identity.value_objects.otp_code import OtpCode
from src.infrastructure.identity.models.otp_code_model import OtpCodeModel


class OtpMapper:
    """Converts between OtpCode domain entity and OtpCodeModel."""

    @staticmethod
    def to_model(entity: OtpCode) -> OtpCodeModel:
        return OtpCodeModel(
            id=entity.id,
            user_id=entity.user_id,
            code_hash=entity.code_hash,
            attempts=entity.attempts,
            expires_at=entity.expires_at,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            version=entity.version,
        )

    @staticmethod
    def to_domain(model: OtpCodeModel) -> OtpCode:
        return OtpCode(
            id=model.id,
            user_id=model.user_id,
            code_hash=model.code_hash,
            attempts=model.attempts,
            expires_at=model.expires_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
            version=model.version,
        )

    @staticmethod
    def apply_to_model(model: OtpCodeModel, entity: OtpCode) -> None:
        model.attempts = entity.attempts
        model.updated_at = entity.updated_at
