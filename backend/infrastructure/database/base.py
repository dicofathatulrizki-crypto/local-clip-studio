"""
Declarative base and common mixins for all database models.

Provides:
- UUIDMixin: auto-generated UUID primary keys (stored as TEXT for SQLite)
- TimestampMixin: created_at, updated_at with auto-update
- SoftDeleteMixin: is_archived, archived_at for soft deletion
- Base: combined declarative base with all mixins
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


# ─── SQLite Optimizations ───────────────────────────────────────


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection: object, _connection_record: object) -> None:
    """Configure SQLite connection pragmas for performance and safety.

    Applied automatically to every new SQLite connection:
    - WAL mode: better concurrent read performance
    - Foreign keys: enforce referential integrity
    - Busy timeout: wait 5s instead of failing immediately
    - Synchronous NORMAL: balance durability/speed
    - Cache: 64MB page cache
    - Temp store: in-memory for temp tables
    - Memory-map: 256MB for faster reads
    """
    import sqlite3

    if not isinstance(dbapi_connection, sqlite3.Connection):
        return

    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode = WAL")
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.execute("PRAGMA busy_timeout = 5000")
    cursor.execute("PRAGMA synchronous = NORMAL")
    cursor.execute("PRAGMA cache_size = -64000")
    cursor.execute("PRAGMA temp_store = MEMORY")
    cursor.execute("PRAGMA mmap_size = 268435456")
    cursor.close()


# ─── Declarative Base ───────────────────────────────────────────


class Base(DeclarativeBase):
    """Base class for all ORM models."""


# ─── Mixins ─────────────────────────────────────────────────────


class UUIDMixin:
    """Adds a UUID primary key column.

    Uses String(36) for SQLite compatibility.
    For PostgreSQL, change to sqlalchemy.dialects.postgresql.UUID.
    """

    id: Mapped[str] = mapped_column(
        String(36),  # type: ignore[name-defined]
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )


class TimestampMixin:
    """Adds created_at and updated_at timestamp columns.

    - created_at: set on insert, never updated
    - updated_at: set on insert and updated on every row update
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now(UTC),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now(UTC),
        server_default=func.now(),
        onupdate=datetime.now(UTC),
    )


class SoftDeleteMixin:
    """Adds soft-delete capability with is_archived flag and archived_at timestamp.

    Soft-deleted records are excluded from normal queries by the base repository.
    They can be restored by setting is_archived=False and clearing archived_at.
    """

    is_archived: Mapped[bool] = mapped_column(
        Integer,  # type: ignore[name-defined]
        nullable=False,
        default=0,
        server_default="0",
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        default=None,
    )

    def soft_delete(self) -> None:
        """Mark this record as archived."""
        self.is_archived = True
        self.archived_at = datetime.now(UTC)


# ─── Type import workaround ─────────────────────────────────────
# SQLAlchemy mapped_column uses String, Integer inline.
# We must import them here for the mixin class bodies to work.
# This is the standard pattern used in SQLAlchemy 2.0 docs.

from sqlalchemy import Integer as _I, String as _S  # noqa: E402, F401

String = _S
Integer = _I
