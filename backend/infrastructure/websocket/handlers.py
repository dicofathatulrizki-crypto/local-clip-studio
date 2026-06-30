"""FastAPI WebSocket endpoint handler.

Provides the async WebSocket endpoint that integrates with the
WebSocketManager for connection lifecycle, message handling,
and event streaming.

Architecture:
- Thin handler — delegates all logic to WebSocketManager
- No business logic — pure protocol handling
- Integrates with FastAPI's WebSocket API
"""

from __future__ import annotations

import asyncio

from fastapi import WebSocket, WebSocketDisconnect

from backend.infrastructure.logging.logger import get_logger
from backend.infrastructure.websocket.exceptions import (
    MaxClientsReachedError,
    WebSocketError,
)
from backend.infrastructure.websocket.manager import WebSocketManager

logger = get_logger(__name__)

# Default manager instance (override for testing)
_default_manager: WebSocketManager | None = None


def set_default_manager(manager: WebSocketManager) -> None:
    """Set the default WebSocket manager for the handler.

    Args:
        manager: The manager instance to use
    """
    global _default_manager
    _default_manager = manager


def get_default_manager() -> WebSocketManager:
    """Get or create the default WebSocket manager.

    Returns:
        The default WebSocketManager instance
    """
    global _default_manager
    if _default_manager is None:
        _default_manager = WebSocketManager()
    return _default_manager


class WebSocketHandler:
    """FastAPI WebSocket endpoint handler.

    Manages a single WebSocket connection lifecycle:
    1. Accept connection → register with manager
    2. Message loop → validate, route, respond
    3. Disconnect → cleanup subscriptions and state

    Usage:
        @app.websocket("/api/v1/ws")
        async def websocket_endpoint(websocket: WebSocket):
            handler = WebSocketHandler(websocket, manager)
            await handler.run()
    """

    def __init__(
        self,
        websocket: WebSocket,
        manager: WebSocketManager | None = None,
    ) -> None:
        self._ws = websocket
        self._manager = manager or get_default_manager()
        self._client_id: str = ""
        self._receive_timeout: float = 300.0  # 5 minutes

    @property
    def client_id(self) -> str:
        """Get the client ID assigned to this connection."""
        return self._client_id

    async def run(self) -> None:
        """Run the WebSocket connection lifecycle.

        Accepts the connection, registers with the manager,
        processes messages in a loop, and cleans up on disconnect.
        """
        await self._ws.accept()

        # Generate a client ID
        self._client_id = self._generate_client_id()

        # Register with manager
        try:
            await self._manager.handle_connect(
                self._client_id,
                send_function=self._send,
                remote_addr=self._ws.client.host if self._ws.client else "",
            )
        except MaxClientsReachedError as exc:
            await self._ws.send_json({"error": str(exc)})
            await self._ws.close(code=1013)  # Try again later
            return

        logger.info(
            "ws_connection_accepted",
            extra={
                "client_id": self._client_id,
                "remote_addr": self._ws.client.host if self._ws.client else "",
            },
        )

        # Message processing loop
        try:
            while True:
                try:
                    raw = await asyncio.wait_for(
                        self._ws.receive_text(),
                        timeout=self._receive_timeout,
                    )
                except TimeoutError:
                    # Send a ping to check if client is still alive
                    if not await self._manager.send_ping(self._client_id):
                        break
                    continue

                if raw is None:
                    break

                await self._manager.handle_message(self._client_id, raw)

        except WebSocketDisconnect:
            logger.info(
                "ws_disconnected",
                extra={"client_id": self._client_id},
            )
        except Exception as exc:
            logger.warning(
                "ws_error",
                extra={
                    "client_id": self._client_id,
                    "error": str(exc),
                },
            )
        finally:
            await self._manager.handle_disconnect(
                self._client_id,
                reason="connection_closed",
            )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _send(self, client_id: str, data: str | bytes) -> None:
        """Send data to the WebSocket client.

        Args:
            client_id: Client ID (must match this handler's client)
            data: JSON string or bytes to send

        Raises:
            WebSocketError: If client_id doesn't match or send fails
        """
        if client_id != self._client_id:
            msg = "ERR-WS-ID-MISMATCH"
            raise WebSocketError(
                msg,
                f"Client ID mismatch: '{client_id}' != '{self._client_id}'",
            )

        try:
            if isinstance(data, bytes):
                await self._ws.send_bytes(data)
            else:
                await self._ws.send_text(data)
        except WebSocketDisconnect as exc:
            msg = "ERR-WS-CLOSED"
            raise WebSocketError(
                msg,
                f"Connection closed during send: {exc}",
            ) from exc

    @staticmethod
    def _generate_client_id() -> str:
        """Generate a unique client ID.

        Uses timestamp and a random component for uniqueness.

        Returns:
            Unique client identifier string
        """
        import random
        import time
        timestamp = int(time.time() * 1_000_000)
        rand_part = random.randint(0, 999999)
        return f"ws-client-{timestamp}-{rand_part}"
