"""SettingsEntry ORM model — key-value settings storage."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.database.engine import Base
from backend.infrastructure.database.models.base import UUIDMixin


class SettingsEntry(UUIDMixin, Base):
    """Key-value settings storage with JSON value."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    value: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    category: Mapped[str] = mapped_column(String(100), default="general")
