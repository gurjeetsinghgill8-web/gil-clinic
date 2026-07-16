"""Result type for use case responses.

Provides a consistent success/failure pattern across all engines.
Inspired by Rust's Ok/Error pattern — no exceptions for control flow.

Usage:
    result = Result.ok(data={"user_id": "..."})
    if result.is_ok:
        return result.value
    else:
        logger.error(result.error)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

T = TypeVar("T")
E = TypeVar("E")


@dataclass(frozen=True)
class Result(Generic[T, E]):
    """Immutable result type representing success or failure.

    Attributes:
        data: The success value (None if error).
        error: The error value (None if success).
        code: Optional machine-readable code for error cases.
        message: Optional human-readable message.
        metadata: Optional dict for pagination, tracing, etc.
    """

    data: T | None = None
    error: str | None = None
    code: str | None = None
    message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Constructors
    # ------------------------------------------------------------------

    @classmethod
    def ok(
        cls,
        data: T | None = None,
        message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Result[T, None]:
        """Create a successful result.

        Args:
            data: Response payload.
            message: Optional success message.
            metadata: Optional metadata (pagination, etc.).

        Returns:
            Result with is_ok = True.
        """
        return cls(
            data=data,
            message=message,
            metadata=metadata or {},
        )

    @classmethod
    def fail(
        cls,
        error: str,
        code: str | None = None,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> Result[None, str]:
        """Create a failure result.

        Args:
            error: Machine-readable error description.
            code: Optional error code (e.g., "IDENTITY_003").
            message: Optional user-facing message.
            details: Optional error details dict.

        Returns:
            Result with is_ok = False.
        """
        return cls(
            data=details,
            error=error,
            code=code,
            message=message,
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_ok(self) -> bool:
        """Check if the result is success."""
        return self.error is None

    @property
    def is_fail(self) -> bool:
        """Check if the result is failure."""
        return self.error is not None

    @property
    def value(self) -> T:
        """Get the success value.

        Raises:
            ValueError: If result is not success.
        """
        if self.is_fail:
            msg = self.error or "Result is not ok"
            raise ValueError(f"Cannot get value from failed result: {msg}")
        return self.data

    def unwrap_or(self, default: T) -> T:
        """Get value or default if error.

        Args:
            default: Fallback value.

        Returns:
            Data if ok, default otherwise.
        """
        return self.data if self.is_ok else default

    def map(self, fn) -> Result:
        """Transform the success value.

        Args:
            fn: Transform function for success data.

        Returns:
            New Result with transformed data.
        """
        if self.is_ok:
            return Result.ok(data=fn(self.data), message=self.message)
        return self

    def __bool__(self) -> bool:
        return self.is_ok

    def __repr__(self) -> str:
        if self.is_ok:
            return f"<Result OK data={self.data!r}>"
        return f"<Result FAIL code={self.code} error={self.error!r}>"
