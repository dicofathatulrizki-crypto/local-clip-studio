"""
Tests for the logging infrastructure (backend/infrastructure/logging/).

Covers:
- Logger creation
- Correlation ID propagation
- Sensitive data filtering
- Log level configuration
"""

from __future__ import annotations

import io
import json
import logging
from typing import Generator

import pytest
import structlog

from backend.infrastructure.logging.correlation import (
    get_correlation_id,
    get_request_id,
    get_trace_context,
    set_correlation_id,
    set_request_id,
)
from backend.infrastructure.logging.logger import ensure_configured, get_logger, set_log_level


class TestLogger:
    """Verify logger creation and basic functionality."""

    def test_get_logger(self):
        logger = get_logger("test")
        assert logger is not None
        assert isinstance(logger, structlog.stdlib.BoundLogger)

    def test_get_logger_default_name(self):
        logger = get_logger()
        assert logger is not None

    def test_logger_logs_without_error(self):
        """Logging at all levels should not raise exceptions."""
        logger = get_logger("test")
        logger.debug("debug message")
        logger.info("info message")
        logger.warning("warning message")
        logger.error("error message")


class TestCorrelationId:
    """Verify correlation ID propagation."""

    def test_generate_correlation_id(self):
        cid = set_correlation_id()
        assert len(cid) == 36  # UUID4 format
        assert cid.count("-") == 4

    def test_set_and_get_correlation_id(self):
        set_correlation_id("test-cid-123")
        assert get_correlation_id() == "test-cid-123"

    def test_set_and_get_request_id(self):
        set_request_id("test-rid-456")
        assert get_request_id() == "test-rid-456"

    def test_trace_context(self):
        set_correlation_id("cid-trace")
        set_request_id("rid-trace")
        ctx = get_trace_context()
        assert ctx["correlation_id"] == "cid-trace"
        assert ctx["request_id"] == "rid-trace"


class TestLogLevel:
    """Verify log level configuration."""

    def test_set_log_level_valid(self):
        """Setting valid log levels should work."""
        set_log_level("DEBUG")
        set_log_level("INFO")
        set_log_level("WARNING")
        set_log_level("ERROR")

    def test_set_log_level_invalid(self):
        """Setting invalid log level should raise."""
        with pytest.raises(ValueError, match="Invalid log level"):
            set_log_level("INVALID")
