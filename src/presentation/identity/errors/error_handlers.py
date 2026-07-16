"""Error handlers for the Identity Engine.

Maps domain exceptions and application exceptions to standard HTTP
error responses. Registered with the FastAPI app on startup.

Usage:
    from src.presentation.identity.errors.error_handlers import (
        register_error_handlers,
    )

    app = FastAPI()
    register_error_handlers(app)
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.domain.identity.exceptions.domain_error import DomainError
from src.application.common.exceptions import ApplicationException


def register_error_handlers(app: FastAPI) -> None:
    """Register all identity engine error handlers with the FastAPI app.

    Args:
        app: The FastAPI application instance.
    """

    @app.exception_handler(DomainError)
    async def domain_error_handler(
        request: Request,
        exc: DomainError,
    ) -> JSONResponse:
        """Handle domain-level errors (pure business logic)."""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.code,
                "message": exc.message,
                "details": exc.details or {},
            },
        )

    @app.exception_handler(ApplicationException)
    async def application_error_handler(
        request: Request,
        exc: ApplicationException,
    ) -> JSONResponse:
        """Handle application-level errors (use case orchestration)."""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.code,
                "message": exc.message,
                "details": exc.details or {},
            },
        )

    @app.exception_handler(ValueError)
    async def validation_error_handler(
        request: Request,
        exc: ValueError,
    ) -> JSONResponse:
        """Handle general value/validation errors."""
        return JSONResponse(
            status_code=400,
            content={
                "error": "VALIDATION_ERROR",
                "message": str(exc),
                "details": {},
            },
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        """Catch-all handler for unexpected errors."""
        return JSONResponse(
            status_code=500,
            content={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred.",
                "details": {},
            },
        )
