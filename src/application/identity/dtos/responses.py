"""Response DTOs for Identity Engine use cases.

Each DTO is a frozen dataclass representing the output of a use case.
DTOs are pure data carriers — no business logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# =============================================================================
# Authentication
# =============================================================================


@dataclass(frozen=True)
class AuthenticateResponse:
    """Response for successful authentication.

    Attributes:
        access_token: JWT access token string.
        refresh_token: Raw refresh token string (for rotation).
        session_id: UUID of the created session.
        user_id: UUID of the authenticated user.
        username: Username of the authenticated user.
        role: Role code of the authenticated user.
    """

    access_token: str
    refresh_token: str
    session_id: str
    user_id: str
    username: str
    role: str


@dataclass(frozen=True)
class TokenRefreshResponse:
    """Response for successful token refresh.

    Attributes:
        access_token: New JWT access token.
        refresh_token: New raw refresh token.
    """

    access_token: str
    refresh_token: str


@dataclass(frozen=True)
class LogoutResponse:
    """Response for logout.

    Attributes:
        message: Confirmation message.
        sessions_revoked: Number of sessions revoked.
    """

    message: str = "Logged out successfully"
    sessions_revoked: int = 1


# =============================================================================
# OTP
# =============================================================================


@dataclass(frozen=True)
class OtpResponse:
    """Response for OTP operations.

    Attributes:
        message: Status message.
        otp: The OTP (only returned in dev/test; in production sent via SMS/email).
    """

    message: str
    otp: str | None = None


@dataclass(frozen=True)
class OtpVerifiedResponse:
    """Response for OTP verification.

    Attributes:
        verified: Whether the OTP was verified.
        message: Status message.
    """

    verified: bool = True
    message: str = "OTP verified successfully"


# =============================================================================
# Account Management
# =============================================================================


@dataclass(frozen=True)
class PinChangedResponse:
    """Response for PIN change.

    Attributes:
        message: Confirmation message.
        sessions_revoked: Number of other sessions revoked.
    """

    message: str = "PIN changed successfully"
    sessions_revoked: int = 0


@dataclass(frozen=True)
class AccountUnlockedResponse:
    """Response for account unlock.

    Attributes:
        user_id: UUID of the unlocked user.
        message: Confirmation message.
    """

    user_id: str
    message: str = "Account unlocked successfully"


# =============================================================================
# Role Management
# =============================================================================


@dataclass(frozen=True)
class RoleAssignedResponse:
    """Response for role assignment.

    Attributes:
        user_id: UUID of the user.
        new_role: New role code.
        message: Confirmation message.
        old_role: Previous role code.
    """

    user_id: str
    new_role: str
    message: str = "Role assigned successfully"
    old_role: str | None = None
