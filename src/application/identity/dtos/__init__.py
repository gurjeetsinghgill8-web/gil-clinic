"""Data Transfer Objects: requests, responses."""

from src.application.identity.dtos.requests import (
    AuthenticateWithPinRequest,
    AuthenticateWithPasswordRequest,
    RefreshTokenRequest,
    LogoutRequest,
    RequestOtpRequest,
    VerifyOtpRequest,
    ChangePinRequest,
    UnlockAccountRequest,
    AssignRoleRequest,
    RevokeRoleRequest,
)
from src.application.identity.dtos.responses import (
    AuthenticateResponse,
    TokenRefreshResponse,
    LogoutResponse,
    OtpResponse,
    OtpVerifiedResponse,
    PinChangedResponse,
    AccountUnlockedResponse,
    RoleAssignedResponse,
)

__all__ = [
    "AuthenticateWithPinRequest",
    "AuthenticateWithPasswordRequest",
    "RefreshTokenRequest",
    "LogoutRequest",
    "RequestOtpRequest",
    "VerifyOtpRequest",
    "ChangePinRequest",
    "UnlockAccountRequest",
    "AssignRoleRequest",
    "RevokeRoleRequest",
    "AuthenticateResponse",
    "TokenRefreshResponse",
    "LogoutResponse",
    "OtpResponse",
    "OtpVerifiedResponse",
    "PinChangedResponse",
    "AccountUnlockedResponse",
    "RoleAssignedResponse",
]
