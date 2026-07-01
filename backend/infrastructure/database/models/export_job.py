"""ExportJob ORM model — tracks export operations."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.database.engine import Base
from backend.infrastructure.database.models.base import UUIDMixin


class ExportJob(UUIDMixin, Base):
    """Export job tracking — format, preset, progress, output."""

    __tablename__ = "export_jobs"

    clip_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("clip_candidates.id", ondelete="CASCADE")
    )
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    preset: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    output_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_export_status", "status"),
        Index("idx_export_clip", "clip_id"),
    )
