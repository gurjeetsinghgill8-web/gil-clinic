"""Authentication request/response schemas.

Pydantic v2 models for the authentication API surface.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ------------------------------------------------------------------
# PIN Authentication
# ------------------------------------------------------------------

class AuthenticateWithPinRequest(BaseModel):
    """Request body for PIN-based login."""

    username: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Staff username.",
        examples=["receptionist", "dr.sharma"],
    )
    pin: str = Field(
        ...,
        min_length=4,
        max_length=6,
        description="4-6 digit numeric PIN.",
        examples=["1234"],
    )
    device_id: str | None = Field(default=None)
    device_name: str | None = Field(default=None)
    user_agent: str | None = Field(default=None)
    ip_address: str | None = Field(default=None)


class AuthenticateWithPasswordRequest(BaseModel):
    """Request body for password-based login (admin only)."""

    username: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Admin username.",
        examples=["admin"],
    )
    password: str = Field(
        ...,
        min_length=1,
        description="Admin password.",
    )
    device_id: str | None = Field(default=None)
    device_name: str | None = Field(default=None)
    user_agent: str | None = Field(default=None)
    ip_address: str | None = Field(default=None)


class AuthenticateResponse(BaseModel):
    """Response body for successful authentication."""

    access_token: str = Field(...)
    refresh_token: str = Field(...)
    session_id: str = Field(...)
    user_id: str = Field(...)
    username: str = Field(...)
    role: str = Field(...)


# ------------------------------------------------------------------
# Token Refresh
# ------------------------------------------------------------------

class RefreshTokenRequest(BaseModel):
    """Request body for token refresh (rotation)."""

    user_id: str = Field(...)
    refresh_token: str = Field(...)


class TokenRefreshResponse(BaseModel):
    """Response body for token refresh."""

    access_token: str = Field(...)
    refresh_token: str = Field(...)


# ------------------------------------------------------------------
# Logout
# ------------------------------------------------------------------

class LogoutRequest(BaseModel):
    """Request body for logout."""

    user_id: str = Field(...)
    session_id: str | None = Field(default=None)
    revoke_all: bool = Field(default=False)


class LogoutResponse(BaseModel):
    """Response body for logout."""

    message: str = Field(default="Logged out successfully.")
    sessions_revoked: int = Field(default=1)


# ------------------------------------------------------------------
# PIN Change
# ------------------------------------------------------------------

class ChangePinRequest(BaseModel):
    """Request body for PIN change."""

    user_id: str = Field(...)
    old_pin: str = Field(..., min_length=4, max_length=6)
    new_pin: str = Field(..., min_length=4, max_length=6)


class PinChangedResponse(BaseModel):
    """Response body for PIN change."""

    message: str = Field(default="PIN changed successfully.")
    sessions_revoked: int = Field(default=0)


# ------------------------------------------------------------------
# Error Response
# ------------------------------------------------------------------

class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str = Field(...)
    code: str = Field(...)
    message: str = Field(...)
    details: dict | None = Field(default=None)
