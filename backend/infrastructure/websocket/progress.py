"""Progress streaming helpers for pipeline stage updates.

Provides typed helpers for consistent progress reporting across
all pipeline stages (import, analysis, clip, caption, export, model download).

No business logic — pure infrastructure for structured progress updates.
"""

from __future__ import annotations

from typing import Any

from backend.infrastructure.websocket.models import (
    ProgressUpdate,
    WebSocketEvent,
    WebSocketMessageType,
)


class ProgressStream:
    """Helper for streaming progress updates for a long-running operation.

    Provides a consistent interface for pipeline stages to report progress.
    Each stage creates its own ProgressStream and calls update() as work
    progresses.

    Usage:
        stream = ProgressStream("analysis", project_id="proj-1")
        stream.start(stage="transcribing", total_items=100)
        stream.advance(items=10)
        stream.complete()
    """

    def __init__(
        self,
        operation: str,
        project_id: str = "",
        topic: str = "",
    ) -> None:
        self.operation = operation
        self.project_id = project_id
        self.topic = topic
        self._current_stage = ""
        self._progress = 0.0
        self._stage_progress: float | None = None
        self._items_completed = 0
        self._items_total = 0
        self._message = ""
        self._started = False
        self._completed = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(
        self,
        stage: str = "",
        total_items: int = 0,
        message: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ProgressUpdate:
        """Start or advance to a new stage.

        Args:
            stage: Stage name (e.g., 'transcribing', 'scoring')
            total_items: Total items to process in this stage
            message: Human-readable status message
            metadata: Additional metadata

        Returns:
            ProgressUpdate with progress=0
        """
        self._current_stage = stage
        self._items_total = total_items
        self._items_completed = 0
        self._stage_progress = 0.0
        self._message = message or f"Starting {stage}"
        self._started = True

        return self._build_update(metadata=metadata)

    def advance(
        self,
        items: int = 1,
        message: str = "",
        stage_progress: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ProgressUpdate:
        """Advance progress by a number of completed items.

        Args:
            items: Number of items completed
            message: Updated status message
            stage_progress: Override stage progress (0.0-1.0)
            metadata: Additional metadata

        Returns:
            ProgressUpdate with updated progress
        """
        self._items_completed += items

        if self._items_total > 0:
            self._stage_progress = stage_progress or (
                self._items_completed / self._items_total
            )

        if message:
            self._message = message

        return self._build_update(metadata=metadata)

    def set_progress(
        self,
        progress: float,
        message: str = "",
        stage_progress: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ProgressUpdate:
        """Set overall progress directly (0.0–1.0).

        Args:
            progress: Overall progress (0.0-1.0)
            message: Updated status message
            stage_progress: Current stage progress (0.0-1.0)
            metadata: Additional metadata

        Returns:
            ProgressUpdate
        """
        self._progress = max(0.0, min(1.0, progress))
        if message:
            self._message = message
        if stage_progress is not None:
            self._stage_progress = stage_progress

        return self._build_update(metadata=metadata)

    def complete(
        self,
        message: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ProgressUpdate:
        """Mark the operation as complete.

        Args:
            message: Completion message
            metadata: Additional metadata

        Returns:
            ProgressUpdate with progress=1.0
        """
        self._progress = 1.0
        self._stage_progress = 1.0
        self._items_completed = self._items_total
        self._message = message or "Complete"
        self._completed = True

        return self._build_update(metadata=metadata)

    def fail(
        self,
        error_message: str,
        metadata: dict[str, Any] | None = None,
    ) -> ProgressUpdate:
        """Mark the operation as failed.

        Args:
            error_message: Error description
            metadata: Additional metadata

        Returns:
            ProgressUpdate with error info
        """
        self._message = error_message
        self._completed = True

        update = self._build_update(metadata=metadata)
        update.error_message = error_message
        return update

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    def to_websocket_event(self) -> WebSocketEvent:
        """Convert current progress to a WebSocketEvent for publishing.

        Returns:
            WebSocketEvent with appropriate message type
        """
        update = self._build_update()
        type_map = {
            "analysis": WebSocketMessageType.ANALYSIS_PROGRESS,
            "import": WebSocketMessageType.VIDEO_IMPORT_PROGRESS,
            "clip": WebSocketMessageType.CLIP_GENERATION_PROGRESS,
            "caption": WebSocketMessageType.CAPTION_GENERATION_PROGRESS,
            "export": WebSocketMessageType.EXPORT_PROGRESS,
            "model": WebSocketMessageType.MODEL_DOWNLOAD_PROGRESS,
            "queue": WebSocketMessageType.QUEUE_JOB_PROGRESS,
        }
        msg_type = type_map.get(self.operation, WebSocketMessageType.SYSTEM_EVENT)

        return WebSocketEvent(
            type=msg_type,
            payload={
                "operation": self.operation,
                "progress": update.progress,
                "stage": update.stage,
                "message": update.message,
                "stage_progress": update.stage_progress,
                "estimated_remaining_seconds": update.estimated_remaining_seconds,
                "items_completed": update.items_completed,
                "items_total": update.items_total,
                "error_message": update.error_message,
                "metadata": update.metadata,
            },
            topic=self.topic,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_update(
        self,
        metadata: dict[str, Any] | None = None,
    ) -> ProgressUpdate:
        """Build a ProgressUpdate from current state."""
        return ProgressUpdate(
            operation=self.operation,
            progress=self._progress,
            stage=self._current_stage,
            message=self._message,
            stage_progress=self._stage_progress,
            items_completed=self._items_completed,
            items_total=self._items_total,
            metadata=metadata or {},
        )
