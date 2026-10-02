"""Session management request/response schemas.

Pydantic v2 models for session listing and revocation.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SessionResponse(BaseModel):
    """Response body for session queries."""

    id: str = Field(...)
    user_id: str = Field(...)
    device_id: str | None = Field(default=None)
    device_name: str | None = Field(default=None)
    user_agent: str | None = Field(default=None)
    ip_address: str | None = Field(default=None)
    last_activity: datetime | None = Field(default=None)
    is_trusted: bool = Field(default=False)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(...)
    expires_at: datetime | None = Field(default=None)


class SessionListResponse(BaseModel):
    """Response body for listing sessions."""

    sessions: list[SessionResponse] = Field(...)
    total: int = Field(...)


class RevokeSessionRequest(BaseModel):
    """Request body for revoking a specific session."""

    user_id: str = Field(...)
    session_id: str = Field(...)
