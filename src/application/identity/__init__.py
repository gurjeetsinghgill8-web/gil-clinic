"""Identity Engine - Application Layer (use cases, DTOs, CQRS).

Contains all orchestration logic for identity operations.
The domain layer contains ONLY business rules — everything else lives here.

Structure:
- use_cases/: Command handlers for each identity operation
- dtos/: Request/response data transfer objects
- interfaces/: Unit of Work and other application-level abstractions
"""

from src.application.identity.use_cases import (
    AuthenticateWithPinUseCase,
    AuthenticateWithPasswordUseCase,
    RefreshTokenUseCase,
    LogoutUseCase,
    RequestOtpUseCase,
    VerifyOtpUseCase,
    ChangePinUseCase,
    UnlockAccountUseCase,
    AssignRoleUseCase,
)
from src.application.identity.dtos import (
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
    AuthenticateResponse,
    TokenRefreshResponse,
    LogoutResponse,
    OtpResponse,
    OtpVerifiedResponse,
    PinChangedResponse,
    AccountUnlockedResponse,
    RoleAssignedResponse,
)
from src.application.identity.interfaces import IdentityUnitOfWork

__all__ = [
    # Use Cases
    "AuthenticateWithPinUseCase",
    "AuthenticateWithPasswordUseCase",
    "RefreshTokenUseCase",
    "LogoutUseCase",
    "RequestOtpUseCase",
    "VerifyOtpUseCase",
    "ChangePinUseCase",
    "UnlockAccountUseCase",
    "AssignRoleUseCase",
    # Request DTOs
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
    # Response DTOs
    "AuthenticateResponse",
    "TokenRefreshResponse",
    "LogoutResponse",
    "OtpResponse",
    "OtpVerifiedResponse",
    "PinChangedResponse",
    "AccountUnlockedResponse",
    "RoleAssignedResponse",
    # Interfaces
    "IdentityUnitOfWork",
]
