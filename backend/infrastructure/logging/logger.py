"""
Structured JSON logging for Local Clip Studio.

Provides a `get_logger()` function that returns a structured logger
configured with:
- JSON output format (for log aggregation)
- ISO 8601 timestamps
- Correlation ID injection
- Sensitive data filtering (API keys, tokens)
- Configurable log levels per module

Usage:
    from backend.infrastructure.logging import get_logger

    logger = get_logger(__name__)
    logger.info("Video import started", video_id="abc-123", file_size_mb=500)
    logger.error("FFmpeg failed", exc_info=True, stderr="...")
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.typing import EventDict

from backend.config.settings import get_settings
from backend.infrastructure.logging.correlation import get_trace_context

# ─── Constants ────────────────────────────────────────────────────────────

_SENSITIVE_KEYS: frozenset[str] = frozenset({
    "api_key",
    "api_key",
    "password",
    "secret",
    "token",
    "auth_token",
    "access_token",
    "refresh_token",
    "private_key",
    "encryption_key",
})

# ─── Processors ───────────────────────────────────────────────────────────


def _add_timestamp(_: logging.Logger, __: str, event_dict: EventDict) -> EventDict:
    """Add ISO 8601 timestamp to every log entry."""
    from datetime import datetime, timezone

    event_dict["timestamp"] = datetime.now(timezone.utc).isoformat()
    return event_dict


def _add_trace_context(_: logging.Logger, __: str, event_dict: EventDict) -> EventDict:
    """Inject correlation ID and request ID from context."""
    trace = get_trace_context()
    event_dict.update(trace)
    return event_dict


def _filter_sensitive_fields(_: logging.Logger, __: str, event_dict: EventDict) -> EventDict:
    """Mask sensitive fields like API keys and tokens."""
    for key in list(event_dict.keys()):
        if key.lower() in _SENSITIVE_KEYS:
            event_dict[key] = "***"
    return event_dict


def _format_exc_info(_: logging.Logger, __: str, event_dict: EventDict) -> EventDict:
    """Format exception info as a string for JSON serialization."""
    exc_info = event_dict.pop("exc_info", None)
    if exc_info and not isinstance(exc_info, bool):
        event_dict["exception"] = _serialize_exception(exc_info)
    elif exc_info and isinstance(exc_info, bool):
        # structlog will handle this via the format_exc_info processor
        pass
    return event_dict


def _serialize_exception(exc_info: tuple[type, BaseException, object]) -> dict | None:
    """Serialize exception info to a dict for structured logging."""
    exc_type, exc_value, _traceback = exc_info
    return {
        "type": exc_type.__name__,
        "message": str(exc_value),
        "module": exc_type.__module__,
    }


# ─── Logger Configuration ────────────────────────────────────────────────


def _configure_structlog(log_level: str) -> None:
    """
    Configure structlog with JSON output and our custom processors.

    Args:
        log_level: One of DEBUG, INFO, WARNING, ERROR, CRITICAL.
    """
    structlog.configure(
        processors=[
            _add_timestamp,
            _add_trace_context,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            _filter_sensitive_fields,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            _format_exc_info,
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer() if log_level == "DEBUG" else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def _configure_stdlib_logging(log_level: str) -> None:
    """Configure Python's standard logging to work with structlog."""
    level = getattr(logging, log_level.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Disable noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


# ─── Public API ───────────────────────────────────────────────────────────


_initialized: bool = False


def ensure_configured() -> None:
    """Ensure logging is configured. Safe to call multiple times."""
    global _initialized
    if _initialized:
        return

    settings = get_settings()
    log_level = settings.log_level
    _configure_structlog(log_level)
    _configure_stdlib_logging(log_level)
    _initialized = True


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger for the given module name.

    Args:
        name: Typically ``__name__`` from the calling module.
              Falls back to 'root' if not provided.

    Returns:
        A structured logger with bound context methods.
    """
    ensure_configured()
    return structlog.get_logger(name or "root")


def get_log_level() -> str:
    """Get the currently configured log level."""
    return get_settings().log_level


def set_log_level(level: str) -> None:
    """Dynamically change the log level at runtime."""
    level = level.upper()
    if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ValueError(f"Invalid log level: {level}")

    logging.getLogger().setLevel(getattr(logging, level))
    # Force re-configuration on next get_logger call
    global _initialized
    _initialized = False
    ensure_configured()
