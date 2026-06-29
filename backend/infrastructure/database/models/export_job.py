"""
ExportJob model — tracks video export rendering jobs.

Each export job renders a clip candidate to a specific output format.
Tracks progress, encoding speed, and error details.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.infrastructure.database.base import Base, UUIDMixin

if TYPE_CHECKING:
    from backend.infrastructure.database.models.clip_candidate import ClipCandidate


class ExportJob(Base, UUIDMixin):
    """A video export rendering job.

    Each job renders a clip to a specific format/preset combination.
    Status tracks the full lifecycle: pending → rendering → completed/failed/cancelled.
    """

    __tablename__ = "export_jobs"

    # ─── Fields ────────────────────────────────────────────────
    clip_id: Mapped[str] = mapped_column(
        String(36),  # type: ignore[name-defined]
        ForeignKey("clip_candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    preset: Mapped[str | None] = mapped_column(String(50), nullable=True, default=None)
    resolution: Mapped[str | None] = mapped_column(String(20), nullable=True, default=None)
    bitrate: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    include_captions: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    caption_language: Mapped[str] = mapped_column(
        String(10), nullable=False, default="en"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", index=True
    )
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    output_path: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    encoding_speed: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=None
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now(UTC)
    )

    # ─── Relationships ─────────────────────────────────────────
    clip: Mapped[ClipCandidate] = relationship("ClipCandidate", back_populates="export_jobs")

    # ─── Indexes ───────────────────────────────────────────────
    __table_args__ = (
        Index("idx_export_status", "status"),
    )
