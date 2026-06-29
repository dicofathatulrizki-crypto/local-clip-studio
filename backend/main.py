"""
FastAPI application entry point for Local Clip Studio.

This module creates and configures the FastAPI application instance.
"""
from __future__ import annotations

from fastapi import FastAPI

from backend.api.middleware import register_middleware
from backend.config.settings import get_settings
from backend.infrastructure.database import init_database
from backend.infrastructure.errors import register_exception_handlers
from backend.infrastructure.logging.logger import configure_logging, get_logger

logger = get_logger(__name__)


_db_manager_ref = None


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    # Configure structured logging
    configure_logging(settings.logging.level)

    app = FastAPI(
        title="Local Clip Studio API",
        description="Local-first AI-powered video editing application",
        version="1.0.0",
        docs_url="/docs" if settings.api.show_docs else None,
        redoc_url="/redoc" if settings.api.show_docs else None,
    )

    # Register middleware (CORS, request ID, timing)
    register_middleware(app)

    # Register exception handlers (AppError, ValueError, Exception)
    register_exception_handlers(app)

    # Startup event
    @app.on_event("startup")
    async def on_startup() -> None:
        logger.info(
            "Application starting",
            extra={
                "version": "1.0.0",
                "api_host": settings.api.host,
                "api_port": settings.api.port,
                "storage_path": str(settings.app_directory),
                "log_level": settings.logging.level,
            },
        )

        # Initialize database on startup
        global _db_manager_ref
        try:
            db = await init_database()
            _db_manager_ref = db
            health = await db.health_check()
            logger.info(
                "Database initialized",
                extra={"health": health},
            )
        except Exception as exc:
            logger.critical(
                "Database initialization failed",
                extra={"error": str(exc)},
            )
            raise

    # Shutdown event
    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        logger.info("Application shutting down")
        global _db_manager_ref
        if _db_manager_ref is not None:
            await _db_manager_ref.shutdown()
            _db_manager_ref = None

    # Root health check
    @app.get("/health")
    async def health_check() -> dict[str, str | dict]:
        from backend.infrastructure.database.engine import get_db_manager

        db = get_db_manager()
        db_health = await db.health_check()

        return {
            "status": "ok",
            "version": "1.0.0",
            "app_name": "Local Clip Studio",
            "database": db_health,
        }

    logger.info("Application created successfully")
    return app


app = create_app()
