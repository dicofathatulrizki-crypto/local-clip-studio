"""
ModelRegistry model — tracks downloaded AI model files.

Each row represents an AI model (STT, LLM, vision, embedding) with
its download status, file path, version, and checksum.
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.database.base import Base


class ModelRegistry(Base):
    """AI model file tracking.

    Tracks the lifecycle of AI models: not downloaded → downloading →
    ready → error. Each model has metadata about size, VRAM requirements,
    version, and checksum for integrity verification.
    """

    __tablename__ = "model_registry"

    # ─── Fields ────────────────────────────────────────────────
    model_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    model_type: Mapped[str] = mapped_column(String(30), nullable=False)
    size_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    vram_mb: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    path: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="not_downloaded"
    )
    download_progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    version: Mapped[str | None] = mapped_column(String(50), nullable=True, default=None)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True, default=None)
    downloaded_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now(UTC)
    )
