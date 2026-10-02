"""Generic base repository with OCC, batch operations, and Specification support.

Provides reusable CRUD operations for all aggregate types.
Repositories only persist — no business logic, no event publishing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.infrastructure.persistence.identity.exceptions.persistence_exceptions import (
    ConcurrentModificationError,
    EntityNotFoundError,
)
from src.infrastructure.persistence.identity.pagination.page import (
    CursorPage,
    OffsetPage,
    PageResult,
    PaginationHelper,
)
from src.infrastructure.persistence.identity.specifications.base_specification import (
    Specification,
)

ModelT = TypeVar("ModelT")
DomainT = TypeVar("DomainT")


class BaseRepository(ABC, Generic[DomainT, ModelT]):
    """Generic base repository with OCC, batch ops, and specifications.

    Subclasses implement:
    - _to_domain(): Model → Domain entity mapping
    - _apply_to_model(): Domain → Model mapping (for updates)
    - _model_class: The SQLAlchemy model class
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @property
    @abstractmethod
    def _model_class(self) -> type[ModelT]:
        """Return the SQLAlchemy model class for this repository."""
        ...

    @abstractmethod
    def _to_domain(self, model: ModelT) -> DomainT:
        """Convert a SQLAlchemy model instance to a domain entity.

        Args:
            model: SQLAlchemy model instance.

        Returns:
            Domain entity.
        """
        ...

    @abstractmethod
    def _apply_to_model(self, model: ModelT, entity: DomainT) -> None:
        """Apply domain entity data to a SQLAlchemy model.

        Args:
            model: SQLAlchemy model to update.
            entity: Domain entity with new values.
        """
        ...

    # ------------------------------------------------------------------
    # Default eager loading relationships
    # ------------------------------------------------------------------

    def _default_eager_loads(self, query):
        """Apply default eager loads to prevent N+1 queries.

        Override in subclasses to specify relationships.
        """
        return query

    # ------------------------------------------------------------------
    # CRUD Operations
    # ------------------------------------------------------------------

    async def save(self, entity: DomainT) -> DomainT:
        """Persist a new or updated aggregate.

        If the entity has an existing version > 0, this performs
        an OCC check. If the version doesn't match, raises
        ConcurrentModificationError.

        Args:
            entity: Domain entity to persist.

        Returns:
            The saved domain entity with updated version.

        Raises:
            ConcurrentModificationError: If OCC version mismatch.
        """
        entity_id = str(entity.id)
        model = await self.get_model(entity_id)

        if model:
            # Update — OCC check
            expected_version = entity.version - 1
            if model.version != expected_version:
                raise ConcurrentModificationError(
                    entity_type=self._model_class.__name__,
                    entity_id=entity_id,
                    expected_version=expected_version,
                )
            self._apply_to_model(model, entity)
            model.version += 1
        else:
            # Insert
            model = self._model_class(id=entity.id)
            self._apply_to_model(model, entity)
            model.version = entity.version
            self.session.add(model)

        await self.session.flush()
        return self._to_domain(model)

    async def get_by_id(self, entity_id: str) -> DomainT | None:
        """Get an entity by its UUID.

        Args:
            entity_id: UUID string.

        Returns:
            Domain entity if found, None otherwise.
        """
        query = select(self._model_class).where(
            self._model_class.id == entity_id
        )
        query = self._default_eager_loads(query)
        result = await self.session.execute(query)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def exists(self, entity_id: str) -> bool:
        """Check if an entity exists.

        Args:
            entity_id: UUID string.

        Returns:
            True if entity exists.
        """
        query = select(self._model_class.id).where(
            self._model_class.id == entity_id
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None

    async def delete(self, entity_id: str) -> bool:
        """Hard delete an entity by ID.

        For soft-delete, use soft_delete() instead.

        Args:
            entity_id: UUID string.

        Returns:
            True if deleted, False if not found.
        """
        query = delete(self._model_class).where(
            self._model_class.id == entity_id
        )
        result = await self.session.execute(query)
        await self.session.flush()
        return result.rowcount > 0

    async def soft_delete(self, entity_id: str) -> bool:
        """Soft delete an entity by ID (set is_deleted = True).

        Args:
            entity_id: UUID string.

        Returns:
            True if soft-deleted, False if not found.
        """
        from datetime import datetime, timezone

        stmt = (
            update(self._model_class)
            .where(self._model_class.id == entity_id)
            .values(
                is_deleted=True,
                deleted_at=datetime.now(timezone.utc),
            )
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount > 0

    # ------------------------------------------------------------------
    # Specification-based queries
    # ------------------------------------------------------------------

    async def find(
        self,
        spec: Specification,
        page: OffsetPage | None = None,
    ) -> list[DomainT]:
        """Find entities matching a specification.

        Args:
            spec: Filter specification.
            page: Optional pagination.

        Returns:
            List of domain entities.
        """
        query = select(self._model_class).where(spec.apply())
        query = self._default_eager_loads(query)

        if page:
            query = query.offset(page.offset).limit(page.limit)

        result = await self.session.execute(query)
        models = list(result.scalars().unique().all())
        return [self._to_domain(m) for m in models]

    async def find_one(
        self,
        spec: Specification,
    ) -> DomainT | None:
        """Find a single entity matching a specification.

        Args:
            spec: Filter specification.

        Returns:
            Domain entity if found, None otherwise.
        """
        query = select(self._model_class).where(spec.apply()).limit(1)
        query = self._default_eager_loads(query)
        result = await self.session.execute(query)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def count(self, spec: Specification | None = None) -> int:
        """Count entities matching a specification.

        Args:
            spec: Optional filter specification.

        Returns:
            Count of matching entities.
        """
        from sqlalchemy import func

        query = select(func.count()).select_from(self._model_class)
        if spec:
            query = query.where(spec.apply())
        result = await self.session.execute(query)
        return result.scalar() or 0

    async def find_paginated(
        self,
        spec: Specification,
        page: OffsetPage,
    ) -> PageResult[DomainT]:
        """Find entities with offset pagination.

        Args:
            spec: Filter specification.
            page: Offset page parameters.

        Returns:
            Paginated result with items and total count.
        """
        query = select(self._model_class).where(spec.apply())
        query = self._default_eager_loads(query)

        result = await PaginationHelper.paginate_offset(
            self.session, query, page
        )
        result.items = [self._to_domain(m) for m in result.items]
        return result

    async def find_cursor(
        self,
        spec: Specification,
        page: CursorPage,
    ) -> PageResult[DomainT]:
        """Find entities with cursor-based pagination.

        Args:
            spec: Filter specification.
            page: Cursor page parameters.

        Returns:
            Paginated result with items and next cursor.
        """
        query = select(self._model_class).where(spec.apply())
        query = self._default_eager_loads(query)

        cursor_column = getattr(
            self._model_class, page.sort_by, self._model_class.created_at
        )
        result = await PaginationHelper.paginate_cursor(
            self.session, query, page, cursor_column
        )
        result.items = [self._to_domain(m) for m in result.items]
        return result

    # ------------------------------------------------------------------
    # Batch Operations
    # ------------------------------------------------------------------

    async def save_batch(self, entities: list[DomainT]) -> list[DomainT]:
        """Persist multiple entities in a single transaction.

        Args:
            entities: List of domain entities to persist.

        Returns:
            List of saved domain entities.
        """
        return [await self.save(entity) for entity in entities]

    async def delete_batch(self, entity_ids: list[str]) -> int:
        """Hard delete multiple entities by IDs.

        Args:
            entity_ids: List of UUID strings.

        Returns:
            Number of deleted rows.
        """
        stmt = delete(self._model_class).where(
            self._model_class.id.in_(entity_ids)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount

    async def soft_delete_batch(self, entity_ids: list[str]) -> int:
        """Soft delete multiple entities by IDs.

        Args:
            entity_ids: List of UUID strings.

        Returns:
            Number of soft-deleted rows.
        """
        from datetime import datetime, timezone

        stmt = (
            update(self._model_class)
            .where(self._model_class.id.in_(entity_ids))
            .values(
                is_deleted=True,
                deleted_at=datetime.now(timezone.utc),
            )
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def get_model(self, entity_id: str) -> ModelT | None:
        """Get the raw SQLAlchemy model by ID.

        Args:
            entity_id: UUID string.

        Returns:
            SQLAlchemy model instance or None.
        """
        query = select(self._model_class).where(
            self._model_class.id == entity_id
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def _check_duplicate(
        self, field: Any, value: Any, exclude_id: str | None = None
    ) -> bool:
        """Check if a field value already exists (for unique validation).

        Args:
            field: SQLAlchemy column to check.
            value: Value to check for.
            exclude_id: Optional ID to exclude from check.

        Returns:
            True if duplicate exists.
        """
        query = select(self._model_class).where(field == value)
        if exclude_id:
            query = query.where(self._model_class.id != exclude_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None
