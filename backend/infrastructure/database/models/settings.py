"""
SettingsEntry model — global key-value settings storage.

Each setting is stored as a single row with a dot-separated key
and JSON-encoded value. Supports any number of settings without
schema changes.
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.database.base import Base


class SettingsEntry(Base):
    """Global application settings stored as key-value pairs.

    Keys use dot-separated notation (e.g., 'storage.max_cache_size_gb').
    Values are JSON-encoded for type flexibility.
    """

    __tablename__ = "settings"

    # ─── Fields ────────────────────────────────────────────────
    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now(UTC),
        onupdate=datetime.now(UTC),
    )
