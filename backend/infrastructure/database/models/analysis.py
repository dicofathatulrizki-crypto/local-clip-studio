"""Analysis ORM model — stores AI pipeline results."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.infrastructure.database.engine import Base
from backend.infrastructure.database.models.base import UUIDMixin

if TYPE_CHECKING:
    from backend.infrastructure.database.models.project_video import ProjectVideo


class Analysis(UUIDMixin, Base):
    """AI pipeline analysis results for a video."""

    __tablename__ = "analyses"

    video_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("project_videos.id", ondelete="CASCADE"), unique=True
    )
    status: Mapped[str] = mapped_column(String(20), default="pending")
    transcript: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    speakers: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    scenes: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    topics: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    keywords: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    emotions: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    hooks: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    chapters: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    quality_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    video: Mapped["ProjectVideo"] = relationship("ProjectVideo", back_populates="analysis")
