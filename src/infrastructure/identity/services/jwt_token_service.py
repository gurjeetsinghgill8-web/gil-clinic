"""JWT token service implementation.

Implements the TokenService port protocol from the domain layer.
Supports RS256 (asymmetric) with HS256 fallback.
Uses PyJWT for signing and verification.

Usage:
    service = JwtTokenService()
    token = service.create_access_token(user_id, "DOCTOR", session_id)
    payload = service.decode(token)
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import jwt as pyjwt

from src.infrastructure.identity.config.settings import settings


class JwtTokenService:
    """JWT access token service with RS256/HS256 support.

    Implements the TokenService protocol from domain.identity.ports.
    Uses RS256 when RSA keys are configured, falls back to HS256.

    Thread-safe and stateless.
    """

    def __init__(self) -> None:
        self._private_key = settings.JWT_PRIVATE_KEY
        self._public_key = settings.JWT_PUBLIC_KEY
        self._secret = settings.JWT_SECRET
        self._algorithm = settings.JWT_ALGORITHM
        self._expire_minutes = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        self._use_rsa = bool(self._private_key and self._public_key)

        # Fall back to HS256 if no RSA keys configured
        if self._use_rsa:
            self._algorithm = "RS256"
        else:
            self._algorithm = "HS256"

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
        now = datetime.now(timezone.utc)
        payload = {
            "sub": user_id,
            "role": role,
            "sid": session_id,
            "iat": now,
            "exp": now + timedelta(minutes=self._expire_minutes),
            "iss": "ghos-identity",
            "type": "access",
        }

        if self._use_rsa:
            token: str = pyjwt.encode(
                payload,
                self._private_key,
                algorithm=self._algorithm,
            )
        else:
            token = pyjwt.encode(
                payload,
                self._secret,
                algorithm=self._algorithm,
            )

        return token

    def decode(self, token: str) -> dict:
        """Decode and verify a JWT token.

        Args:
            token: JWT string to decode.

        Returns:
            Decoded payload dictionary.

        Raises:
            jwt.ExpiredSignatureError: If token has expired.
            jwt.InvalidTokenError: If token is malformed or signature invalid.
        """
        if self._use_rsa:
            payload: dict = pyjwt.decode(
                token,
                self._public_key,
                algorithms=[self._algorithm],
                issuer="ghos-identity",
                options={"require": ["sub", "role", "sid", "exp"]},
            )
        else:
            payload = pyjwt.decode(
                token,
                self._secret,
                algorithms=[self._algorithm],
                issuer="ghos-identity",
                options={"require": ["sub", "role", "sid", "exp"]},
            )

        return payload

    def hash_token(self, token: str) -> str:
        """Hash a token for secure storage using SHA-256.

        Used for refresh tokens stored in the database — never store
        raw tokens, only their hashes.

        Args:
            token: Raw token string.

        Returns:
            SHA-256 hex digest.
        """
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
