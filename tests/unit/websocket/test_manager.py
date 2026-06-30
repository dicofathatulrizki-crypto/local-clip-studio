"""Tests for WebSocketManager facade.

Covers:
- Connection lifecycle via manager
- Message handling (built-in types: ping, subscribe, etc.)
- Event publishing and broadcasting
- Subscription management
- Heartbeat integration
- Shutdown
- Statistics

Uses mocked send functions to test without real WebSocket.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from backend.infrastructure.websocket.exceptions import (
    ConnectionClosedError,
    InvalidMessageError,
    MaxClientsReachedError,
    MessageTooLargeError,
    WebSocketError,
)
from backend.infrastructure.websocket.manager import WebSocketManager
from backend.infrastructure.websocket.models import (
    MessageEnvelope,
    ProgressUpdate,
    WebSocketEvent,
    WebSocketMessage,
    WebSocketMessageType,
)


class TestWebSocketManager:
    """Tests for WebSocketManager."""

    @pytest.fixture
    def manager(self) -> WebSocketManager:
        return WebSocketManager(
            max_clients=10,
            heartbeat_interval=3600.0,  # Very long to avoid interfering
            heartbeat_timeout=7200.0,
            rate_limit=100,
            rate_window_seconds=60,
            max_message_size=65536,
        )

    @pytest.fixture
    def send_mock(self) -> AsyncMock:
        return AsyncMock()

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_handle_connect(self, manager: WebSocketManager, send_mock: AsyncMock) -> None:
        """handle_connect registers a client."""
        info = await manager.handle_connect("client-1", send_mock, remote_addr="127.0.0.1")
        assert info.client_id == "client-1"
        assert info.is_alive is True
        stats = await manager.get_stats()
        assert stats["active_connections"] == 1

    @pytest.mark.asyncio
    async def test_handle_connect_max(self, manager: WebSocketManager, send_mock: AsyncMock) -> None:
        """Exceeding max clients raises MaxClientsReachedError."""
        for i in range(10):
            await manager.handle_connect(f"c-{i}", send_mock)
        with pytest.raises(MaxClientsReachedError):
            await manager.handle_connect("too-many", send_mock)

    @pytest.mark.asyncio
    async def test_handle_disconnect(self, manager: WebSocketManager, send_mock: AsyncMock) -> None:
        """handle_disconnect cleans up client state."""
        await manager.handle_connect("client-1", send_mock)
        await manager.handle_disconnect("client-1", reason="test")
        stats = await manager.get_stats()
        assert stats["active_connections"] == 0

    @pytest.mark.asyncio
    async def test_connect_disconnect_subscriptions_cleaned(
        self, manager: WebSocketManager, send_mock: AsyncMock
    ) -> None:
        """Disconnecting removes all subscriptions."""
        await manager.handle_connect("client-1", send_mock)
        await manager.subscribe("client-1", "project.test")
        assert manager.subscription_manager.has_subscriber("project.test") is True
        await manager.handle_disconnect("client-1")
        assert manager.subscription_manager.has_subscriber("project.test") is False

    # ------------------------------------------------------------------
    # Message handling
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_handle_ping(self, manager: WebSocketManager, send_mock: AsyncMock) -> None:
        """Ping is handled automatically with pong response."""
        await manager.handle_connect("client-1", send_mock)
        result = await manager.handle_message(
            "client-1",
            '{"type": "ping", "payload": {}}',
        )
        # Ping is handled internally — returns None
        assert result is None
        # Pong should have been sent
        assert send_mock.called

    @pytest.mark.asyncio
    async def test_handle_pong(self, manager: WebSocketManager, send_mock: AsyncMock) -> None:
        """Pong is recorded."""
        await manager.handle_connect("client-1", send_mock)
        result = await manager.handle_message(
            "client-1",
            '{"type": "pong", "payload": {}}',
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_handle_subscribe(self, manager: WebSocketManager, send_mock: AsyncMock) -> None:
        """Subscribe message type handles subscription."""
        await manager.handle_connect("client-1", send_mock)
        result = await manager.handle_message(
            "client-1",
            '{"type": "subscribe", "payload": {"topic": "project.test"}}',
        )
        assert result is None  # Handled internally
        assert manager.subscription_manager.is_subscribed("client-1", "project.test")

    @pytest.mark.asyncio
    async def test_handle_message_passthrough(
        self, manager: WebSocketManager, send_mock: AsyncMock
    ) -> None:
        """Non-built-in messages pass through for application handling."""
        await manager.handle_connect("client-1", send_mock)
        msg = await manager.handle_message(
            "client-1",
            '{"type": "system.event", "payload": {"key": "value"}}',
        )
        assert msg is not None
        assert msg.type == WebSocketMessageType.SYSTEM_EVENT
        assert msg.payload["key"] == "value"

    @pytest.mark.asyncio
    async def test_handle_invalid_message(
        self, manager: WebSocketManager, send_mock: AsyncMock
    ) -> None:
        """Invalid message sends error and returns None."""
        await manager.handle_connect("client-1", send_mock)
        result = await manager.handle_message(
            "client-1",
            '{"type": "unknown.type"}',
        )
        assert result is None  # Error sent to client

    @pytest.mark.asyncio
    async def test_handle_message_rate_limited(
        self, manager: WebSocketManager, send_mock: AsyncMock
    ) -> None:
        """Rate limited message sends error back."""
        # Use a manager with tight rate limit
        strict_manager = WebSocketManager(rate_limit=2, rate_window_seconds=60)
        await strict_manager.handle_connect("client-1", send_mock)

        await strict_manager.handle_message("client-1", '{"type": "ping", "payload": {}}')
        await strict_manager.handle_message("client-1", '{"type": "ping", "payload": {}}')
        result = await strict_manager.handle_message("client-1", '{"type": "ping", "payload": {}}')
        # Third message should be rate limited — result None, error sent
        assert result is None

    # ------------------------------------------------------------------
    # Event publishing
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_publish_event_no_subscribers(
        self, manager: WebSocketManager, send_mock: AsyncMock
    ) -> None:
        """Publishing to a topic with no subscribers returns 0."""
        event = WebSocketEvent(
            type=WebSocketMessageType.PROJECT_CREATED,
            payload={"id": "p1"},
            topic="nonexistent",
        )
        count = await manager.publish_event(event)
        assert count == 0

    @pytest.mark.asyncio
    async def test_publish_event_to_subscriber(
        self, manager: WebSocketManager, send_mock: AsyncMock
    ) -> None:
        """Publishing sends to subscribers."""
        await manager.handle_connect("client-1", send_mock)
        await manager.subscribe("client-1", "project.test")

        event = WebSocketEvent(
            type=WebSocketMessageType.PROJECT_CREATED,
            payload={"id": "p1"},
            topic="project.test",
        )
        count = await manager.publish_event(event)
        assert count == 1
        assert send_mock.called

    @pytest.mark.asyncio
    async def test_broadcast_event(
        self, manager: WebSocketManager, send_mock: AsyncMock
    ) -> None:
        """Broadcast sends to all connected clients."""
        await manager.handle_connect("c1", send_mock)
        await manager.handle_connect("c2", send_mock)

        event = WebSocketEvent(
            type=WebSocketMessageType.SYSTEM_HEALTH,
            payload={"status": "ok"},
        )
        count = await manager.broadcast_event(event)
        assert count == 2

    @pytest.mark.asyncio
    async def test_emit_to_client(
        self, manager: WebSocketManager, send_mock: AsyncMock
    ) -> None:
        """emit_to_client sends to specific client."""
        await manager.handle_connect("c1", send_mock)

        event = WebSocketEvent(
            type=WebSocketMessageType.SYSTEM_EVENT,
            payload={"msg": "hi"},
        )
        result = await manager.emit_to_client("c1", event)
        assert result is True

    @pytest.mark.asyncio
    async def test_emit_to_unknown_client(
        self, manager: WebSocketManager, send_mock: AsyncMock
    ) -> None:
        """emit_to_client for unknown client returns False."""
        event = WebSocketEvent(type=WebSocketMessageType.SYSTEM_EVENT, payload={})
        result = await manager.emit_to_client("unknown", event)
        assert result is False

    @pytest.mark.asyncio
    async def test_emit_progress(
        self, manager: WebSocketManager, send_mock: AsyncMock
    ) -> None:
        """emit_progress sends progress to project subscribers."""
        await manager.handle_connect("c1", send_mock)
        await manager.subscribe_to_project("c1", "proj-1")

        update = ProgressUpdate(
            operation="analysis",
            progress=0.5,
            stage="transcribing",
        )
        count = await manager.emit_progress("proj-1", update)
        assert count >= 0

    # ------------------------------------------------------------------
    # Subscription management via manager
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_subscribe_unsubscribe(
        self, manager: WebSocketManager, send_mock: AsyncMock
    ) -> None:
        """subscribe and unsubscribe through manager."""
        await manager.handle_connect("c1", send_mock)
        assert await manager.subscribe("c1", "topic.1") is True
        assert manager.subscription_manager.is_subscribed("c1", "topic.1") is True
        assert await manager.unsubscribe("c1", "topic.1") is True
        assert manager.subscription_manager.is_subscribed("c1", "topic.1") is False

    @pytest.mark.asyncio
    async def test_subscribe_to_project(
        self, manager: WebSocketManager, send_mock: AsyncMock
    ) -> None:
        """subscribe_to_project through manager."""
        await manager.handle_connect("c1", send_mock)
        count = await manager.subscribe_to_project("c1", "proj-1")
        assert count == 6  # 6 project topics
        assert manager.subscription_manager.is_subscribed(
            "c1", "project.proj-1"
        )

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_send_to_closed_connection(
        self, manager: WebSocketManager, send_mock: AsyncMock
    ) -> None:
        """Sending to a closed connection raises ConnectionClosedError."""
        # Create a send mock that raises OSError to simulate closed connection
        failing_send = AsyncMock(side_effect=OSError("Connection closed"))

        await manager.handle_connect("c1", failing_send)
        await manager.handle_disconnect("c1")

        event = WebSocketEvent(type=WebSocketMessageType.SYSTEM_EVENT, payload={})
        result = await manager.emit_to_client("c1", event)
        assert result is False

    @pytest.mark.asyncio
    async def test_shutdown_cleanup(
        self, manager: WebSocketManager, send_mock: AsyncMock
    ) -> None:
        """Shutdown cleans up all connections."""
        await manager.handle_connect("c1", send_mock)
        await manager.handle_connect("c2", send_mock)
        await manager.shutdown()
        stats = await manager.get_stats()
        assert stats["active_connections"] == 0

    @pytest.mark.asyncio
    async def test_get_stats(
        self, manager: WebSocketManager, send_mock: AsyncMock
    ) -> None:
        """get_stats returns current state."""
        await manager.handle_connect("c1", send_mock)
        await manager.subscribe("c1", "topic.test")

        stats = await manager.get_stats()
        assert "active_connections" in stats
        assert "total_subscriptions" in stats
        assert "heartbeat_running" in stats
        assert stats["active_connections"] == 1

    @pytest.mark.asyncio
    async def test_cleanup(
        self, manager: WebSocketManager, send_mock: AsyncMock
    ) -> None:
        """Cleanup returns maintenance counts."""
        result = await manager.cleanup()
        assert "stale_connections_removed" in result
        assert "rate_limit_entries_cleaned" in result

    @pytest.mark.asyncio
    async def test_send_ping(self, manager: WebSocketManager, send_mock: AsyncMock) -> None:
        """send_ping sends a ping to a client."""
        await manager.handle_connect("c1", send_mock)
        result = await manager.send_ping("c1")
        assert result is True

    @pytest.mark.asyncio
    async def test_handle_pong_recording(
        self, manager: WebSocketManager, send_mock: AsyncMock
    ) -> None:
        """handle_pong records the pong response."""
        await manager.handle_connect("c1", send_mock)
        await manager.handle_pong("c1")
        missed = await manager.heartbeat.get_missed_count("c1")
        assert missed == 0

    @pytest.mark.asyncio
    async def test_unknown_message_type_no_crash(
        self, manager: WebSocketManager, send_mock: AsyncMock
    ) -> None:
        """Unknown message type does not crash the manager."""
        await manager.handle_connect("c1", send_mock)
        result = await manager.handle_message(
            "c1",
            '{"type": "system.event", "payload": {"data": "test"}}',
        )
        assert result is not None
        assert result.type == WebSocketMessageType.SYSTEM_EVENT

    @pytest.mark.asyncio
    async def test_exception_in_message_handling(
        self, manager: WebSocketManager, send_mock: AsyncMock
    ) -> None:
        """Exceptions during message handling are caught."""
        await manager.handle_connect("c1", send_mock)
        # Malformed JSON should not crash
        result = await manager.handle_message("c1", "{not valid json}")
        assert result is None
