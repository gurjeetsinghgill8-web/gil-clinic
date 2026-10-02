"""Offset-based pagination and cursor-based pagination.

Offset pagination:
    page = OffsetPage(offset=0, limit=20)
    results = await repo.find_paginated(spec, page)

Cursor pagination (keyset):
    page = CursorPage(last_seen_id="uuid", limit=20)
    results = await repo.find_cursor(spec, page)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

T = TypeVar("T")


@dataclass
class OffsetPage:
    """Offset-based pagination parameters.

    Attributes:
        offset: Number of records to skip.
        limit: Maximum records to return.
        sort_by: Column name to sort by.
        sort_order: "asc" or "desc".
    """

    offset: int = 0
    limit: int = 20
    sort_by: str | None = None
    sort_order: str = "asc"

    @property
    def page(self) -> int:
        return (self.offset // self.limit) + 1 if self.limit > 0 else 1

    def to_metadata(self) -> dict[str, Any]:
        return {
            "page": self.page,
            "limit": self.limit,
            "offset": self.offset,
        }


@dataclass
class CursorPage:
    """Cursor-based (keyset) pagination parameters.

    More efficient than offset for large datasets.
    Cursor is typically the last-seen UUID or timestamp.

    Attributes:
        cursor: Last seen value (UUID, datetime, etc.).
        limit: Maximum records to return.
        sort_by: Column name for cursor ordering.
        sort_order: "asc" or "desc".
    """

    cursor: str | None = None
    limit: int = 20
    sort_by: str = "created_at"
    sort_order: str = "desc"

    def to_metadata(self) -> dict[str, Any]:
        return {
            "cursor": self.cursor,
            "limit": self.limit,
            "next_cursor": None,  # Set after query
        }


@dataclass
class PageResult(Generic[T]):
    """Result of a paginated query.

    Attributes:
        items: The returned records.
        total: Total matching records (offset pagination only).
        page: Pagination metadata.
    """

    items: list[T]
    total: int = 0
    page: OffsetPage | CursorPage | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": self.items,
            "total": self.total,
            "page": self.page.to_metadata() if self.page else None,
        }


class PaginationHelper:
    """Helper methods for building paginated SQLAlchemy queries."""

    @staticmethod
    async def paginate_offset(
        session: AsyncSession,
        query,
        page: OffsetPage,
        count_query=None,
    ) -> PageResult:
        """Execute an offset-paginated query.

        Args:
            session: Database session.
            query: SQLAlchemy select statement.
            page: OffsetPage with offset, limit, sorting.
            count_query: Optional count query (default: query with no eager loads).

        Returns:
            PageResult with items and total.
        """
        # Get total count
        if count_query is None:
            count_query = select(func.count()).select_from(query.subquery())
        total_result = await session.execute(count_query)
        total = total_result.scalar() or 0

        # Apply sorting
        if page.sort_by:
            sort_col = getattr(query.selected_columns, page.sort_by, None)
            if sort_col is not None:
                order_fn = asc if page.sort_order == "asc" else desc
                query = query.order_by(order_fn(sort_col))

        # Apply pagination
        query = query.offset(page.offset).limit(page.limit)

        result = await session.execute(query)
        items = list(result.scalars().unique().all())

        return PageResult(items=items, total=total, page=page)

    @staticmethod
    async def paginate_cursor(
        session: AsyncSession,
        query,
        page: CursorPage,
        cursor_column=None,
    ) -> PageResult:
        """Execute a cursor-paginated query.

        Args:
            session: Database session.
            query: SQLAlchemy select statement.
            page: CursorPage with cursor value and limit.
            cursor_column: The column to apply cursor filtering on.

        Returns:
            PageResult with items.
        """
        if page.cursor and cursor_column is not None:
            op = ">" if page.sort_order == "asc" else "<"
            query = query.where(
                getattr(cursor_column, op)(page.cursor)
            )

        order_fn = asc if page.sort_order == "asc" else desc
        query = query.order_by(order_fn(cursor_column)).limit(page.limit)

        result = await session.execute(query)
        items = list(result.scalars().unique().all())

        # Set next cursor
        if items and page.cursor is None:
            page.cursor = str(getattr(items[-1], page.sort_by, ""))

        return PageResult(items=items, page=page)
