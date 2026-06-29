"""
Base repository pattern for Local Clip Studio.

Provides generic CRUD operations that all specific repositories inherit.
Uses SQLAlchemy 2.0 async ORM patterns with type safety.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from sqlalchemy import Result, Select, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.infrastructure.database.base import Base, SoftDeleteMixin

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Generic repository providing CRUD operations for any model.

    Features:
    - Automatic soft-delete filtering (excludes archived records)
    - Pagination with limit/offset
    - Ordering by any column
    - Count queries
    """

    def __init__(self, model_class: type[ModelT], session: AsyncSession) -> None:
        self.model_class = model_class
        self.session = session

    # ─── Query Building Helpers ─────────────────────────────────

    def _apply_soft_delete_filter(self, stmt: Select) -> Select:
        """Add soft-delete filter if the model supports it."""
        if issubclass(self.model_class, SoftDeleteMixin):
            return stmt.where(self.model_class.is_archived == 0)  # type: ignore[attr-defined]
        return stmt

    # ─── Create ─────────────────────────────────────────────────

    async def create(self, **kwargs: Any) -> ModelT:
        """Create a new record and flush to get the ID.

        Args:
            **kwargs: Field values for the new record
        Returns:
            The created model instance
        """
        instance = self.model_class(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    # ─── Read ───────────────────────────────────────────────────

    async def get(self, id_: str) -> ModelT | None:
        """Get a record by primary key.

        Args:
            id_: The UUID string primary key
        Returns:
            The model instance or None if not found
        """
        stmt = select(self.model_class).where(
            self.model_class.id == id_  # type: ignore[attr-defined]
        )
        stmt = self._apply_soft_delete_filter(stmt)
        result: Result = await self.session.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def list(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        order_by: str | None = None,
        descending: bool = True,
        filters: dict[str, Any] | None = None,
    ) -> tuple[list[ModelT], int]:
        """List records with pagination, ordering, and filtering.

        Args:
            limit: Maximum number of records to return
            offset: Number of records to skip
            order_by: Column name to order by (defaults to id)
            descending: Sort descending if True
            filters: Dict of column=value equality filters
        Returns:
            Tuple of (records list, total count)
        """
        # Count query
        count_stmt = select(func.count()).select_from(self.model_class)
        count_stmt = self._apply_soft_delete_filter(count_stmt)
        if filters:
            for col, val in filters.items():
                count_stmt = count_stmt.where(
                    getattr(self.model_class, col) == val
                )
        count_result: Result = await self.session.execute(count_stmt)
        total: int = count_result.scalar_one()

        # Data query
        stmt = select(self.model_class)
        stmt = self._apply_soft_delete_filter(stmt)

        if filters:
            for col, val in filters.items():
                stmt = stmt.where(getattr(self.model_class, col) == val)

        if order_by:
            col = getattr(self.model_class, order_by)
            stmt = stmt.order_by(col.desc() if descending else col.asc())

        stmt = stmt.offset(offset).limit(limit)
        result: Result = await self.session.execute(stmt)
        records: list[ModelT] = list(result.unique().scalars().all())

        return records, total

    async def find_by(
        self, **kwargs: Any
    ) -> ModelT | None:
        """Find a single record by field values.

        Args:
            **kwargs: Field=value pairs to filter by
        Returns:
            The first matching record or None
        """
        stmt = select(self.model_class)
        stmt = self._apply_soft_delete_filter(stmt)
        for col, val in kwargs.items():
            stmt = stmt.where(getattr(self.model_class, col) == val)
        result: Result = await self.session.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def find_many_by(
        self, **kwargs: Any
    ) -> Sequence[ModelT]:
        """Find all records matching field values.

        Args:
            **kwargs: Field=value pairs to filter by
        Returns:
            List of matching records
        """
        stmt = select(self.model_class)
        stmt = self._apply_soft_delete_filter(stmt)
        for col, val in kwargs.items():
            stmt = stmt.where(getattr(self.model_class, col) == val)
        result: Result = await self.session.execute(stmt)
        return list(result.unique().scalars().all())

    async def exists(self, id_: str) -> bool:
        """Check if a record exists by primary key.

        Args:
            id_: The UUID string primary key
        Returns:
            True if the record exists (and is not soft-deleted)
        """
        stmt = select(self.model_class).where(
            self.model_class.id == id_  # type: ignore[attr-defined]
        )
        stmt = self._apply_soft_delete_filter(stmt)
        result: Result = await self.session.execute(stmt)
        return result.unique().scalar_one_or_none() is not None

    # ─── Update ─────────────────────────────────────────────────

    async def update(self, id_: str, **kwargs: Any) -> ModelT | None:
        """Update a record by primary key with partial field updates.

        Args:
            id_: The UUID string primary key
            **kwargs: Field values to update
        Returns:
            The updated model instance or None if not found
        """
        instance = await self.get(id_)
        if instance is None:
            return None

        for key, value in kwargs.items():
            if hasattr(instance, key):
                setattr(instance, key, value)

        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    # ─── Delete ─────────────────────────────────────────────────

    async def delete(self, id_: str) -> bool:
        """Hard delete a record by primary key.

        Returns True if a record was deleted, False if not found.
        """
        instance = await self.get(id_)
        if instance is None:
            return False

        await self.session.delete(instance)
        await self.session.flush()
        return True

    async def soft_delete(self, id_: str) -> bool:
        """Soft delete (archive) a record if it supports soft-delete.

        Returns True if archived, False if not found or not supported.
        """
        if not issubclass(self.model_class, SoftDeleteMixin):
            return await self.delete(id_)

        instance = await self.get(id_)
        if instance is None:
            return False

        instance.soft_delete()  # type: ignore[attr-defined]
        await self.session.flush()
        return True

    async def restore(self, id_: str) -> ModelT | None:
        """Restore a soft-deleted record.

        Args:
            id_: The UUID string primary key
        Returns:
            The restored instance or None if not found
        """
        if not issubclass(self.model_class, SoftDeleteMixin):
            return None

        # Bypass soft-delete filter to find archived records
        stmt = select(self.model_class).where(
            self.model_class.id == id_  # type: ignore[attr-defined]
        )
        result: Result = await self.session.execute(stmt)
        instance = result.unique().scalar_one_or_none()

        if instance is None:
            return None

        instance.restore()  # type: ignore[attr-defined]
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    # ─── Utility ────────────────────────────────────────────────

    async def count(
        self, filters: dict[str, Any] | None = None
    ) -> int:
        """Count records with optional filters.

        Args:
            filters: Dict of column=value equality filters
        Returns:
            Total count
        """
        stmt = select(func.count()).select_from(self.model_class)
        stmt = self._apply_soft_delete_filter(stmt)
        if filters:
            for col, val in filters.items():
                stmt = stmt.where(getattr(self.model_class, col) == val)
        result: Result = await self.session.execute(stmt)
        return result.scalar_one()

    async def raw_sql(self, sql: str, params: dict[str, Any] | None = None) -> Result:
        """Execute raw SQL (for custom queries beyond ORM).

        Args:
            sql: Raw SQL string
            params: Optional parameters for the query
        Returns:
            SQLAlchemy Result object
        """
        result: Result = await self.session.execute(
            text(sql).bindparams(**(params or {}))
        )
        return result
