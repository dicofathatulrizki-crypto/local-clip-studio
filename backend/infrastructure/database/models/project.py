"""
Project model — the top-level aggregate for a video editing project.

Each project owns videos, a timeline, processing jobs, and version snapshots.
Projects can be soft-deleted (archived) for recovery.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.infrastructure.database.base import (
    Base,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDMixin,
)

if TYPE_CHECKING:
    from backend.infrastructure.database.models.project_video import ProjectVideo
    from backend.infrastructure.database.models.processing_queue import ProcessingQueue
    from backend.infrastructure.database.models.timeline_state import TimelineState
    from backend.infrastructure.database.models.version_snapshot import VersionSnapshot


class Project(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """A video editing project — the top-level aggregate.

    Relationships cascade on delete: videos, timeline, queue items, snapshots.
    Soft-delete via is_archived preserves data for potential recovery.
    """

    __tablename__ = "projects"

    # ─── Fields ────────────────────────────────────────────────
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    last_opened_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=None, index=True
    )
    settings: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)
    thumbnail_path: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)

    # ─── Relationships ─────────────────────────────────────────
    videos: Mapped[list[ProjectVideo]] = relationship(
        "ProjectVideo",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    timeline: Mapped[TimelineState | None] = relationship(
        "TimelineState",
        back_populates="project",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    queue_items: Mapped[list[ProcessingQueue]] = relationship(
        "ProcessingQueue",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    version_snapshots: Mapped[list[VersionSnapshot]] = relationship(
        "VersionSnapshot",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def restore(self) -> None:
        """Restore a soft-deleted project."""
        self.is_archived = False
        self.archived_at = None

    def touch(self) -> None:
        """Mark project as recently opened."""
        self.last_opened_at = datetime.now(UTC)
