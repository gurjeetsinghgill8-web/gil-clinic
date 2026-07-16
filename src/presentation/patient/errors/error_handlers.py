"""Error handlers for the Patient Engine.

Registers exception-to-HTTP-response mapping for patient-specific errors.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi import status

from src.application.common.exceptions import (
    ConflictError,
    NotFoundError,
    ValidationError,
)


def register_error_handlers(app) -> None:
    """Register patient-specific error handlers with the FastAPI app.

    Args:
        app: The FastAPI application instance.
    """

    @app.exception_handler(ConflictError)
    async def conflict_error_handler(
        request: Request, exc: ConflictError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": exc.message,
                "code": exc.code,
            },
        )

    @app.exception_handler(NotFoundError)
    async def not_found_error_handler(
        request: Request, exc: NotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "detail": exc.message,
                "code": exc.code,
            },
        )

    @app.exception_handler(ValidationError)
    async def validation_error_handler(
        request: Request, exc: ValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": exc.message,
                "code": exc.code,
                "details": exc.details,
            },
        )
