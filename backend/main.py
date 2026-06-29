"""
Application entry point for Local Clip Studio.

Initializes the FastAPI application, configures middleware,
registers routes, and starts the uvicorn server.
"""

import argparse
import sys

import uvicorn

from backend.config.settings import get_settings


def create_app() -> "FastAPI":
    """Create and configure the FastAPI application instance."""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    from backend.api.deps import configure_di
    from backend.api.middleware import RequestIDMiddleware, catch_all_exceptions
    from backend.config.settings import Settings
    from backend.infrastructure.logging.logger import get_logger

    settings = get_settings()
    logger = get_logger(__name__)

    app = FastAPI(
        title="Local Clip Studio API",
        version="1.0.0",
        description="Local-first AI-powered video clipping API",
        docs_url="/api/docs" if settings.debug else None,
        redoc_url="/api/redoc" if settings.debug else None,
        openapi_url="/api/openapi.json" if settings.debug else None,
    )

    # CORS — allow frontend dev server and static builds
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",  # Vite dev server
            "http://127.0.0.1:5173",
            "http://localhost:8765",  # Same-origin for static files
        ],
        allow_credentials=False,  # No cookies/auth
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Custom middleware
    app.add_middleware(RequestIDMiddleware)

    # Exception handler
    app.add_exception_handler(Exception, catch_all_exceptions)

    # Configure dependency injection
    configure_di(app)

    # Startup / shutdown events
    @app.on_event("startup")
    async def on_startup() -> None:
        logger.info(
            "Application starting",
            version="1.0.0",
            storage_path=str(settings.storage_path),
            gpu_backend=settings.gpu.backend,
        )
        await _initialize_infrastructure(app, settings)

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        logger.info("Application shutting down")
        await _shutdown_infrastructure(app)

    # Health check endpoint (no dependencies)
    @app.get("/api/v1/system/ping")
    async def ping():
        return {"status": "ok", "version": "1.0.0"}

    return app


async def _initialize_infrastructure(app: "FastAPI", settings: "Settings") -> None:
    """Initialize all infrastructure components on startup."""
    from backend.infrastructure.logging.logger import get_logger

    logger = get_logger(__name__)

    try:
        # Initialize database
        from backend.infrastructure.database.engine import create_database

        engine = await create_database(settings)
        app.state.db_engine = engine
        logger.info("Database initialized")

        # Initialize filesystem
        from backend.infrastructure.filesystem.project_dirs import ensure_directories

        await ensure_directories(settings)
        logger.info("Filesystem directories initialized")

        # Initialize HAL (GPU detection)
        from backend.infrastructure.hal.registry import HALRegistry

        hal = HALRegistry()
        await hal.initialize(settings)
        app.state.hal = hal
        logger.info(
            "HAL initialized",
            backend=hal.active_backend,
            device=hal.device_name if hal.active_backend != "cpu" else "cpu",
        )

        logger.info("Infrastructure initialization complete")

    except Exception as exc:
        logger.critical("Infrastructure initialization failed", exc_info=exc)
        raise


async def _shutdown_infrastructure(app: "FastAPI") -> None:
    """Cleanly shut down all infrastructure components."""
    from backend.infrastructure.logging.logger import get_logger

    logger = get_logger(__name__)

    if hasattr(app.state, "db_engine") and app.state.db_engine:
        await app.state.db_engine.dispose()
        logger.info("Database engine disposed")

    if hasattr(app.state, "hal") and app.state.hal:
        await app.state.hal.shutdown()
        logger.info("HAL shut down")


def main() -> None:
    """CLI entry point for starting the server."""
    parser = argparse.ArgumentParser(description="Local Clip Studio Backend")
    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="Host to bind to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port to bind to (default: 8765)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        default=False,
        help="Enable auto-reload for development",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level",
    )

    args = parser.parse_args()
    settings = get_settings()

    host = args.host or settings.host
    port = args.port or settings.port
    log_level = (args.log_level or settings.log_level).lower()

    uvicorn.run(
        "backend.main:create_app",
        host=host,
        port=port,
        reload=args.reload,
        log_level=log_level,
        factory=True,
    )


def cli_entry() -> None:
    """Entry point for the `localclip` console script."""
    main()


if __name__ == "__main__":
    main()
