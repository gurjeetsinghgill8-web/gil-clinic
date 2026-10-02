"""Application-level exceptions.

These are used for errors that cross the use case boundary:
- Validation failures
- Authorization failures
- Not found errors
- Conflict errors

ApplicationExceptions are caught by the framework layer and mapped to HTTP responses.
DomainError classes (from domain layer) are NEVER used directly in application layer —
they are caught and wrapped into ApplicationException with Result codes.
"""

from __future__ import annotations


class ApplicationException(Exception):
    """Base exception for all application-layer errors.

    Attributes:
        message: Human-readable error description.
        code: Machine-readable error code.
        status_code: HTTP status code for API responses.
        details: Optional extra context.
    """

    def __init__(
        self,
        message: str = "Application error",
        code: str = "APP_000",
        status_code: int = 400,
        details: dict | None = None,
    ) -> None:
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class ValidationError(ApplicationException):
    """Input validation failure."""

    def __init__(
        self,
        message: str = "Validation failed",
        details: dict | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="APP_001",
            status_code=422,
            details=details,
        )


class NotFoundError(ApplicationException):
    """Resource not found."""

    def __init__(
        self,
        message: str = "Resource not found",
        details: dict | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="APP_002",
            status_code=404,
            details=details,
        )


class ConflictError(ApplicationException):
    """Resource conflict (e.g., duplicate username)."""

    def __init__(
        self,
        message: str = "Resource already exists",
        details: dict | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="APP_003",
            status_code=409,
            details=details,
        )


class UnauthorizedError(ApplicationException):
    """Caller not authenticated or insufficient permissions."""

    def __init__(
        self,
        message: str = "Unauthorized",
        details: dict | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="APP_004",
            status_code=401,
            details=details,
        )


class ForbiddenError(ApplicationException):
    """Caller authenticated but lacks required role/permission."""

    def __init__(
        self,
        message: str = "Forbidden",
        details: dict | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="APP_005",
            status_code=403,
            details=details,
        )


class InternalError(ApplicationException):
    """Unexpected internal error."""

    def __init__(
        self,
        message: str = "Internal error",
        details: dict | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="APP_500",
            status_code=500,
            details=details,
        )
