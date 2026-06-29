"""
Dependency injection configuration for Local Clip Studio.

Uses FastAPI's dependency injection system to provide request-scoped
and application-scoped dependencies to route handlers and services.

All dependencies are wired through this module to provide a single
source of truth for DI configuration.

Usage:
    from fastapi import Depends
    from backend.api.deps import get_settings, get_logger

    @router.get("/")
    async def handler(
        settings=Depends(get_settings),
    ):
        ...
"""

from __future__ import annotations

from typing import AsyncGenerator

from fastapi import FastAPI, Request

from backend.config.settings import Settings, get_settings
from backend.infrastructure.logging.logger import get_logger
from backend.infrastructure.logging.correlation import (
    get_request_id,
    set_correlation_id,
    set_request_id,
)


def configure_di(app: FastAPI) -> None:
    """
    Configure dependency injection for the FastAPI application.

    Registers startup hooks, middleware wrappers, and any
    app-wide state needed for DI resolution.

    Args:
        app: The FastAPI application instance.
    """
    # Register exception handlers
    from backend.api.middleware import (
        app_error_handler,
        catch_all_exceptions,
        validation_exception_handler,
    )
    from fastapi.exceptions import RequestValidationError

    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, catch_all_exceptions)


# ─── Dependency Providers ────────────────────────────────────────────────


async def get_settings_dep() -> Settings:
    """Provide the application settings singleton."""
    return get_settings()


async def get_logger_dep(name: str = "api") -> AsyncGenerator:
    """Provide a request-scoped logger."""
    logger = get_logger(name)
    yield logger


async def request_context(request: Request) -> None:
    """Initialize trace context for the current request."""
    rid = request.headers.get("X-Request-ID")
    if rid:
        set_request_id(rid)
    set_correlation_id()


# ─── Late imports to avoid circular dependencies ─────────────────────────
from backend.infrastructure.errors.app_error import AppError  # noqa: E402
