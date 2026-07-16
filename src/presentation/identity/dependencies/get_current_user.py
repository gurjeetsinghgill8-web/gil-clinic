"""Dependency: extract and validate current user from JWT.

Provides FastAPI dependencies for authenticating requests via JWT
and extracting the current user's identity and permissions.

Development bypass: set GHOS_DEV_AUTH_BYPASS=true to skip JWT validation.
"""

from __future__ import annotations

import os

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.infrastructure.identity.services.jwt_token_service import (
    JwtTokenService,
)

security_scheme = HTTPBearer(
    scheme_name="Bearer",
    description="JWT access token obtained from /api/v1/identity/auth/login",
    auto_error=False,
)


class CurrentUser:
    """Represents the authenticated user extracted from JWT.

    This is injected into route handlers via Depends(get_current_user).
    """

    def __init__(
        self,
        user_id: str,
        username: str,
        role: str,
        session_id: str,
    ) -> None:
        self.user_id = user_id
        self.username = username
        self.role = role
        self.session_id = session_id

    def has_role(self, *roles: str) -> bool:
        """Check if user has one of the specified roles."""
        return self.role in roles

    def __repr__(self) -> str:
        return f"CurrentUser({self.username}, {self.role})"


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> CurrentUser:
    """Extract and validate the current user from a JWT token.

    If GHOS_DEV_AUTH_BYPASS=true, skip JWT validation and return a dummy admin user.

    Args:
        credentials: Bearer token from the Authorization header.

    Returns:
        CurrentUser with user_id, username, role, session_id.

    Raises:
        HTTPException 401: If token is missing, expired, or invalid.
    """
    # Dev bypass: skip JWT validation
    if os.getenv("GHOS_DEV_AUTH_BYPASS", "").lower() in ("true", "1", "yes"):
        return CurrentUser(
            user_id="dev-user",
            username="dev-admin",
            role="ADMIN",
            session_id="dev-session",
        )

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing.",
        )

    token = credentials.credentials
    token_service = JwtTokenService()

    try:
        payload = token_service.decode(token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user_id = payload.get("sub")
    role = payload.get("role")
    session_id = payload.get("sid")

    if not user_id or not role or not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing required claims.",
        )

    return CurrentUser(
        user_id=user_id,
        username=payload.get("username", ""),
        role=role,
        session_id=session_id,
    )


def require_role(*roles: str) -> callable:
    """Dependency factory: require specific role(s) for an endpoint.

    Usage:
        @router.get("/admin-only")
        async def admin_endpoint(
            user: CurrentUser = Depends(require_role("ADMIN")),
        ):
            ...
    """

    async def _role_checker(
        user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        if not user.has_role(*roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {', '.join(roles)}",
            )
        return user

    return _role_checker
