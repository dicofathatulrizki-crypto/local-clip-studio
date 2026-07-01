"""ModelRegistry ORM model — tracks downloaded AI models."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.database.engine import Base
from backend.infrastructure.database.models.base import UUIDMixin


class ModelRegistry(UUIDMixin, Base):
    """Downloaded AI model registry."""

    __tablename__ = "model_registry"

    model_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    checksum: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    is_downloaded: Mapped[bool] = mapped_column(Boolean, default=False)
    model_metadata: Mapped[Optional[dict]] = mapped_column("model_metadata", JSON, nullable=True)
    downloaded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
