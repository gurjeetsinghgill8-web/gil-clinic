"""Base use case with unit of work integration.

All use cases across all engines follow this pattern.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

TRequest = TypeVar("TRequest")
TResponse = TypeVar("TResponse")


class BaseUseCase(ABC, Generic[TRequest, TResponse]):
    """Abstract base class for all use cases.

    Each use case:
    - Receives a typed request DTO
    - Returns a typed response DTO
    - Raises DomainError for business rule violations
    - Operates within a unit of work transaction boundary
    """

    @abstractmethod
    def __call__(self, request: TRequest) -> TResponse:
        """Execute the use case.

        Args:
            request: Typed request DTO with validated input.

        Returns:
            Typed response DTO.

        Raises:
            DomainError: When business rules are violated.
        """
        ...
