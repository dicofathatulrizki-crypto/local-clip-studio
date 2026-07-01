"""ProcessingQueue ORM model — background job queue."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.database.engine import Base
from backend.infrastructure.database.models.base import UUIDMixin


class ProcessingQueue(UUIDMixin, Base):
    """Background job queue — tracks pipeline, export, and other jobs."""

    __tablename__ = "processing_queue"

    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE")
    )
    video_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("project_videos.id", ondelete="SET NULL"), nullable=True
    )
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    priority: Mapped[int] = mapped_column(Integer, default=0)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now()
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_queue_status", "status", "priority"),
        Index("idx_queue_type", "job_type"),
    )
