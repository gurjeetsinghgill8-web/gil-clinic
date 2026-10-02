"""Domain exceptions for the Identity Engine.

All IDENTITY_* error codes from the error catalog (020_ERROR_CATALOG.md).
"""

from __future__ import annotations


class DomainError(Exception):
    """Base exception for all domain-level errors.

    Every domain error has:
    - code: Machine-readable error code (e.g., "IDENTITY_001")
    - message: Human-readable error description
    - status_code: HTTP status code for API responses
    - details: Optional extra context
    """

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict:
        """Convert to API-friendly error dict."""
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }


# =============================================================================
# Identity-Specific Errors
# =============================================================================

class InvalidPinFormatError(DomainError):
    """PIN must be 4-6 numeric digits."""

    def __init__(self, details: dict | None = None) -> None:
        super().__init__(
            code="IDENTITY_001",
            message="PIN must be 4-6 numeric digits. PIN 4-6 digits ka hona chahiye.",
            status_code=400,
            details=details,
        )


class AccountLockedError(DomainError):
    """Account locked due to too many failed attempts."""

    def __init__(self, locked_until: str, details: dict | None = None) -> None:
        super().__init__(
            code="IDENTITY_002",
            message=f"Account locked until {locked_until}. 5 failures ke baad 30 min lock.",
            status_code=423,
            details={"locked_until": locked_until, **(details or {})},
        )


class InvalidCredentialsError(DomainError):
    """Invalid PIN, password, or OTP."""

    def __init__(self, details: dict | None = None) -> None:
        super().__init__(
            code="IDENTITY_003",
            message="Invalid credentials. Galat PIN/password.",
            status_code=401,
            details=details,
        )


class OtpExpiredError(DomainError):
    """OTP has expired (5 minute window)."""

    def __init__(self, details: dict | None = None) -> None:
        super().__init__(
            code="IDENTITY_004",
            message="OTP has expired. Please request a new one. OTP expire ho gaya. Naya request karein.",
            status_code=410,
            details=details,
        )


class MaxOtpAttemptsError(DomainError):
    """Maximum OTP verification attempts reached."""

    def __init__(self, details: dict | None = None) -> None:
        super().__init__(
            code="IDENTITY_005",
            message="Maximum OTP attempts reached. Try again after 30 minutes.",
            status_code=429,
            details=details,
        )


class UnauthorizedError(DomainError):
    """User lacks permission for this action."""

    def __init__(self, details: dict | None = None) -> None:
        super().__init__(
            code="IDENTITY_006",
            message="You do not have permission for this action. Aapke paas permission nahi hai.",
            status_code=403,
            details=details,
        )


class SessionExpiredError(DomainError):
    """JWT or session has expired."""

    def __init__(self, details: dict | None = None) -> None:
        super().__init__(
            code="IDENTITY_007",
            message="Session has expired. Please login again. Session expire ho gaya. Phir login karein.",
            status_code=401,
            details=details,
        )


class UserNotFoundError(DomainError):
    """User with given identifier not found."""

    def __init__(self, details: dict | None = None) -> None:
        super().__init__(
            code="IDENTITY_008",
            message="User not found. User nahi mila.",
            status_code=404,
            details=details,
        )


class DuplicateUsernameError(DomainError):
    """Username already exists in the system."""

    def __init__(self, details: dict | None = None) -> None:
        super().__init__(
            code="IDENTITY_009",
            message="Username already exists. Yeh username pehle se hai.",
            status_code=409,
            details=details,
        )


class RoleNotFoundError(DomainError):
    """Role code does not exist."""

    def __init__(self, details: dict | None = None) -> None:
        super().__init__(
            code="IDENTITY_010",
            message="Role does not exist. Yeh role exist nahi karta.",
            status_code=404,
            details=details,
        )


class CannotDeleteLastAdminError(DomainError):
    """Cannot delete the last active admin user."""

    def __init__(self, details: dict | None = None) -> None:
        super().__init__(
            code="IDENTITY_011",
            message="Cannot delete the last admin user. Last admin delete nahi kar sakte.",
            status_code=403,
            details=details,
        )
