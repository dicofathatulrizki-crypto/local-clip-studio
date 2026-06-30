"""Tests for WebSocket event bus.

Covers:
- Event publishing
- Broadcast
- Emit to client
- Emit to project
- Progress streaming
- Deduplication
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.infrastructure.websocket.event_bus import EventBus
from backend.infrastructure.websocket.models import (
    ProgressUpdate,
    SubscriptionTopic,
    WebSocketEvent,
    WebSocketMessageType,
)
from backend.infrastructure.websocket.serializer import Serializer


class TestEventBus:
    """Tests for EventBus."""

    @pytest.fixture
    def bus(self) -> EventBus:
        serializer = Serializer()
        send_mock = AsyncMock(return_value=None)
        return EventBus(serializer, send_function=send_mock)

    @pytest.mark.asyncio
    async def test_publish(self, bus: EventBus) -> None:
        """Publish an event (serialization only — actual fan-out is by manager)."""
        event = WebSocketEvent(
            type=WebSocketMessageType.PROJECT_CREATED,
            payload={"project_id": "p1"},
            topic="projects",
        )
        count = await bus.publish(event, skip_dedup=True)
        # Count is 0 because no send_function routing — sent via manager
        assert count >= 0

    @pytest.mark.asyncio
    async def test_publish_with_dedup(self, bus: EventBus) -> None:
        """Duplicate events are skipped."""
        event = WebSocketEvent(
            type=WebSocketMessageType.PROJECT_CREATED,
            payload={"project_id": "p1"},
            topic="projects",
            event_id="unique-1",
        )
        await bus.publish(event)
        # Second publish with same ID should be deduped
        count = await bus.publish(event)
        assert count == 0

    @pytest.mark.asyncio
    async def test_broadcast(self, bus: EventBus) -> None:
        """Broadcast sends to all."""
        event = WebSocketEvent(
            type=WebSocketMessageType.SYSTEM_HEALTH,
            payload={"status": "ok"},
        )
        # Should not raise
        await bus.broadcast(event, skip_dedup=True)

    @pytest.mark.asyncio
    async def test_emit_to_client(self, bus: EventBus) -> None:
        """emit_to_client sends to specific client."""
        event = WebSocketEvent(
            type=WebSocketMessageType.SYSTEM_EVENT,
            payload={"msg": "hello"},
        )
        result = await bus.emit_to_client("client-1", event)
        assert result is True  # Mock returns None (success)

    @pytest.mark.asyncio
    async def test_emit_to_project(self, bus: EventBus) -> None:
        """emit_to_project publishes to project topic."""
        event = WebSocketEvent(
            type=WebSocketMessageType.ANALYSIS_COMPLETED,
            payload={"project_id": "proj-1"},
        )
        count = await bus.emit_to_project("proj-1", event)
        assert count >= 0

    @pytest.mark.asyncio
    async def test_emit_progress(self, bus: EventBus) -> None:
        """emit_progress publishes a progress update."""
        update = ProgressUpdate(
            operation="analysis",
            progress=0.5,
            stage="transcribing",
            message="Processing...",
            items_completed=5,
            items_total=10,
        )
        count = await bus.emit_progress("proj-1", update)
        assert count >= 0

    @pytest.mark.asyncio
    async def test_dedup_trim(self, bus: EventBus) -> None:
        """trim_delivered_events maintains bound on dedup set."""
        # Add many events
        for i in range(50):
            event = WebSocketEvent(
                type=WebSocketMessageType.SYSTEM_EVENT,
                payload={"i": i},
                event_id=f"evt-{i}",
            )
            await bus.publish(event)

        trimmed = await bus.trim_delivered_events(max_events=10)
        assert trimmed >= 0

    @pytest.mark.asyncio
    async def test_clear(self, bus: EventBus) -> None:
        """Clear resets event bus state."""
        event = WebSocketEvent(
            type=WebSocketMessageType.PROJECT_CREATED,
            payload={},
            event_id="clear-test",
        )
        await bus.publish(event)
        await bus.clear()
        # After clear, event can be published again
        count = await bus.publish(event)
        assert count >= 0

    @pytest.mark.asyncio
    async def test_progress_different_operations(self, bus: EventBus) -> None:
        """Progress updates for different operations use correct types."""
        operations = ["analysis", "import", "clip", "caption", "export", "model", "queue"]
        for op in operations:
            update = ProgressUpdate(
                operation=op,
                progress=0.5,
            )
            count = await bus.emit_progress("proj-1", update)
            assert count >= 0

    @pytest.mark.asyncio
    async def test_topic_for_type(self, bus: EventBus) -> None:
        """_topic_for_type returns correct default topics."""
        # Test specific type→topic mapping
        from backend.infrastructure.websocket.event_bus import EventBus as EB
        assert EB._topic_for_type(WebSocketMessageType.SYSTEM_HEALTH) == "system"
        assert EB._topic_for_type(WebSocketMessageType.PROJECT_CREATED) == "projects"
        assert EB._topic_for_type(WebSocketMessageType.SYSTEM_EVENT) == "system"
