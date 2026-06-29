"""Application error handling framework.

Provides `AppError` and typed error subclasses that carry:
- Machine-readable error code (e.g., ERR-IMP-001)
- Human-readable user message
- Detailed context for debugging
- HTTP status code mapping
- Suggested recovery actions
"""

from backend.infrastructure.errors.app_error import (
    AppError,
    ConflictError,
    ExportError,
    ImportError,
    NotFoundError,
    PipelineError,
    PluginError,
    SecurityError,
    StorageError,
    SystemError,
    ValidationError,
)

__all__ = [
    "AppError",
    "ConflictError",
    "ExportError",
    "ImportError",
    "NotFoundError",
    "PipelineError",
    "PluginError",
    "SecurityError",
    "StorageError",
    "SystemError",
    "ValidationError",
]
