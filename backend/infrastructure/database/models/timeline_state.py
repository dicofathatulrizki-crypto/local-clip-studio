"""TimelineState ORM model — project timeline state."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.infrastructure.database.engine import Base
from backend.infrastructure.database.models.base import UUIDMixin

if TYPE_CHECKING:
    from backend.infrastructure.database.models.project import Project


class TimelineState(UUIDMixin, Base):
    """Project timeline state — tracks, markers, zoom, playhead."""

    __tablename__ = "timeline_states"

    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), unique=True
    )
    tracks: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    markers: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    zoom_level: Mapped[float] = mapped_column(Float, default=1.0)
    playhead_position_ms: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)

    project: Mapped["Project"] = relationship("Project", back_populates="timeline")
