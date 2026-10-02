"""Port: JWT token service interface.

Domain layer defines this protocol. Infrastructure provides JwtTokenService.
"""

from __future__ import annotations

from typing import Protocol


class TokenService(Protocol):
    """Interface for JWT access token creation and verification.

    Uses RS256 asymmetric signing.
    Access tokens expire after 24 hours.
    """

    def create_access_token(
        self,
        user_id: str,
        role: str,
        session_id: str,
    ) -> str:
        """Create a signed JWT access token.

        Args:
            user_id: UUID of the authenticated user.
            role: User's role code (e.g., "DOCTOR").
            session_id: UUID of the active session.

        Returns:
            Signed JWT string.
        """
        ...

    def decode(self, token: str) -> dict:
        """Decode and verify a JWT token.

        Args:
            token: JWT string to decode.

        Returns:
            Decoded payload dictionary.

        Raises:
            TokenError: If token is expired, malformed, or signature invalid.
        """
        ...

    def hash_token(self, token: str) -> str:
        """Hash a token for secure storage.

        Used for refresh tokens stored in the database.
        Uses SHA-256.

        Args:
            token: Raw token string.

        Returns:
            SHA-256 hex digest.
        """
        ...
