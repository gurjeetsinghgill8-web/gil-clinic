"""Authentication API routes.

Endpoints:
    POST /api/v1/identity/auth/login/pin       -- PIN-based login
    POST /api/v1/identity/auth/login/password   -- Password-based login
    POST /api/v1/identity/auth/refresh          -- Token refresh (rotation)
    POST /api/v1/identity/auth/logout           -- Logout (revoke session)
    POST /api/v1/identity/auth/change-pin       -- Change PIN
    POST /api/v1/identity/auth/otp/request      -- Request OTP
    POST /api/v1/identity/auth/otp/verify       -- Verify OTP
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from src.presentation.identity.dependencies.get_current_user import (
    CurrentUser,
    get_current_user,
)
from src.presentation.identity.dependencies.use_case_dependencies import (
    get_auth_with_pin_use_case,
    get_auth_with_password_use_case,
    get_change_pin_use_case,
    get_logout_use_case,
    get_refresh_token_use_case,
    get_request_otp_use_case,
    get_verify_otp_use_case,
)
from src.presentation.identity.schemas.auth_schemas import (
    AuthenticateResponse,
    AuthenticateWithPasswordRequest,
    AuthenticateWithPinRequest,
    ChangePinRequest,
    ErrorResponse,
    LogoutRequest,
    LogoutResponse,
    PinChangedResponse,
    RefreshTokenRequest,
    TokenRefreshResponse,
)
from src.presentation.identity.schemas.otp_schemas import (
    OtpResponse,
    OtpVerifiedResponse,
    RequestOtpRequest,
    VerifyOtpRequest,
)

router = APIRouter(
    prefix="/api/v1/identity/auth",
    tags=["Identity - Authentication"],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        429: {"model": ErrorResponse, "description": "Too many attempts"},
    },
)


@router.post(
    "/login/pin",
    response_model=AuthenticateResponse,
    summary="PIN-based staff login",
)
async def login_with_pin(
    request: AuthenticateWithPinRequest,
    use_case=Depends(get_auth_with_pin_use_case),
) -> AuthenticateResponse:
    result = await use_case.execute(request)
    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result.message or "Authentication failed.",
        )
    return AuthenticateResponse(**result.data)


@router.post(
    "/login/password",
    response_model=AuthenticateResponse,
    summary="Password-based admin login",
)
async def login_with_password(
    request: AuthenticateWithPasswordRequest,
    use_case=Depends(get_auth_with_password_use_case),
) -> AuthenticateResponse:
    result = await use_case.execute(request)
    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result.message or "Authentication failed.",
        )
    return AuthenticateResponse(**result.data)


@router.post(
    "/refresh",
    response_model=TokenRefreshResponse,
    summary="Refresh access token",
)
async def refresh_token(
    request: RefreshTokenRequest,
    use_case=Depends(get_refresh_token_use_case),
) -> TokenRefreshResponse:
    result = await use_case.execute(request)
    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result.message or "Token refresh failed.",
        )
    return TokenRefreshResponse(**result.data)


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Logout user",
)
async def logout(
    request: LogoutRequest,
    use_case=Depends(get_logout_use_case),
) -> LogoutResponse:
    result = await use_case.execute(request)
    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.message or "Logout failed.",
        )
    return LogoutResponse(**result.data)


@router.post(
    "/change-pin",
    response_model=PinChangedResponse,
    summary="Change PIN",
)
async def change_pin(
    request: ChangePinRequest,
    use_case=Depends(get_change_pin_use_case),
) -> PinChangedResponse:
    result = await use_case.execute(request)
    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.message or "PIN change failed.",
        )
    return PinChangedResponse(**result.data)


@router.post(
    "/otp/request",
    response_model=OtpResponse,
    summary="Request OTP",
)
async def request_otp(
    request: RequestOtpRequest,
    use_case=Depends(get_request_otp_use_case),
) -> OtpResponse:
    result = await use_case.execute(request)
    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.message or "OTP request failed.",
        )
    return OtpResponse(**result.data)


@router.post(
    "/otp/verify",
    response_model=OtpVerifiedResponse,
    summary="Verify OTP",
)
async def verify_otp(
    request: VerifyOtpRequest,
    use_case=Depends(get_verify_otp_use_case),
) -> OtpVerifiedResponse:
    result = await use_case.execute(request)
    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.message or "OTP verification failed.",
        )
    return OtpVerifiedResponse(**result.data)


@router.get(
    "/me",
    summary="Get current user info",
)
async def get_current_user_info(
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    return {
        "user_id": current_user.user_id,
        "username": current_user.username,
        "role": current_user.role,
        "session_id": current_user.session_id,
    }
