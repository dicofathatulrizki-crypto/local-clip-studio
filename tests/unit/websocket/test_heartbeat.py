"""Tests for WebSocket heartbeat monitor.

Covers:
- Start/stop
- Pong recording
- Timeout detection
- Missed pong tracking
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from backend.infrastructure.websocket.heartbeat import HeartbeatMonitor
from backend.infrastructure.websocket.models import MessageEnvelope


class TestHeartbeatMonitor:
    """Tests for HeartbeatMonitor."""

    @pytest.fixture
    def monitor(self) -> HeartbeatMonitor:
        send_mock = AsyncMock(return_value=None)
        disconnect_mock = AsyncMock(return_value=None)
        return HeartbeatMonitor(
            send_function=send_mock,
            disconnect_function=disconnect_mock,
            interval_seconds=60.0,
            timeout_seconds=120.0,
            max_missed_pongs=3,
        )

    def test_initial_state(self, monitor: HeartbeatMonitor) -> None:
        """HeartbeatMonitor starts in stopped state."""
        assert monitor.is_running is False
        assert monitor.interval_seconds == 60.0
        assert monitor.timeout_seconds == 120.0

    def test_start_stop(self, monitor: HeartbeatMonitor) -> None:
        """Start and stop the heartbeat monitor."""
        task = monitor.start()
        assert monitor.is_running is True
        assert task is not None

        monitor.stop()
        assert monitor.is_running is False

    @pytest.mark.asyncio
    async def test_record_pong(self, monitor: HeartbeatMonitor) -> None:
        """Recording a pong resets the missed count."""
        await monitor.mark_ping_sent("client-1")
        await monitor.mark_ping_sent("client-1")
        assert await monitor.get_missed_count("client-1") == 2

        await monitor.record_pong("client-1")
        assert await monitor.get_missed_count("client-1") == 0

    @pytest.mark.asyncio
    async def test_check_timeout_not_timed_out(self, monitor: HeartbeatMonitor) -> None:
        """check_timeout returns False when within limits."""
        await monitor.record_pong("client-1")
        timed_out = await monitor.check_timeout("client-1")
        assert timed_out is False

    @pytest.mark.asyncio
    async def test_check_timeout_timed_out(self, monitor: HeartbeatMonitor) -> None:
        """check_timeout returns True when max missed exceeded."""
        for _ in range(4):
            await monitor.mark_ping_sent("client-1")
        timed_out = await monitor.check_timeout("client-1")
        assert timed_out is True

    @pytest.mark.asyncio
    async def test_ping_client(self, monitor: HeartbeatMonitor) -> None:
        """ping_client sends a ping."""
        result = await monitor.ping_client("client-1")
        # Mock returns True
        assert result is True

    @pytest.mark.asyncio
    async def test_get_missed_count(self, monitor: HeartbeatMonitor) -> None:
        """get_missed_count returns correct count."""
        assert await monitor.get_missed_count("unknown") == 0
        await monitor.mark_ping_sent("c1")
        await monitor.mark_ping_sent("c1")
        assert await monitor.get_missed_count("c1") == 2

    @pytest.mark.asyncio
    async def test_force_timeout(self, monitor: HeartbeatMonitor) -> None:
        """Force timeout with force=True."""
        await monitor.record_pong("client-1")
        timed_out = await monitor.check_timeout("client-1", force=True)
        assert timed_out is True

    def test_start_twice(self, monitor: HeartbeatMonitor) -> None:
        """Starting twice returns same task."""
        task1 = monitor.start()
        task2 = monitor.start()
        assert task1 is task2
        monitor.stop()
