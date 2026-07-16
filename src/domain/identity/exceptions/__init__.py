"""Domain exceptions: DomainError and Identity-specific errors."""

from src.domain.identity.exceptions.domain_error import (
    DomainError,
    InvalidPinFormatError,
    AccountLockedError,
    InvalidCredentialsError,
    OtpExpiredError,
    MaxOtpAttemptsError,
    UnauthorizedError,
    SessionExpiredError,
    UserNotFoundError,
    DuplicateUsernameError,
    RoleNotFoundError,
    CannotDeleteLastAdminError,
)

__all__ = [
    "DomainError",
    "InvalidPinFormatError",
    "AccountLockedError",
    "InvalidCredentialsError",
    "OtpExpiredError",
    "MaxOtpAttemptsError",
    "UnauthorizedError",
    "SessionExpiredError",
    "UserNotFoundError",
    "DuplicateUsernameError",
    "RoleNotFoundError",
    "CannotDeleteLastAdminError",
]
