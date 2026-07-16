"""Base use case — abstract foundation for all engine use cases.

Every use case in GHOS follows this pattern:
1. Validate input
2. Authorize caller
3. Load aggregates
4. Execute domain logic
5. Collect events
6. Commit via Unit of Work
7. Publish events
8. Return Result

This base class provides the skeleton with audit hooks and event collection.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from src.application.common.command import Command
from src.application.common.result import Result


class BaseUseCase(ABC):
    """Abstract base for all use cases in GHOS.

    Subclasses implement execute() with the business logic.
    The framework handles validation, authorization, and commit boundaries.

    Attributes:
        _events: Collected domain events published after commit.
        _audit: Optional audit trail entries.
    """

    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []
        self._audit: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run(self, command: Command) -> Result:
        """Execute the use case with full lifecycle.

        Template method:
        1. Authorize the caller
        2. Validate input
        3. Execute domain logic
        4. Commit
        5. Publish events
        6. Audit

        Args:
            command: Input command with business data.

        Returns:
            Result with success data or failure error.
        """
        try:
            # 1. Pre-execution hooks
            await self._pre_execute(command)

            # 2. Business logic
            result = await self.execute(command)

            # 3. Post-execution hooks
            if result.is_ok:
                await self._post_execute(command, result)

            return result

        except Exception as exc:
            return self._handle_error(exc)

    # ------------------------------------------------------------------
    # Subclasses implement this
    # ------------------------------------------------------------------

    @abstractmethod
    async def execute(self, command: Command) -> Result:
        """Execute the use case business logic.

        Args:
            command: Input command.

        Returns:
            Result with data or error.
        """
        ...

    # ------------------------------------------------------------------
    # Hooks (override in subclasses as needed)
    # ------------------------------------------------------------------

    async def authorize(self, command: Command) -> None:
        """Check if the caller is authorized.

        Override this in use cases that need authorization.
        Raise ForbiddenError if not authorized.

        Args:
            command: Input command with caller context.
        """
        ...

    async def validate(self, command: Command) -> None:
        """Validate input before execution.

        Override this in use cases that need input validation.
        Raise ValidationError if invalid.

        Args:
            command: Input command to validate.
        """
        ...

    def collect_event(self, event: dict[str, Any]) -> None:
        """Collect a domain event for publishing after commit.

        Args:
            event: Domain event dict (CloudEvents format).
        """
        self._events.append(event)

    def collect_audit(self, entry: dict[str, Any]) -> None:
        """Collect an audit trail entry.

        Args:
            entry: Audit record dict.
        """
        self._audit.append(entry)

    # ------------------------------------------------------------------
    # Internal lifecycle
    # ------------------------------------------------------------------

    async def _pre_execute(self, command: Command) -> None:
        """Run pre-execution hooks.

        Order: authorize → validate
        """
        await self.authorize(command)
        await self.validate(command)

    async def _post_execute(self, command: Command, result: Result) -> None:
        """Run post-execution hooks.

        Override in subclasses for:
        - Event publishing
        - Audit logging
        - Notification dispatch
        """
        pass

    def _handle_error(self, exc: Exception) -> Result:
        """Convert exception to Result.

        Args:
            exc: The caught exception.

        Returns:
            Result with error information.
        """
        from src.application.common.exceptions import ApplicationException

        if isinstance(exc, ApplicationException):
            return Result.fail(
                error=str(exc),
                code=exc.code,
                details=exc.details,
            )
        # Unexpected errors — log and return generic
        return Result.fail(
            error="Internal error",
            code="APP_500",
        )
