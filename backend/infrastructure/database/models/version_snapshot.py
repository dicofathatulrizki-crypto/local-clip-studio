"""
VersionSnapshot model — stores project version history for recovery.

Snapshots are created automatically (on project close, before analysis,
before export) and manually (user-initiated). Supports restoring
projects to previous states.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.infrastructure.database.base import Base, UUIDMixin

if TYPE_CHECKING:
    from backend.infrastructure.database.models.project import Project


class VersionSnapshot(Base, UUIDMixin):
    """A point-in-time snapshot of a project's state.

    Supports the backup and recovery strategy: snapshots are created
    at key moments and can be used to restore the project to a
    previous state.
    """

    __tablename__ = "version_snapshots"

    # ─── Fields ────────────────────────────────────────────────
    project_id: Mapped[str] = mapped_column(
        String(36),  # type: ignore[name-defined]
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_path: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="auto"
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now(UTC)
    )

    # ─── Relationships ─────────────────────────────────────────
    project: Mapped[Project] = relationship("Project", back_populates="version_snapshots")

    # ─── Constraints ───────────────────────────────────────────
    __table_args__ = (
        UniqueConstraint(
            "project_id", "version_number", name="uq_snapshot_version"
        ),
    )
