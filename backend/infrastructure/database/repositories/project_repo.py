"""
ProjectRepository — data access for Project entities.

Extends BaseRepository with project-specific queries:
- Recent projects (sorted by last_opened_at)
- Search by name
- List archived (soft-deleted) projects
"""
from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.infrastructure.database.models.project import Project
from backend.infrastructure.database.repositories.base import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    """Repository for Project CRUD with project-specific queries."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Project, session)

    async def get_recent(
        self, count: int = 10, include_archived: bool = False
    ) -> Sequence[Project]:
        """Get the most recently opened projects.

        Args:
            count: Maximum number of projects to return
            include_archived: Whether to include soft-deleted projects
        Returns:
            List of projects sorted by last_opened_at descending
        """
        stmt = (
            select(Project)
            .order_by(Project.last_opened_at.desc().nullslast())
            .limit(count)
        )
        if not include_archived:
            stmt = stmt.where(Project.is_archived == 0)  # type: ignore[attr-defined]
        result = await self.session.execute(stmt)
        return list(result.unique().scalars().all())

    async def search_by_name(
        self, query: str, limit: int = 20
    ) -> Sequence[Project]:
        """Search projects by name (case-insensitive LIKE).

        Args:
            query: Search string
            limit: Maximum results
        Returns:
            List of matching projects
        """
        pattern = f"%{query}%"
        stmt = (
            select(Project)
            .where(Project.name.ilike(pattern))
            .where(Project.is_archived == 0)  # type: ignore[attr-defined]
            .order_by(Project.last_opened_at.desc().nullslast())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.unique().scalars().all())

    async def list_archived(
        self, limit: int = 50, offset: int = 0
    ) -> tuple[Sequence[Project], int]:
        """List soft-deleted (archived) projects.

        Args:
            limit: Maximum records
            offset: Pagination offset
        Returns:
            Tuple of (projects list, total archived count)
        """
        count_stmt = select(func.count()).select_from(Project).where(
            Project.is_archived == 1  # type: ignore[attr-defined]
        )
        count_result = await self.session.execute(count_stmt)
        total: int = count_result.scalar_one()

        stmt = (
            select(Project)
            .where(Project.is_archived == 1)  # type: ignore[attr-defined]
            .order_by(Project.archived_at.desc().nullslast())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.unique().scalars().all()), total
