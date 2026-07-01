"""VersionSnapshot ORM model — project version history."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.database.engine import Base
from backend.infrastructure.database.models.base import UUIDMixin


class VersionSnapshot(UUIDMixin, Base):
    """Project version history snapshot."""

    __tablename__ = "version_snapshots"

    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE")
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_type: Mapped[str] = mapped_column(String(20), default="auto")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timeline_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    project_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now()
    )

    __table_args__ = (
        Index("idx_snapshot_project", "project_id", "version_number"),
        Index("idx_snapshot_created", "created_at"),
    )
