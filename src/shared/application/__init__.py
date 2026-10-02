"""Shared application layer — reusable use case infrastructure.

Provides:
- BaseUseCase: Abstract base for all use cases
- UnitOfWork: Transaction boundary abstraction
"""

from src.shared.application.base_use_case import BaseUseCase

__all__ = ["BaseUseCase"]
