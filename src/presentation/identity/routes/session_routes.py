"""Session management API routes.

Endpoints:
    GET  /api/v1/identity/sessions/me          -- Get current session
    GET  /api/v1/identity/sessions/user/{user_id}  -- Get user's sessions
    POST /api/v1/identity/sessions/revoke      -- Revoke a session
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from src.presentation.identity.dependencies.get_current_user import (
    CurrentUser,
    get_current_user,
    require_role,
)
from src.presentation.identity.dependencies.use_case_dependencies import (
    get_session_repository,
)
from src.presentation.identity.schemas.session_schemas import (
    RevokeSessionRequest,
    SessionListResponse,
    SessionResponse,
)

router = APIRouter(
    prefix="/api/v1/identity/sessions",
    tags=["Identity - Sessions"],
)


@router.get(
    "/me",
    response_model=SessionResponse,
    summary="Get current session info",
)
async def get_current_session(
    session_repo=Depends(get_session_repository),
    current_user: CurrentUser = Depends(get_current_user),
) -> SessionResponse:
    session = await session_repo.get_by_id(current_user.session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found.",
        )
    return SessionResponse(
        id=str(session.id),
        user_id=str(session.user_id),
        device_id=session.device_id,
        device_name=session.device_name,
        user_agent=session.user_agent,
        ip_address=session.ip_address,
        last_activity=session.last_activity,
        is_trusted=session.is_trusted,
        is_active=session.is_active,
        created_at=session.created_at,
        expires_at=session.expires_at,
    )


@router.get(
    "/user/{user_id}",
    response_model=SessionListResponse,
    summary="List all sessions for a user",
)
async def list_user_sessions(
    user_id: str,
    session_repo=Depends(get_session_repository),
    current_user: CurrentUser = Depends(require_role("ADMIN")),
) -> SessionListResponse:
    sessions = await session_repo.list_by_user_id(user_id)
    return SessionListResponse(
        sessions=[
            SessionResponse(
                id=str(s.id),
                user_id=str(s.user_id),
                device_id=s.device_id,
                device_name=s.device_name,
                user_agent=s.user_agent,
                ip_address=s.ip_address,
                last_activity=s.last_activity,
                is_trusted=s.is_trusted,
                is_active=s.is_active,
                created_at=s.created_at,
                expires_at=s.expires_at,
            )
            for s in sessions
        ],
        total=len(sessions),
    )


@router.post(
    "/revoke",
    summary="Revoke a specific session",
)
async def revoke_session(
    request: RevokeSessionRequest,
    session_repo=Depends(get_session_repository),
    current_user: CurrentUser = Depends(require_role("ADMIN")),
) -> dict:
    await session_repo.revoke_session(request.session_id)
    return {"message": "Session revoked successfully."}
