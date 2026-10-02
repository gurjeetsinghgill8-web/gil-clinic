"""Pagination value object for list queries.

Consistent pagination across all engines.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Pagination:
    """Pagination parameters for list queries.

    Attributes:
        offset: Number of records to skip.
        limit: Maximum number of records to return.
        total: Total number of records (set after query).
        sort_by: Field to sort by.
        sort_order: "asc" or "desc".
    """

    offset: int = 0
    limit: int = 20
    total: int = 0
    sort_by: str | None = None
    sort_order: str = "asc"

    @classmethod
    def default(cls) -> Pagination:
        """Create default pagination.

        Returns:
            Pagination with offset=0, limit=20.
        """
        return cls()

    @property
    def page(self) -> int:
        """Get 1-based page number.

        Returns:
            Current page number.
        """
        return (self.offset // self.limit) + 1 if self.limit > 0 else 1

    @property
    def total_pages(self) -> int:
        """Get total pages.

        Returns:
            Number of pages based on total/limit.
        """
        if self.limit <= 0:
            return 0
        return (self.total + self.limit - 1) // self.limit

    @property
    def has_next(self) -> bool:
        """Check if there is a next page."""
        return self.offset + self.limit < self.total

    @property
    def has_prev(self) -> bool:
        """Check if there is a previous page."""
        return self.offset > 0

    def to_metadata(self) -> dict[str, Any]:
        """Convert to metadata dict for Result.

        Returns:
            Dict with pagination info.
        """
        return {
            "page": self.page,
            "limit": self.limit,
            "total": self.total,
            "total_pages": self.total_pages,
            "has_next": self.has_next,
            "has_prev": self.has_prev,
        }

    def __repr__(self) -> str:
        return (
            f"<Pagination page={self.page} "
            f"limit={self.limit} "
            f"total={self.total}>"
        )
