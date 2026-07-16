"""User management API routes.

Endpoints:
    POST   /api/v1/identity/users               -- Create user
    GET    /api/v1/identity/users                -- List users
    GET    /api/v1/identity/users/{user_id}      -- Get user by ID
    PATCH  /api/v1/identity/users/{user_id}      -- Update user
    DELETE /api/v1/identity/users/{user_id}      -- Deactivate user
    POST   /api/v1/identity/users/assign-role    -- Assign role
    POST   /api/v1/identity/users/unlock         -- Unlock account
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from src.presentation.identity.dependencies.get_current_user import (
    CurrentUser,
    get_current_user,
    require_role,
)
from src.presentation.identity.dependencies.use_case_dependencies import (
    get_assign_role_use_case,
    get_unlock_account_use_case,
    get_user_repository,
)
from src.presentation.identity.schemas.auth_schemas import ErrorResponse
from src.presentation.identity.schemas.user_schemas import (
    AccountUnlockedResponse,
    AssignRoleRequest,
    CreateUserRequest,
    RoleAssignedResponse,
    UnlockAccountRequest,
    UserResponse,
)

router = APIRouter(
    prefix="/api/v1/identity/users",
    tags=["Identity - Users"],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        404: {"model": ErrorResponse, "description": "Not found"},
        409: {"model": ErrorResponse, "description": "Conflict"},
    },
)


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new staff user",
)
async def create_user(
    request: CreateUserRequest,
    user_repo=Depends(get_user_repository),
    current_user: CurrentUser = Depends(require_role("ADMIN")),
) -> UserResponse:
    exists = await user_repo.exists_by_username(request.username)
    if exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{request.username}' already exists.",
        )
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Create user use case not yet implemented.",
    )


@router.get(
    "",
    response_model=dict,
    summary="List all active users",
)
async def list_users(
    user_repo=Depends(get_user_repository),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    users = await user_repo.list_active()
    return {
        "users": [
            {
                "id": str(u.id),
                "username": u.username,
                "full_name": u.full_name,
                "role_code": u.role_code,
                "department": u.department,
                "is_active": u.is_active,
            }
            for u in users
        ],
        "total": len(users),
    }


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get user by ID",
)
async def get_user(
    user_id: str,
    user_repo=Depends(get_user_repository),
    current_user: CurrentUser = Depends(get_current_user),
) -> UserResponse:
    user = await user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{user_id}' not found.",
        )
    return UserResponse(
        id=str(user.id),
        username=user.username,
        full_name=user.full_name,
        role_code=user.role_code,
        department=user.department,
        phone=user.phone,
        email=user.email,
        is_active=user.is_active,
        is_locked=user.is_locked,
        last_login=user.last_login,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.post(
    "/assign-role",
    response_model=RoleAssignedResponse,
    summary="Assign role to user",
)
async def assign_role(
    request: AssignRoleRequest,
    use_case=Depends(get_assign_role_use_case),
    current_user: CurrentUser = Depends(get_current_user),
) -> RoleAssignedResponse:
    result = await use_case.execute(request)
    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.message or "Role assignment failed.",
        )
    return RoleAssignedResponse(**result.data)


@router.post(
    "/unlock",
    response_model=AccountUnlockedResponse,
    summary="Unlock a locked account",
)
async def unlock_account(
    request: UnlockAccountRequest,
    use_case=Depends(get_unlock_account_use_case),
    current_user: CurrentUser = Depends(require_role("ADMIN")),
) -> AccountUnlockedResponse:
    result = await use_case.execute(request)
    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.message or "Unlock failed.",
        )
    return AccountUnlockedResponse(**result.data)
