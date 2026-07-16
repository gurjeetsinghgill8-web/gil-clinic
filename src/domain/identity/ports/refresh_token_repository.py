"""Refresh token repository interface (port).

Defines the contract for persisting and retrieving RefreshToken aggregates.
Implemented by SqlAlchemyRefreshTokenRepository in the infrastructure layer.

Supports token rotation: finding and revoking tokens by hash.
"""

from __future__ import annotations

from typing import Protocol

from src.domain.identity.entities.refresh_token import RefreshToken


class RefreshTokenRepository(Protocol):
    """Interface for RefreshToken aggregate persistence.

    Refresh tokens are a separate aggregate from User and Session,
    enabling independent token lifecycle and rotation.
    """

    async def save(self, token: RefreshToken) -> None:
        """Persist a new or updated refresh token.

        Args:
            token: RefreshToken aggregate to save.
        """
        ...

    async def get_by_id(self, token_id: str) -> RefreshToken | None:
        """Get a refresh token by its UUID.

        Args:
            token_id: UUID string.

        Returns:
            RefreshToken if found, None otherwise.
        """
        ...

    async def get_by_token_hash(self, token_hash: str) -> RefreshToken | None:
        """Get a refresh token by its SHA-256 hash.

        Used during token rotation — look up the existing token by its hash.

        Args:
            token_hash: SHA-256 hex digest of the raw token.

        Returns:
            RefreshToken if found, None otherwise.
        """
        ...

    async def list_active_by_user_id(self, user_id: str) -> list[RefreshToken]:
        """List active (non-revoked, non-expired) tokens for a user.

        Args:
            user_id: UUID string of the user.

        Returns:
            List of active RefreshToken aggregates.
        """
        ...

    async def revoke_by_user_id(self, user_id: str) -> int:
        """Revoke all active refresh tokens for a user.

        Used when password/PIN is changed or account is locked.

        Args:
            user_id: UUID string of the user.

        Returns:
            Number of revoked tokens.
        """
        ...

    async def revoke_by_session_id(self, session_id: str) -> int:
        """Revoke all tokens associated with a session.

        Used when a session is revoked.

        Args:
            session_id: UUID string of the session.

        Returns:
            Number of revoked tokens.
        """
        ...
