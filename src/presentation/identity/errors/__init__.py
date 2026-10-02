"""Error handlers: map DomainError to HTTP responses."""

from src.presentation.identity.errors.error_handlers import register_error_handlers

__all__ = [
    "register_error_handlers",
]
