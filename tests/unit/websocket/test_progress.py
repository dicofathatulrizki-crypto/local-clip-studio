"""Tests for WebSocket progress streaming.

Covers:
- ProgressStream lifecycle
- Start, advance, set_progress, complete, fail
- Progress bounds
- Conversion to WebSocketEvent
"""

from __future__ import annotations

import pytest

from backend.infrastructure.websocket.models import WebSocketMessageType
from backend.infrastructure.websocket.progress import ProgressStream


class TestProgressStream:
    """Tests for ProgressStream."""

    def test_start(self) -> None:
        """Start creates initial progress update."""
        stream = ProgressStream("analysis", project_id="proj-1")
        update = stream.start(stage="transcribing", total_items=100, message="Starting")
        assert update.operation == "analysis"
        assert update.progress == 0.0
        assert update.stage == "transcribing"
        assert update.items_total == 100
        assert update.items_completed == 0

    def test_advance(self) -> None:
        """Advance increments completed items and progress."""
        stream = ProgressStream("import", project_id="proj-1")
        stream.start(stage="copying", total_items=10)
        update = stream.advance(items=5, message="5 of 10 copied")
        assert update.items_completed == 5
        assert update.items_total == 10
        assert update.stage_progress is not None and update.stage_progress > 0

    def test_advance_complete(self) -> None:
        """Advancing all items reaches 100%."""
        stream = ProgressStream("export", project_id="proj-1")
        stream.start(stage="encoding", total_items=10)
        stream.advance(items=10)
        update = stream.complete()
        assert update.progress == 1.0
        assert update.stage_progress == 1.0
        assert update.message == "Complete"

    def test_set_progress(self) -> None:
        """set_progress sets overall progress directly."""
        stream = ProgressStream("clip", project_id="proj-1")
        stream.start(total_items=50)
        update = stream.set_progress(0.75, message="75% done")
        assert update.progress == 0.75
        assert update.message == "75% done"

    def test_set_progress_clamps(self) -> None:
        """set_progress clamps values to 0.0-1.0."""
        stream = ProgressStream("test")
        update = stream.set_progress(1.5)
        assert update.progress <= 1.0
        update = stream.set_progress(-0.5)
        assert update.progress >= 0.0

    def test_fail(self) -> None:
        """Fail marks the operation with an error."""
        stream = ProgressStream("caption", project_id="proj-1")
        stream.start(total_items=10)
        update = stream.fail("Translation failed")
        assert update.error_message == "Translation failed"

    def test_to_websocket_event(self) -> None:
        """to_websocket_event creates a typed WebSocketEvent."""
        stream = ProgressStream("analysis", project_id="proj-1")
        stream.start(stage="scoring", total_items=5)
        stream.advance(items=3)

        event = stream.to_websocket_event()
        assert event.type == WebSocketMessageType.ANALYSIS_PROGRESS
        assert event.payload["operation"] == "analysis"
        assert event.payload["progress"] >= 0
        assert event.payload["stage"] == "scoring"

    def test_multiple_stages(self) -> None:
        """ProgressStream supports multiple stages."""
        stream = ProgressStream("analysis", project_id="proj-1")

        # Stage 1
        stream.start(stage="transcribing", total_items=100, message="Transcribing")
        stream.advance(items=100)
        assert stream._completed is False

        # Stage 2
        stream.start(stage="scoring", total_items=50, message="Scoring")
        stream.advance(items=50)
        stream.complete()
        assert stream._completed is True
        assert stream._progress == 1.0

    def test_export_event_type(self) -> None:
        """Export operation maps to EXPORT_PROGRESS type."""
        stream = ProgressStream("export", project_id="proj-1")
        event = stream.to_websocket_event()
        assert event.type == WebSocketMessageType.EXPORT_PROGRESS

    def test_queue_event_type(self) -> None:
        """Queue operation maps to QUEUE_JOB_PROGRESS type."""
        stream = ProgressStream("queue", project_id="proj-1")
        event = stream.to_websocket_event()
        assert event.type == WebSocketMessageType.QUEUE_JOB_PROGRESS

    def test_unknown_operation_defaults(self) -> None:
        """Unknown operation maps to SYSTEM_EVENT."""
        stream = ProgressStream("unknown_op", project_id="proj-1")
        event = stream.to_websocket_event()
        assert event.type == WebSocketMessageType.SYSTEM_EVENT

    def test_complete_with_message(self) -> None:
        """Complete with custom message."""
        stream = ProgressStream("import", project_id="proj-1")
        stream.start(total_items=5)
        stream.advance(items=5)
        update = stream.complete(message="Import finished successfully")
        assert update.message == "Import finished successfully"
        assert update.progress == 1.0
