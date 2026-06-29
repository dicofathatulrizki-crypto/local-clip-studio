"""
Correlation ID propagation for request tracing.

Each incoming request gets a unique correlation ID that is propagated
through all service calls, Celery tasks, and subprocess invocations.
This enables end-to-end tracing of operations.

Usage:
    from backend.infrastructure.logging.correlation import (
        get_correlation_id,
        set_correlation_id,
    )

    # In middleware:
    set_correlation_id(request.headers.get("X-Request-ID"))

    # In services:
    cid = get_correlation_id()
    logger.info("Processing video", correlation_id=cid)
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from typing import Any

# Context variable for async-safe correlation ID propagation
_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")
_request_id: ContextVar[str] = ContextVar("request_id", default="")


def generate_id() -> str:
    """Generate a new UUID4-based correlation ID."""
    return str(uuid.uuid4())


def get_correlation_id() -> str:
    """Get the current correlation ID, or empty string if not set."""
    return _correlation_id.get()


def set_correlation_id(cid: str | None = None) -> str:
    """
    Set the correlation ID for the current context.

    Args:
        cid: Correlation ID to set. If None, generates a new one.

    Returns:
        The correlation ID that was set.
    """
    if not cid:
        cid = generate_id()
    _correlation_id.set(cid)
    return cid


def get_request_id() -> str:
    """Get the current request ID, or empty string if not set."""
    return _request_id.get()


def set_request_id(rid: str | None = None) -> str:
    """
    Set the request ID for the current context.

    Args:
        rid: Request ID to set. If None, generates a new one.

    Returns:
        The request ID that was set.
    """
    if not rid:
        rid = generate_id()
    _request_id.set(rid)
    return rid


def get_trace_context() -> dict[str, str]:
    """Get all trace context values as a dictionary."""
    ctx: dict[str, str] = {}
    corr_id = get_correlation_id()
    req_id = get_request_id()
    if corr_id:
        ctx["correlation_id"] = corr_id
    if req_id:
        ctx["request_id"] = req_id
    return ctx


def with_trace_context(extra: dict[str, Any] | None = None) -> dict[str, str]:
    """Get trace context merged with optional extra fields."""
    ctx = get_trace_context()
    if extra:
        ctx.update(extra)
    return ctx
