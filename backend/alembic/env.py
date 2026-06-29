"""Alembic environment configuration for Local Clip Studio.

Loads the application's SQLAlchemy models and configures migration
context for both SQLite (default) and PostgreSQL environments.
"""
from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Alembic Config object
config = context.config

# Set up logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import all models so Alembic can detect them
from backend.infrastructure.database.base import Base  # noqa: E402
from backend.infrastructure.database.models import (  # noqa: E402, F401
    Analysis,
    CaptionTrack,
    ClipCandidate,
    ExportJob,
    ModelRegistry,
    ProcessingQueue,
    Project,
    ProjectVideo,
    ProviderConfig,
    SettingsEntry,
    TimelineState,
    VersionSnapshot,
    VideoMaster,
)

target_metadata = Base.metadata


def get_database_url() -> str:
    """Get the database URL from the application settings.

    Falls back to a default SQLite path for standalone migration runs.
    """
    try:
        from backend.config.settings import get_settings

        settings = get_settings()
        db_dir = Path(settings.app_directory) / "projects" / "global"
        db_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{db_dir / 'localclip.db'}"
    except Exception:
        # Fallback for when settings aren't configured
        home = Path.home()
        db_dir = home / ".localclip" / "projects" / "global"
        db_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{db_dir / 'localclip.db'}"


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Configures the context with just a URL and not an Engine.
    Calls to context.execute() here emit the SQL statements.
    """
    url = config.get_main_option("sqlalchemy.url") or get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Creates an Engine and associates a connection with the context.
    """
    # Override sqlalchemy.url in the alembic config
    url = config.get_main_option("sqlalchemy.url") or get_database_url()
    config.set_main_option("sqlalchemy.url", url)

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
