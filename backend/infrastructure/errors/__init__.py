"""Error handling package."""

from backend.infrastructure.errors.app_error import (
    AppError,
    ValidationError,
    NotFoundError,
    ConflictError,
    StorageError,
    FilesystemError,
    PipelineError,
    ExportError,
    PluginError,
    WebSocketError,
    GPUError,
    DatabaseError,
    ConfigurationError,
)

__all__ = [
    "AppError",
    "ValidationError",
    "NotFoundError",
    "ConflictError",
    "StorageError",
    "FilesystemError",
    "PipelineError",
    "ExportError",
    "PluginError",
    "WebSocketError",
    "GPUError",
    "DatabaseError",
    "ConfigurationError",
]
