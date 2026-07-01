"""ProjectVideo ORM model — joins projects to videos."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.infrastructure.database.engine import Base
from backend.infrastructure.database.models.base import UUIDMixin

if TYPE_CHECKING:
    from backend.infrastructure.database.models.analysis import Analysis
    from backend.infrastructure.database.models.clip_candidate import ClipCandidate
    from backend.infrastructure.database.models.project import Project
    from backend.infrastructure.database.models.video_master import VideoMaster


class ProjectVideo(UUIDMixin, Base):
    """Join table linking projects to videos with import metadata."""

    __tablename__ = "project_videos"

    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    video_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("video_master.id"), nullable=False
    )
    import_order: Mapped[int] = mapped_column(Integer, default=0)
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    proxy_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now()
    )

    project: Mapped["Project"] = relationship("Project", back_populates="videos")
    video_master: Mapped["VideoMaster"] = relationship("VideoMaster")
    analysis: Mapped[Optional["Analysis"]] = relationship(
        "Analysis", back_populates="video", uselist=False, cascade="all, delete-orphan"
    )
    clip_candidates: Mapped[list["ClipCandidate"]] = relationship(
        "ClipCandidate", back_populates="video", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("project_id", "video_id", name="uq_project_video"),
        Index("idx_pv_project", "project_id"),
        Index("idx_pv_video", "video_id"),
    )
