"""Specifications for Session entity queries."""

from __future__ import annotations

from sqlalchemy import ColumnElement

from src.infrastructure.identity.models.session_model import SessionModel
from src.infrastructure.persistence.identity.specifications.base_specification import (
    Specification,
)


class ActiveSessionsSpecification(Specification):
    """Filter for active (non-revoked, non-expired) sessions.

    A session is active if:
    - revoked_at IS NULL
    - expires_at > NOW()
    """

    def apply(self) -> ColumnElement:
        from sqlalchemy import func
        return SessionModel.revoked_at.is_(None) & (
            SessionModel.expires_at > func.now()
        )


class ExpiredSessionsSpecification(Specification):
    """Filter for expired sessions that can be cleaned up."""

    def apply(self) -> ColumnElement:
        from sqlalchemy import func
        return SessionModel.expires_at <= func.now()


class RevokedSessionsSpecification(Specification):
    """Filter for revoked sessions."""

    def apply(self) -> ColumnElement:
        return SessionModel.revoked_at.isnot(None)


class ByUserSpecification(Specification):
    """Filter sessions by user ID.

    Args:
        user_id: UUID string of the user.
    """

    def __init__(self, user_id: str) -> None:
        self.user_id = user_id

    def apply(self) -> ColumnElement:
        return SessionModel.user_id == self.user_id


class TrustedDeviceSpecification(Specification):
    """Filter for sessions on trusted devices."""

    def apply(self) -> ColumnElement:
        return SessionModel.is_trusted == True  # noqa: E712
