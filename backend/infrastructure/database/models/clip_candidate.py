"""ClipCandidate ORM model — AI-generated clip suggestions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.infrastructure.database.engine import Base
from backend.infrastructure.database.models.base import UUIDMixin

if TYPE_CHECKING:
    from backend.infrastructure.database.models.project_video import ProjectVideo


class ClipCandidate(UUIDMixin, Base):
    """AI-generated clip candidate with scores and metadata."""

    __tablename__ = "clip_candidates"

    video_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("project_videos.id", ondelete="CASCADE")
    )
    start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    end_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    quality_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    virality_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    hook_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hashtags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="candidate")
    rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    video: Mapped["ProjectVideo"] = relationship("ProjectVideo", back_populates="clip_candidates")

    __table_args__ = (
        Index("idx_clip_video_status", "video_id", "status"),
        Index("idx_clip_rank", "rank"),
    )
