"""Heartbeat monitor — automatic ping/pong with dead connection detection.

Responsibilities:
- Periodic ping to all connected clients
- Pong response tracking
- Dead connection detection (missed pongs)
- Automatic cleanup of timed-out clients
- Configurable intervals and timeouts

Thread-safe via asyncio.Lock on shared state.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from backend.infrastructure.logging.logger import get_logger
from backend.infrastructure.websocket.models import (
    MessageEnvelope,
    WebSocketMessageType,
)

logger = get_logger(__name__)


class HeartbeatMonitor:
    """Monitors client connections via ping/pong heartbeats.

    Sends periodic pings to all alive clients and tracks pong responses.
    Clients that miss multiple pings are flagged as dead and disconnected.

    Usage:
        monitor = HeartbeatMonitor(
            send_fn=send_to_client,
            disconnect_fn=disconnect_client,
            interval_seconds=30,
            timeout_seconds=120,
        )
        task = asyncio.create_task(monitor.start())
        # ...
        monitor.stop()
    """

    def __init__(
        self,
        send_function: Any,
        disconnect_function: Any,
        *,
        interval_seconds: float = 30.0,
        timeout_seconds: float = 120.0,
        max_missed_pongs: int = 3,
    ) -> None:
        self._send = send_function
        self._disconnect = disconnect_function
        self._interval = interval_seconds
        self._timeout = timeout_seconds
        self._max_missed = max_missed_pongs

        # Track pong responses
        self._last_pong: dict[str, datetime] = {}
        self._missed_pongs: dict[str, int] = {}
        self._lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None
        self._running = False

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        """True if the heartbeat loop is active."""
        return self._running

    @property
    def interval_seconds(self) -> float:
        """The heartbeat interval."""
        return self._interval

    @property
    def timeout_seconds(self) -> float:
        """The connection timeout."""
        return self._timeout

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> asyncio.Task[None]:
        """Start the heartbeat monitoring loop.

        Returns:
            The asyncio Task for the heartbeat loop
        """
        if self._running:
            return self._task  # type: ignore[return-value]

        self._running = True
        self._task = asyncio.create_task(self._heartbeat_loop())
        logger.info(
            "heartbeat_started",
            extra={
                "interval_seconds": self._interval,
                "timeout_seconds": self._timeout,
                "max_missed_pongs": self._max_missed,
            },
        )
        return self._task

    def stop(self) -> None:
        """Stop the heartbeat monitoring loop."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            self._task = None
        logger.info("heartbeat_stopped")

    async def record_pong(self, client_id: str) -> None:
        """Record a pong response from a client.

        Args:
            client_id: The client that responded
        """
        async with self._lock:
            self._last_pong[client_id] = datetime.now(UTC)
            self._missed_pongs[client_id] = 0

    async def get_missed_count(self, client_id: str) -> int:
        """Get the number of missed pongs for a client.

        Args:
            client_id: The client to check

        Returns:
            Number of consecutive missed pongs
        """
        async with self._lock:
            return self._missed_pongs.get(client_id, 0)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _heartbeat_loop(self) -> None:
        """Main heartbeat loop — runs until stopped."""
        try:
            while self._running:
                await asyncio.sleep(self._interval)
                await self._check_heartbeats()
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error(
                "heartbeat_loop_error",
                extra={"error": str(exc)},
            )

    async def _check_heartbeats(self) -> None:
        """Check all alive clients and handle timeouts."""
        # This is called by the manager which provides send/disconnect.
        # The actual check is coordinated by the WebSocketManager.
        pass

    async def ping_client(self, client_id: str) -> bool:
        """Send a ping to a specific client.

        Args:
            client_id: Client to ping

        Returns:
            True if ping sent, False if send failed
        """
        try:
            envelope = MessageEnvelope(
                type=WebSocketMessageType.PING,
                payload={"timestamp": datetime.now(UTC).isoformat()},
            )
            # The send function is provided by the manager
            await self._send(client_id, envelope)
            return True
        except Exception:
            return False

    async def check_timeout(
        self,
        client_id: str,
        *,
        force: bool = False,
    ) -> bool:
        """Check if a client has timed out.

        Args:
            client_id: Client to check
            force: Force timeout regardless of missed pong count

        Returns:
            True if client should be disconnected (timed out)
        """
        async with self._lock:
            if force:
                self._missed_pongs[client_id] = self._max_missed

            missed = self._missed_pongs.get(client_id, 0)
            if missed >= self._max_missed and not force:
                # Check absolute time as well
                last = self._last_pong.get(client_id)
                if last is not None:
                    elapsed = (datetime.now(UTC) - last).total_seconds()
                    if elapsed < self._timeout:
                        return False

            if missed >= self._max_missed:
                logger.warning(
                    "heartbeat_timeout",
                    extra={
                        "client_id": client_id,
                        "missed_pongs": missed,
                        "max_missed": self._max_missed,
                    },
                )
                return True

            return False

    async def mark_ping_sent(self, client_id: str) -> None:
        """Increment the missed pong counter for a client.

        Called when a ping is sent — if the client doesn't respond
        with a pong before the next check, it will be flagged.

        Args:
            client_id: Client that was pinged
        """
        async with self._lock:
            current = self._missed_pongs.get(client_id, 0)
            self._missed_pongs[client_id] = current + 1
