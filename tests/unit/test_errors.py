"""
Tests for the error handling framework (backend/infrastructure/errors/).

Covers:
- AppError creation with all fields
- Each error subclass
- Error serialization to dict
- HTTP status code mapping
"""

from __future__ import annotations

import pytest

from backend.infrastructure.errors import (
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


class TestAppError:
    """Verify base AppError behavior."""

    def test_create_minimal(self):
        error = AppError(code="ERR-TEST-001", message="Test error")
        assert error.code == "ERR-TEST-001"
        assert error.message == "Test error"
        assert error.status_code == 500
        assert error.details == {}
        assert error.recovery is None
        assert error.severity == "ERROR"

    def test_create_full(self):
        error = AppError(
            code="ERR-TEST-002",
            message="Full error",
            status_code=400,
            details={"field": "name"},
            recovery="Provide a valid name.",
            severity="WARNING",
        )
        assert error.status_code == 400
        assert error.details == {"field": "name"}
        assert error.recovery == "Provide a valid name."

    def test_to_dict(self):
        error = AppError(code="ERR-TEST-003", message="Dict test", details={"key": "val"})
        d = error.to_dict()
        assert d["code"] == "ERR-TEST-003"
        assert d["message"] == "Dict test"
        assert d["details"] == {"key": "val"}

    def test_to_log_dict(self):
        error = AppError(code="ERR-TEST-004", message="Log test")
        d = error.to_log_dict()
        assert d["severity"] == "ERROR"
        assert d["status_code"] == 500

    def test_repr(self):
        error = AppError(code="ERR-TEST-005", message="Repr test")
        r = repr(error)
        assert "AppError" in r
        assert "ERR-TEST-005" in r


class TestErrorSubclasses:
    """Verify each error subclass has correct defaults."""

    def test_validation_error(self):
        error = ValidationError("Invalid input", details={"field": "name"})
        assert error.status_code == 400
        assert error.code == "ERR-VALIDATION-001"
        assert "Invalid input" in str(error)

    def test_not_found_error(self):
        error = NotFoundError("Project", "uuid-123")
        assert error.status_code == 404
        assert error.code == "ERR-NOTFOUND-001"
        assert "Project" in error.message
        assert "uuid-123" in error.message

    def test_conflict_error(self):
        error = ConflictError("Already analyzing", recovery="Wait for completion")
        assert error.status_code == 409
        assert error.code == "ERR-CONFLICT-001"
        assert error.recovery is not None

    def test_import_error(self):
        error = ImportError("001", "Unsupported format", details={"format": ".wmv"})
        assert error.code == "ERR-IMP-001"
        assert error.status_code == 400

    def test_pipeline_error(self):
        error = PipelineError("001", "STT failed", stage="transcribing", recovery="Restart pipeline")
        assert error.code == "ERR-PIPE-001"
        assert error.details.get("stage") == "transcribing"
        assert error.recovery is not None

    def test_export_error(self):
        error = ExportError("001", "Encoding failed", details={"codec": "h265"})
        assert error.code == "ERR-EXP-001"
        assert error.status_code == 500

    def test_storage_error(self):
        error = StorageError("Disk full", details={"required_gb": 10, "available_gb": 2})
        assert error.code == "ERR-STORAGE-001"
        assert error.status_code == 507

    def test_system_error(self):
        error = SystemError("001", "FFmpeg not found", recovery="Install FFmpeg")
        assert error.code == "ERR-SYS-001"
        assert error.status_code == 503
        assert error.severity == "CRITICAL"

    def test_security_error(self):
        error = SecurityError("Path traversal detected", details={"path": "../etc"})
        assert error.code == "ERR-SEC-001"
        assert error.status_code == 403

    def test_plugin_error(self):
        error = PluginError("001", "Plugin crashed", plugin_name="whisperx")
        assert error.code == "ERR-PLUG-001"
        assert error.details.get("plugin") == "whisperx"
