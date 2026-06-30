"""Connection manager — tracks active WebSocket clients.

Responsibilities:
- Connect/disconnect lifecycle
- Client metadata tracking
- Active connection enumeration
- Graceful shutdown (disconnect all)
- Reconnect detection
- Max client enforcement

Thread-safe via asyncio.Lock for shared state.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from backend.infrastructure.logging.logger import get_logger
from backend.infrastructure.websocket.exceptions import (
    ConnectionClosedError,
    MaxClientsReachedError,
)
from backend.infrastructure.websocket.models import ClientInfo

logger = get_logger(__name__)


class ConnectionManager:
    """Manages active WebSocket client connections.

    Provides thread-safe tracking of connected clients with metadata.
    Supports max client enforcement, reconnect detection, and
    graceful shutdown of all connections.

    Usage:
        manager = ConnectionManager(max_clients=100)
        await manager.connect("client-1", remote_addr="127.0.0.1")
        await manager.disconnect("client-1")
        await manager.shutdown()
    """

    def __init__(self, max_clients: int = 100) -> None:
        self._max_clients = max_clients
        self._clients: dict[str, ClientInfo] = {}
        self._lock = asyncio.Lock()
        self._shutdown_event = asyncio.Event()
        self._disconnect_handlers: list[Any] = []
        self._total_connections: int = 0

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def active_count(self) -> int:
        """Number of currently active (alive) connections."""
        return sum(1 for c in self._clients.values() if c.is_alive)

    @property
    def total_count(self) -> int:
        """Total number of tracked clients (including dead)."""
        return len(self._clients)

    @property
    def max_clients(self) -> int:
        """Maximum allowed concurrent clients."""
        return self._max_clients

    @property
    def is_shutting_down(self) -> bool:
        """True if shutdown has been initiated."""
        return self._shutdown_event.is_set()

    # ------------------------------------------------------------------
    # Connection Lifecycle
    # ------------------------------------------------------------------

    async def connect(
        self,
        client_id: str,
        *,
        remote_addr: str = "",
        user_agent: str = "",
        metadata: dict[str, Any] | None = None,
        protocol_version: int = 1,
    ) -> ClientInfo:
        """Register a new client connection.

        Args:
            client_id: Unique client identifier
            remote_addr: Client IP address
            user_agent: Client user agent string
            metadata: Arbitrary client metadata
            protocol_version: WebSocket protocol version

        Returns:
            ClientInfo for the newly connected client

        Raises:
            MaxClientsReachedError: If max concurrent clients reached
        """
        if self.is_shutting_down:
            raise ConnectionClosedError(
                client_id, {"reason": "Server is shutting down"},
            )

        async with self._lock:
            if self.active_count >= self._max_clients:
                raise MaxClientsReachedError(
                    self._max_clients,
                    {"client_id": client_id, "active_count": self.active_count},
                )

            now = datetime.now(UTC)

            # Reconnect: update existing record
            if client_id in self._clients:
                info = self._clients[client_id]
                info.is_alive = True
                info.last_activity_at = now
                info.remote_addr = remote_addr or info.remote_addr
                info.user_agent = user_agent or info.user_agent
                if metadata:
                    info.metadata.update(metadata)
                logger.info(
                    "client_reconnected",
                    extra={"client_id": client_id, "reconnect": True},
                )
                return info

            # New connection
            info = ClientInfo(
                client_id=client_id,
                connected_at=now,
                last_activity_at=now,
                remote_addr=remote_addr,
                user_agent=user_agent,
                metadata=metadata or {},
                protocol_version=protocol_version,
            )
            self._clients[client_id] = info
            self._total_connections += 1

            logger.info(
                "client_connected",
                extra={
                    "client_id": client_id,
                    "active_count": self.active_count,
                    "total_connections": self._total_connections,
                },
            )
            return info

    async def disconnect(
        self,
        client_id: str,
        *,
        reason: str = "",
    ) -> None:
        """Mark a client as disconnected.

        Args:
            client_id: Client to disconnect
            reason: Optional disconnect reason for logging
        """
        async with self._lock:
            info = self._clients.get(client_id)
            if info is not None:
                info.is_alive = False
                info.last_activity_at = datetime.now(UTC)

                logger.info(
                    "client_disconnected",
                    extra={
                        "client_id": client_id,
                        "reason": reason or "unknown",
                        "active_count": self.active_count,
                        "total_connections": self._total_connections,
                    },
                )

    async def remove(self, client_id: str) -> None:
        """Completely remove a client from tracking.

        Args:
            client_id: Client to remove
        """
        async with self._lock:
            self._clients.pop(client_id, None)
            logger.info(
                "client_removed",
                extra={
                    "client_id": client_id,
                    "active_count": self.active_count,
                },
            )

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    async def get_client(self, client_id: str) -> ClientInfo | None:
        """Get client info by ID.

        Args:
            client_id: The client identifier

        Returns:
            ClientInfo or None if client not found
        """
        async with self._lock:
            return self._clients.get(client_id)

    async def get_all_clients(self) -> list[ClientInfo]:
        """Get all tracked clients (alive and dead)."""
        async with self._lock:
            return list(self._clients.values())

    async def get_alive_clients(self) -> list[ClientInfo]:
        """Get only alive clients."""
        async with self._lock:
            return [c for c in self._clients.values() if c.is_alive]

    async def get_client_count(self) -> int:
        """Get count of alive clients."""
        async with self._lock:
            return self.active_count

    async def get_client_ids(self) -> set[str]:
        """Get set of all tracked client IDs."""
        async with self._lock:
            return set(self._clients.keys())

    async def update_activity(self, client_id: str) -> None:
        """Update the last activity timestamp for a client.

        Args:
            client_id: Client that had activity
        """
        async with self._lock:
            info = self._clients.get(client_id)
            if info is not None:
                info.last_activity_at = datetime.now(UTC)

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    async def shutdown(self) -> None:
        """Gracefully disconnect all clients.

        Sets shutdown flag and disconnects all tracked clients.
        """
        logger.info("ws_shutdown_started", extra={"active_count": self.active_count})
        self._shutdown_event.set()

        async with self._lock:
            for client_id in list(self._clients.keys()):
                info = self._clients[client_id]
                info.is_alive = False

            self._clients.clear()

        logger.info("ws_shutdown_complete")

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    async def cleanup_stale(
        self,
        max_age_seconds: float = 3600,
    ) -> int:
        """Remove clients that have been dead for too long.

        Args:
            max_age_seconds: Maximum age in seconds for dead clients

        Returns:
            Number of removed clients
        """
        now = datetime.now(UTC)
        stale_ids: list[str] = []

        async with self._lock:
            for client_id, info in self._clients.items():
                if not info.is_alive:
                    age = (now - info.last_activity_at).total_seconds()
                    if age > max_age_seconds:
                        stale_ids.append(client_id)

            for client_id in stale_ids:
                self._clients.pop(client_id, None)

        if stale_ids:
            logger.info(
                "ws_cleanup_stale",
                extra={"removed_count": len(stale_ids)},
            )

        return len(stale_ids)
