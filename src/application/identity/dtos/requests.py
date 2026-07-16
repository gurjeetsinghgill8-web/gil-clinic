"""Request DTOs for Identity Engine use cases.

Each DTO is a frozen dataclass representing the input to a use case.
DTOs are pure data carriers — no business logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# =============================================================================
# Authentication
# =============================================================================


@dataclass(frozen=True)
class AuthenticateWithPinRequest:
    """Input for PIN-based authentication.

    Attributes:
        username: Staff login username.
        pin: 4-6 digit numeric PIN.
        device_id: Optional device identifier.
        device_name: Optional device name.
        user_agent: Optional user agent string.
        ip_address: Optional IP address.
    """

    username: str
    pin: str
    device_id: str | None = None
    device_name: str | None = None
    user_agent: str | None = None
    ip_address: str | None = None


@dataclass(frozen=True)
class AuthenticateWithPasswordRequest:
    """Input for password-based authentication.

    Attributes:
        username: Admin username.
        password: Plaintext password.
        device_id: Optional device identifier.
        device_name: Optional device name.
        user_agent: Optional user agent string.
        ip_address: Optional IP address.
    """

    username: str
    password: str
    device_id: str | None = None
    device_name: str | None = None
    user_agent: str | None = None
    ip_address: str | None = None


@dataclass(frozen=True)
class RefreshTokenRequest:
    """Input for token rotation.

    Attributes:
        user_id: UUID of the token owner.
        refresh_token_hash: SHA-256 hash of current refresh token.
    """

    user_id: str
    refresh_token_hash: str


@dataclass(frozen=True)
class LogoutRequest:
    """Input for user logout.

    Attributes:
        user_id: UUID of the user.
        session_id: UUID of the session to revoke.
        revoke_all: If True, revoke ALL sessions.
    """

    user_id: str
    session_id: str
    revoke_all: bool = False


# =============================================================================
# OTP
# =============================================================================


@dataclass(frozen=True)
class RequestOtpRequest:
    """Input for requesting an OTP.

    Attributes:
        user_id: UUID of the user.
        purpose: Purpose of the OTP ("login", "pin_reset", "mfa").
    """

    user_id: str
    purpose: str = "login"


@dataclass(frozen=True)
class VerifyOtpRequest:
    """Input for verifying an OTP.

    Attributes:
        user_id: UUID of the user.
        otp: 6-digit OTP to verify.
        purpose: Purpose of the OTP.
    """

    user_id: str
    otp: str
    purpose: str = "login"


# =============================================================================
# Account Management
# =============================================================================


@dataclass(frozen=True)
class ChangePinRequest:
    """Input for changing a user's PIN.

    Attributes:
        user_id: UUID of the user.
        old_pin: Current PIN for verification.
        new_pin: New 4-6 digit PIN.
    """

    user_id: str
    old_pin: str
    new_pin: str


@dataclass(frozen=True)
class UnlockAccountRequest:
    """Input for unlocking a locked account.

    Attributes:
        user_id: UUID of the locked user.
        unlocked_by: Who is unlocking ("admin" or "system").
    """

    user_id: str
    unlocked_by: str = "admin"


# =============================================================================
# Role Management
# =============================================================================


@dataclass(frozen=True)
class AssignRoleRequest:
    """Input for assigning a role to a user.

    Attributes:
        actor_user_id: UUID of the admin performing the action.
        target_user_id: UUID of the user receiving the role.
        role_code: New role code to assign.
    """

    actor_user_id: str
    target_user_id: str
    role_code: str


@dataclass(frozen=True)
class RevokeRoleRequest:
    """Input for removing a role from a user.

    Attributes:
        actor_user_id: UUID of the admin performing the action.
        target_user_id: UUID of the user losing the role.
        role_code: Role code to remove.
    """

    actor_user_id: str
    target_user_id: str
    role_code: str
