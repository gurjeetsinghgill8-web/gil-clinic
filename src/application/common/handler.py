"""Command and Query handler interfaces.

Handlers encapsulate the execution logic for a single use case.
Each handler implements exactly one Command or Query.
"""

from __future__ import annotations

from typing import Any, Protocol

from src.application.common.command import Command, Query
from src.application.common.result import Result


class CommandHandler(Protocol):
    """Interface for command handlers.

    A command handler:
    1. Validates input
    2. Authorizes the caller
    3. Loads aggregates from repository
    4. Executes domain logic
    5. Collects domain events
    6. Commits via Unit of Work
    7. Publishes events
    8. Returns Result
    """

    async def handle(self, command: Command) -> Result:
        """Execute the command.

        Args:
            command: Input command with business data.

        Returns:
            Result with success data or failure error.
        """
        ...


class QueryHandler(Protocol):
    """Interface for query handlers.

    A query handler:
    1. Validates query parameters
    2. Authorizes the caller
    3. Loads data from repository
    4. Returns Result

    Queries never mutate state.
    """

    async def handle(self, query: Query) -> Result:
        """Execute the query.

        Args:
            query: Input query with filter/pagination data.

        Returns:
            Result with response data or failure error.
        """
        ...
