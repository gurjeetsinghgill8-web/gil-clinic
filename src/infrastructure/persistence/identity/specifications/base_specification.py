"""Base specification with composite support (AND, OR, NOT).

Specification pattern enables:
- Reusable filter logic
- Composite queries (AND, OR, NOT)
- Type-safe filtering
- Testable query building
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy import and_, not_, or_
from sqlalchemy.sql import ColumnElement


class Specification(ABC):
    """Abstract base for all query specifications.

    A specification encapsulates a WHERE clause condition.
    Specifications can be combined using & (AND), | (OR), ~ (NOT).

    Usage:
        spec = ActiveUsersSpecification() & ByRoleSpecification("DOCTOR")
        query = select(UserModel).where(spec.apply())
    """

    @abstractmethod
    def apply(self) -> ColumnElement[Any]:
        """Apply the specification to produce a SQLAlchemy WHERE clause.

        Returns:
            SQLAlchemy ColumnElement representing the filter condition.
        """
        ...

    def __and__(self, other: Specification) -> AndSpecification:
        """Combine with AND."""
        return AndSpecification(self, other)

    def __or__(self, other: Specification) -> OrSpecification:
        """Combine with OR."""
        return OrSpecification(self, other)

    def __invert__(self) -> NotSpecification:
        """Negate the specification."""
        return NotSpecification(self)


class AndSpecification(Specification):
    """Composite specification: A AND B."""

    def __init__(self, *specs: Specification) -> None:
        self.specs = specs

    def apply(self) -> ColumnElement[Any]:
        return and_(*[s.apply() for s in self.specs])


class OrSpecification(Specification):
    """Composite specification: A OR B."""

    def __init__(self, *specs: Specification) -> None:
        self.specs = specs

    def apply(self) -> ColumnElement[Any]:
        return or_(*[s.apply() for s in self.specs])


class NotSpecification(Specification):
    """Composite specification: NOT A."""

    def __init__(self, spec: Specification) -> None:
        self.spec = spec

    def apply(self) -> ColumnElement[Any]:
        return not_(self.spec.apply())
