"""
VideoMaster model — deduplicated video record shared across projects.

Videos are stored once (by SHA-256 hash) and can be referenced by
multiple projects via the ProjectVideo join table.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.infrastructure.database.base import Base, UUIDMixin

if TYPE_CHECKING:
    from backend.infrastructure.database.models.project_video import ProjectVideo


class VideoMaster(Base, UUIDMixin):
    """Deduplicated video record — shared across projects.

    Every imported video is stored as a VideoMaster record.
    The SHA-256 hash ensures deduplication: the same file
    imported into multiple projects creates only one master record.
    """

    __tablename__ = "video_master"

    # ─── Fields ────────────────────────────────────────────────
    hash: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    fps: Mapped[float] = mapped_column(Float, nullable=False)
    video_codec: Mapped[str] = mapped_column(String(50), nullable=False)
    audio_codec: Mapped[str | None] = mapped_column(String(50), nullable=True, default=None)
    audio_channels: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    audio_sample_rate: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    bitrate: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now(UTC)
    )

    # ─── Relationships ─────────────────────────────────────────
    project_videos: Mapped[list[ProjectVideo]] = relationship(
        "ProjectVideo",
        back_populates="video_master",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
