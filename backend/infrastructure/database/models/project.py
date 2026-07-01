"""Project ORM model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.infrastructure.database.engine import Base
from backend.infrastructure.database.models.base import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from backend.infrastructure.database.models.project_video import ProjectVideo
    from backend.infrastructure.database.models.timeline_state import TimelineState


class Project(UUIDMixin, TimestampMixin, Base):
    """Project entity — root of the project aggregate."""

    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_opened_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    settings: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    thumbnail_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)

    videos: Mapped[list[ProjectVideo]] = relationship(
        "ProjectVideo", back_populates="project", cascade="all, delete-orphan"
    )
    timeline: Mapped[Optional[TimelineState]] = relationship(
        "TimelineState", back_populates="project", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_projects_last_opened", "last_opened_at"),
        Index("idx_projects_archived", "is_archived"),
    )
