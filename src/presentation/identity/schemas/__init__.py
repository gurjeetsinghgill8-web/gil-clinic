"""Pydantic V2 request/response schemas for Identity Engine."""

from src.presentation.identity.schemas.auth_schemas import (
    AuthenticateWithPinRequest,
    AuthenticateWithPasswordRequest,
    AuthenticateResponse,
    RefreshTokenRequest,
    TokenRefreshResponse,
    LogoutRequest,
    LogoutResponse,
    ChangePinRequest,
    PinChangedResponse,
)
from src.presentation.identity.schemas.user_schemas import (
    CreateUserRequest,
    UserResponse,
    AssignRoleRequest,
    RoleAssignedResponse,
    UnlockAccountRequest,
    AccountUnlockedResponse,
)
from src.presentation.identity.schemas.otp_schemas import (
    RequestOtpRequest,
    OtpResponse,
    VerifyOtpRequest,
    OtpVerifiedResponse,
)

__all__ = [
    # Auth
    "AuthenticateWithPinRequest",
    "AuthenticateWithPasswordRequest",
    "AuthenticateResponse",
    "RefreshTokenRequest",
    "TokenRefreshResponse",
    "LogoutRequest",
    "LogoutResponse",
    "ChangePinRequest",
    "PinChangedResponse",
    # Users
    "CreateUserRequest",
    "UserResponse",
    "AssignRoleRequest",
    "RoleAssignedResponse",
    "UnlockAccountRequest",
    "AccountUnlockedResponse",
    # OTP
    "RequestOtpRequest",
    "OtpResponse",
    "VerifyOtpRequest",
    "OtpVerifiedResponse",
]
