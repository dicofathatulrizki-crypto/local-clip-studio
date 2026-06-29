"""Database infrastructure for Local Clip Studio.

Provides:
- SQLAlchemy 2.0 engine and session management
- Declarative base model with common mixins (UUID, Timestamps, SoftDelete)
- All ORM models (13 entities)
- Repository pattern for data access
- Alembic migration support
"""
from __future__ import annotations

from backend.infrastructure.database.base import Base
from backend.infrastructure.database.engine import (
    DatabaseManager,
    create_engine,
    get_db_session,
    get_sync_db_session,
    init_database,
)

__all__ = [
    "Base",
    "DatabaseManager",
    "create_engine",
    "get_db_session",
    "get_sync_db_session",
    "init_database",
]
