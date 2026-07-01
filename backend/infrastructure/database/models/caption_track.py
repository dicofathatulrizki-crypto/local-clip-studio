"""CaptionTrack ORM model — caption tracks for clips."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.database.engine import Base
from backend.infrastructure.database.models.base import UUIDMixin


class CaptionTrack(UUIDMixin, Base):
    """Caption track — timed captions for a clip."""

    __tablename__ = "caption_tracks"

    clip_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("clip_candidates.id", ondelete="CASCADE")
    )
    language: Mapped[str] = mapped_column(String(10), default="en")
    style: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    captions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    is_source_language: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (
        UniqueConstraint("clip_id", "language", name="uq_clip_language"),
    )
