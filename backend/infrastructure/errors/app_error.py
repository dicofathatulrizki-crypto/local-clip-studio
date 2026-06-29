"""
Application error framework for Local Clip Studio.

All application errors inherit from `AppError` and carry:
- Unique error code (e.g., ERR-IMP-001)
- Human-readable user message
- Detailed debug context
- Suggested recovery steps
- HTTP status code mapping
- Severity level for logging
"""

from __future__ import annotations

from typing import Any

from backend.infrastructure.logging.correlation import get_trace_context


class AppError(Exception):
    """
    Base application error with structured context.

    Every error in the application should use AppError or a subclass
    rather than bare Exception or ValueError. This ensures consistent
    error handling, logging, and user-facing messages.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 500,
        details: dict[str, Any] | None = None,
        recovery: str | None = None,
        severity: str = "ERROR",
        cause: Exception | None = None,
    ) -> None:
        """
        Initialize an application error.

        Args:
            code: Machine-readable error code (e.g., 'ERR-IMP-001').
            message: Human-readable error message for the user.
            status_code: HTTP status code (for API responses).
            details: Additional context for debugging.
            recovery: Suggested action for the user to resolve the error.
            severity: Log severity: 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'.
            cause: The original exception that caused this error (if any).
        """
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        self.recovery = recovery
        self.severity = severity
        self.cause = cause
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """Convert error to a JSON-serializable dictionary for API responses."""
        result: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
        }
        if self.details:
            result["details"] = self.details
        if self.recovery:
            result["recovery"] = self.recovery

        # Include trace context
        trace = get_trace_context()
        result.update(trace)

        return result

    def to_log_dict(self) -> dict[str, Any]:
        """Convert error to a structured dict for logging."""
        result = self.to_dict()
        result["severity"] = self.severity
        result["status_code"] = self.status_code
        if self.cause:
            result["cause"] = f"{type(self.cause).__name__}: {self.cause}"
        return result

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(code={self.code!r}, message={self.message!r})"


# ─── Specific Error Types ─────────────────────────────────────────────────


class ValidationError(AppError):
    """Input validation error (HTTP 400)."""

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        recovery: str | None = None,
    ) -> None:
        super().__init__(
            code="ERR-VALIDATION-001",
            message=message,
            status_code=400,
            details=details,
            recovery=recovery,
            severity="WARNING",
        )


class ImportError(AppError):
    """Video import error (HTTP 4xx)."""

    _code_counter: int = 0

    def __init__(
        self,
        code_suffix: str,
        message: str,
        *,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
        recovery: str | None = None,
        severity: str = "WARNING",
    ) -> None:
        super().__init__(
            code=f"ERR-IMP-{code_suffix}",
            message=message,
            status_code=status_code,
            details=details,
            recovery=recovery,
            severity=severity,
        )


class PipelineError(AppError):
    """AI pipeline execution error (HTTP 500)."""

    def __init__(
        self,
        code_suffix: str,
        message: str,
        *,
        stage: str | None = None,
        details: dict[str, Any] | None = None,
        recovery: str | None = None,
        severity: str = "ERROR",
        cause: Exception | None = None,
    ) -> None:
        merged_details = dict(details or {})
        if stage:
            merged_details["stage"] = stage
        super().__init__(
            code=f"ERR-PIPE-{code_suffix}",
            message=message,
            status_code=500,
            details=merged_details,
            recovery=recovery,
            severity=severity,
            cause=cause,
        )


class ExportError(AppError):
    """Video export error (HTTP 500)."""

    def __init__(
        self,
        code_suffix: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        recovery: str | None = None,
    ) -> None:
        super().__init__(
            code=f"ERR-EXP-{code_suffix}",
            message=message,
            status_code=500,
            details=details,
            recovery=recovery,
            severity="ERROR",
        )


class NotFoundError(AppError):
    """Resource not found (HTTP 404)."""

    def __init__(
        self,
        resource_type: str,
        resource_id: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code="ERR-NOTFOUND-001",
            message=f"{resource_type} not found: {resource_id}",
            status_code=404,
            details={"resource_type": resource_type, "resource_id": resource_id, **(details or {})},
            recovery="Verify the resource ID is correct.",
            severity="WARNING",
        )


class ConflictError(AppError):
    """Resource conflict (HTTP 409)."""

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        recovery: str | None = None,
    ) -> None:
        super().__init__(
            code="ERR-CONFLICT-001",
            message=message,
            status_code=409,
            details=details,
            recovery=recovery,
            severity="WARNING",
        )


class StorageError(AppError):
    """Storage-related error (HTTP 500 or 507)."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 507,
        details: dict[str, Any] | None = None,
        recovery: str | None = None,
    ) -> None:
        super().__init__(
            code="ERR-STORAGE-001",
            message=message,
            status_code=status_code,
            details=details,
            recovery=recovery,
            severity="ERROR",
        )


class SystemError(AppError):
    """System-level error (HTTP 503)."""

    def __init__(
        self,
        code_suffix: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        recovery: str | None = None,
        severity: str = "CRITICAL",
    ) -> None:
        super().__init__(
            code=f"ERR-SYS-{code_suffix}",
            message=message,
            status_code=503,
            details=details,
            recovery=recovery,
            severity=severity,
        )


class SecurityError(AppError):
    """Security violation (HTTP 403)."""

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code="ERR-SEC-001",
            message=message,
            status_code=403,
            details=details,
            recovery="This operation was blocked for security reasons.",
            severity="CRITICAL",
        )


class PluginError(AppError):
    """Plugin-related error (HTTP 500)."""

    def __init__(
        self,
        code_suffix: str,
        message: str,
        *,
        plugin_name: str | None = None,
        details: dict[str, Any] | None = None,
        recovery: str | None = None,
    ) -> None:
        merged_details = dict(details or {})
        if plugin_name:
            merged_details["plugin"] = plugin_name
        super().__init__(
            code=f"ERR-PLUG-{code_suffix}",
            message=message,
            status_code=500,
            details=merged_details,
            recovery=recovery,
            severity="ERROR",
        )
