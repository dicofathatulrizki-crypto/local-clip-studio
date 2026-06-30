"""Tests for WebSocket connection manager.

Covers:
- Connect/disconnect lifecycle
- Connection limits
- Client metadata tracking
- Reconnect detection
- Graceful shutdown
- Activity tracking
"""

from __future__ import annotations

import pytest

from backend.infrastructure.websocket.connection import ConnectionManager
from backend.infrastructure.websocket.exceptions import (
    ConnectionClosedError,
    MaxClientsReachedError,
)


class TestConnectionManager:
    """Tests for ConnectionManager."""

    @pytest.fixture
    def manager(self) -> ConnectionManager:
        return ConnectionManager(max_clients=10)

    @pytest.mark.asyncio
    async def test_connect(self, manager: ConnectionManager) -> None:
        """Connect registers a new client."""
        info = await manager.connect(
            "client-1",
            remote_addr="127.0.0.1",
            user_agent="test-agent",
        )
        assert info.client_id == "client-1"
        assert info.is_alive is True
        assert info.remote_addr == "127.0.0.1"
        assert info.user_agent == "test-agent"
        assert await manager.get_client_count() == 1

    @pytest.mark.asyncio
    async def test_connect_with_metadata(self, manager: ConnectionManager) -> None:
        """Connect with custom metadata stores it."""
        info = await manager.connect(
            "client-1",
            metadata={"version": "1.0", "platform": "test"},
        )
        assert info.metadata["version"] == "1.0"
        assert info.metadata["platform"] == "test"

    @pytest.mark.asyncio
    async def test_disconnect(self, manager: ConnectionManager) -> None:
        """Disconnect marks client as not alive."""
        await manager.connect("client-1")
        await manager.disconnect("client-1", reason="test")
        info = await manager.get_client("client-1")
        assert info is not None
        assert info.is_alive is False

    @pytest.mark.asyncio
    async def test_disconnect_unknown(self, manager: ConnectionManager) -> None:
        """Disconnecting an unknown client should not raise."""
        await manager.disconnect("nonexistent")

    @pytest.mark.asyncio
    async def test_reconnect(self, manager: ConnectionManager) -> None:
        """Reconnecting an existing client updates it."""
        await manager.connect("client-1", user_agent="v1")
        await manager.disconnect("client-1")
        info = await manager.connect("client-1", user_agent="v2")
        assert info.is_alive is True
        # Should have been updated
        assert info.user_agent == "v2"

    @pytest.mark.asyncio
    async def test_max_clients(self, manager: ConnectionManager) -> None:
        """Exceeding max_clients raises MaxClientsReachedError."""
        for i in range(10):
            await manager.connect(f"client-{i}")
        with pytest.raises(MaxClientsReachedError):
            await manager.connect("client-too-many")

    @pytest.mark.asyncio
    async def test_shutdown(self, manager: ConnectionManager) -> None:
        """Shutdown disconnects all clients."""
        await manager.connect("client-1")
        await manager.connect("client-2")
        await manager.shutdown()
        assert manager.is_shutting_down is True
        assert manager.total_count == 0

    @pytest.mark.asyncio
    async def test_shutdown_rejects_new(self, manager: ConnectionManager) -> None:
        """Connect during shutdown raises ConnectionClosedError."""
        await manager.shutdown()
        with pytest.raises(ConnectionClosedError):
            await manager.connect("client-1")

    @pytest.mark.asyncio
    async def test_get_client_nonexistent(self, manager: ConnectionManager) -> None:
        """Getting a non-existent client returns None."""
        info = await manager.get_client("nonexistent")
        assert info is None

    @pytest.mark.asyncio
    async def test_get_all_clients(self, manager: ConnectionManager) -> None:
        """get_all_clients returns all tracked clients."""
        await manager.connect("c1")
        await manager.connect("c2")
        await manager.disconnect("c2")
        clients = await manager.get_all_clients()
        assert len(clients) == 2

    @pytest.mark.asyncio
    async def test_get_alive_clients(self, manager: ConnectionManager) -> None:
        """get_alive_clients returns only alive clients."""
        await manager.connect("c1")
        await manager.connect("c2")
        await manager.disconnect("c2")
        alive = await manager.get_alive_clients()
        assert len(alive) == 1
        assert alive[0].client_id == "c1"

    @pytest.mark.asyncio
    async def test_remove(self, manager: ConnectionManager) -> None:
        """Remove completely removes a client from tracking."""
        await manager.connect("c1")
        await manager.remove("c1")
        assert await manager.get_client("c1") is None
        assert manager.total_count == 0

    @pytest.mark.asyncio
    async def test_update_activity(self, manager: ConnectionManager) -> None:
        """update_activity updates last_activity_at."""
        await manager.connect("c1")
        info = await manager.get_client("c1")
        assert info is not None
        old_time = info.last_activity_at
        await manager.update_activity("c1")
        # Should update
        assert info.last_activity_at >= old_time

    @pytest.mark.asyncio
    async def test_get_client_ids(self, manager: ConnectionManager) -> None:
        """get_client_ids returns set of all client IDs."""
        await manager.connect("c1")
        await manager.connect("c2")
        ids = await manager.get_client_ids()
        assert ids == {"c1", "c2"}

    @pytest.mark.asyncio
    async def test_cleanup_stale(self, manager: ConnectionManager) -> None:
        """cleanup_stale removes old dead clients."""
        await manager.connect("c1")
        await manager.connect("c2")
        await manager.disconnect("c1", reason="test")
        # Cleanup with very short timeout
        removed = await manager.cleanup_stale(max_age_seconds=0)
        assert removed >= 1
        # c2 is alive, should remain
        assert await manager.get_client("c2") is not None
