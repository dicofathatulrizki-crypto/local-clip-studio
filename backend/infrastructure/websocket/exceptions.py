"""WebSocket exception hierarchy.

All exceptions inherit from WebSocketError base.
Translates raw websocket/protocol errors into structured exceptions.
No business logic — pure infrastructure error types.
"""

from __future__ import annotations

from typing import Any


class WebSocketError(Exception):
    """Base exception for all WebSocket infrastructure errors."""

    def __init__(
        self,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON transmission."""
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details,
        }


class ConnectionClosedError(WebSocketError):
    """Raised when attempting to use a closed connection."""

    def __init__(
        self,
        client_id: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            "ERR-WS-CLOSED",
            f"Connection '{client_id}' is already closed",
            {"client_id": client_id, **(details or {})},
        )


class MaxClientsReachedError(WebSocketError):
    """Raised when the maximum number of client connections is reached."""

    def __init__(
        self,
        max_clients: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            "ERR-WS-MAX-CLIENTS",
            f"Maximum client count ({max_clients}) reached",
            {"max_clients": max_clients, **(details or {})},
        )


class InvalidMessageError(WebSocketError):
    """Raised when a received message is malformed or invalid."""

    def __init__(
        self,
        reason: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            "ERR-WS-INVALID-MSG",
            f"Invalid message: {reason}",
            {"reason": reason, **(details or {})},
        )


class MessageTooLargeError(WebSocketError):
    """Raised when a message exceeds the maximum allowed size."""

    def __init__(
        self,
        size_bytes: int,
        max_bytes: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            "ERR-WS-MSG-TOO-LARGE",
            f"Message size {size_bytes} bytes exceeds maximum {max_bytes} bytes",
            {
                "size_bytes": size_bytes,
                "max_bytes": max_bytes,
                **(details or {}),
            },
        )


class HeartbeatTimeoutError(WebSocketError):
    """Raised when a client fails to respond to heartbeat pings."""

    def __init__(
        self,
        client_id: str,
        timeout_seconds: float,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            "ERR-WS-HEARTBEAT",
            f"Client '{client_id}' heartbeat timeout ({timeout_seconds}s)",
            {
                "client_id": client_id,
                "timeout_seconds": timeout_seconds,
                **(details or {}),
            },
        )


class SubscriptionError(WebSocketError):
    """Raised when a subscription operation fails."""

    def __init__(
        self,
        reason: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            "ERR-WS-SUBSCRIPTION",
            f"Subscription error: {reason}",
            {"reason": reason, **(details or {})},
        )


class RateLimitExceededError(WebSocketError):
    """Raised when a client exceeds the message rate limit."""

    def __init__(
        self,
        client_id: str,
        limit: int,
        window_seconds: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            "ERR-WS-RATE-LIMIT",
            f"Client '{client_id}' exceeded rate limit ({limit}/{window_seconds}s)",
            {
                "client_id": client_id,
                "limit": limit,
                "window_seconds": window_seconds,
                **(details or {}),
            },
        )


class SerializationError(WebSocketError):
    """Raised when serialization or deserialization fails."""

    def __init__(
        self,
        reason: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            "ERR-WS-SERIALIZE",
            f"Serialization error: {reason}",
            {"reason": reason, **(details or {})},
        )
