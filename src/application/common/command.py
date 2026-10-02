"""CQRS Command and Query marker classes.

Every use case in GHOS is either a Command (mutates state) or a Query (reads state).
This provides consistent typing across all 13 engines.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Command:
    """Marker for commands — operations that change system state.

    Commands are named with past-tense verbs (e.g., "AuthenticateUser").
    They carry input data and an optional metadata context.

    Attributes:
        data: Input payload for the command.
        command_id: Unique identifier for tracing.
        metadata: Optional dict for correlation IDs, trace IDs.
    """

    data: dict = field(default_factory=dict)
    command_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Query:
    """Marker for queries — read-only operations.

    Queries never mutate state. They return data through a Result.

    Attributes:
        data: Input payload for the query (filters, search params, etc.).
        query_id: Unique identifier for tracing.
        metadata: Optional dict for correlation IDs.
    """

    data: dict = field(default_factory=dict)
    query_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
