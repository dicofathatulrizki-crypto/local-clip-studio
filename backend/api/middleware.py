"""
Middleware and exception handlers for the FastAPI application.

Provides:
- Request ID injection and propagation
- Structured error responses for all error types
- CORS configuration (already in main.py)
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from backend.infrastructure.errors.app_error import AppError
from backend.infrastructure.logging.correlation import get_trace_context, set_request_id
from backend.infrastructure.logging.logger import get_logger


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware that ensures every request has a unique request ID.

    If the client provides an X-Request-ID header, it is used.
    Otherwise, a new UUID is generated. The ID is set in the
    trace context and echoed back in the response header.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        rid = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        set_request_id(rid)

        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """
    Handle known application errors with structured responses.

    Returns:
        JSON response with error code, message, details, and trace context.
    """
    logger = get_logger("api.error")
    log_method = getattr(logger, exc.severity.lower(), logger.error)
    log_method(
        exc.message,
        error_code=exc.code,
        status_code=exc.status_code,
        details=exc.details,
        path=str(request.url.path),
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.to_dict(),
            "request_id": get_trace_context().get("request_id", ""),
        },
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Handle Pydantic/FastAPI validation errors.

    Returns:
        JSON response with field-level validation error details.
    """
    logger = get_logger("api.validation")
    errors = exc.errors()

    logger.warning(
        "Request validation failed",
        path=str(request.url.path),
        error_count=len(errors),
    )

    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "ERR-VALIDATION-001",
                "message": "Request validation failed",
                "details": {"errors": errors},
                **get_trace_context(),
            },
            "request_id": get_trace_context().get("request_id", ""),
        },
    )


async def catch_all_exceptions(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all exception handler for unexpected errors.

    Returns:
        Generic 500 error response. The real error details are
        logged and not exposed to the user for security reasons.
    """
    logger = get_logger("api.error")
    logger.critical(
        "Unhandled exception",
        exc_info=exc,
        path=str(request.url.path),
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "ERR-SYS-000",
                "message": "An unexpected error occurred. Check the logs for details.",
                "recovery": "Restart the application and try again. If the error persists, check the logs.",
                **get_trace_context(),
            },
            "request_id": get_trace_context().get("request_id", ""),
        },
    )
