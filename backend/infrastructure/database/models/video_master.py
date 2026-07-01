"""VideoMaster ORM model — deduplicated video record shared across projects."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.database.engine import Base
from backend.infrastructure.database.models.base import UUIDMixin


class VideoMaster(UUIDMixin, Base):
    """Deduplicated video record — shared across projects."""

    __tablename__ = "video_master"

    hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    fps: Mapped[float] = mapped_column(Float, nullable=False)
    video_codec: Mapped[str] = mapped_column(String(50), nullable=False)
    audio_codec: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    bitrate: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now()
    )
