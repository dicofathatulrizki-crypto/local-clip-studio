"""Security and validation for WebSocket messages.

Responsibilities:
- Payload validation (structure, types, required fields)
- Malformed JSON detection
- Unknown event type rejection
- Rate limiting per client
- Max message size enforcement
- Subscription validation
- Sensitive data filtering

No authentication or cloud/telemetry — localhost only.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from backend.infrastructure.logging.logger import get_logger
from backend.infrastructure.websocket.exceptions import (
    InvalidMessageError,
    MessageTooLargeError,
    RateLimitExceededError,
    SubscriptionError,
)
from backend.infrastructure.websocket.models import (
    WebSocketMessage,
    WebSocketMessageType,
)

logger = get_logger(__name__)


class SecurityValidator:
    """Validates WebSocket messages for security and correctness.

    Enforces:
    - Max message size (configurable)
    - Rate limiting per client (configurable window)
    - Payload structure validation
    - Unknown type rejection
    - Subscription topic validation

    Thread-safe for concurrent validation calls.
    """

    def __init__(
        self,
        max_message_size: int = 256 * 1024,
        rate_limit: int = 100,
        rate_window_seconds: int = 60,
        allowed_types: set[str] | None = None,
    ) -> None:
        self._max_message_size = max_message_size
        self._rate_limit = rate_limit
        self._rate_window = rate_window_seconds

        # Track rate limits per client
        self._client_message_times: dict[str, list[float]] = {}
        self._lock = asyncio.Lock()

        # All message types from the enum
        self._allowed_types = allowed_types or {
            t.value for t in WebSocketMessageType
        }

    # ------------------------------------------------------------------
    # Message Validation
    # ------------------------------------------------------------------

    async def validate_message(
        self,
        raw: str,
        client_id: str,
    ) -> WebSocketMessage:
        """Validate a raw WebSocket message from a client.

        Checks size, rate limits, and content validity.

        Args:
            raw: Raw JSON message string
            client_id: Sending client's ID

        Returns:
            Parsed WebSocketMessage

        Raises:
            MessageTooLargeError: If message exceeds max size
            RateLimitExceededError: If client exceeded rate limit
            InvalidMessageError: If message is malformed or type unknown
        """
        # 1. Check message size
        if len(raw) > self._max_message_size:
            raise MessageTooLargeError(
                len(raw), self._max_message_size,
                {"client_id": client_id},
            )

        # 2. Check rate limit
        await self._check_rate_limit(client_id)

        # 3. Parse JSON
        try:
            data: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise InvalidMessageError(
                f"Malformed JSON: {exc}",
                {"client_id": client_id},
            ) from exc

        if not isinstance(data, dict):
            raise InvalidMessageError(
                "Message must be a JSON object",
                {"client_id": client_id, "actual_type": type(data).__name__},
            )

        # 4. Check required fields
        if "type" not in data:
            raise InvalidMessageError(
                "Missing required field: 'type'",
                {"client_id": client_id},
            )

        msg_type_str = data["type"]
        if not isinstance(msg_type_str, str):
            raise InvalidMessageError(
                "'type' must be a string",
                {"client_id": client_id, "type": type(msg_type_str).__name__},
            )

        # 5. Check type is allowed
        if msg_type_str not in self._allowed_types:
            raise InvalidMessageError(
                f"Unknown message type: '{msg_type_str}'",
                {"client_id": client_id, "type": msg_type_str},
            )

        # 6. Validate payload structure
        payload = data.get("payload", {})
        if not isinstance(payload, dict):
            raise InvalidMessageError(
                "'payload' must be a JSON object",
                {"client_id": client_id, "payload_type": type(payload).__name__},
            )

        # 7. Build validated message
        try:
            msg_type = WebSocketMessageType(msg_type_str)
        except ValueError:
            raise InvalidMessageError(
                f"Invalid message type value: '{msg_type_str}'",
                {"client_id": client_id},
            )

        return WebSocketMessage(
            type=msg_type,
            payload=payload,
            client_id=client_id,
            event_id=data.get("event_id", ""),
            correlation_id=data.get("correlation_id", ""),
            topic=data.get("topic", ""),
            schema_version=data.get("schema_version", 1),
        )

    def validate_topic(self, topic: str) -> bool:
        """Validate a subscription topic string.

        Args:
            topic: Topic to validate

        Returns:
            True if topic is valid

        Raises:
            SubscriptionError: If topic is invalid
        """
        if not topic or not topic.strip():
            raise SubscriptionError("Topic cannot be empty")

        # Check for path traversal in topic names
        if ".." in topic or "/" in topic:
            raise SubscriptionError(
                f"Invalid topic: '{topic}'",
                {"topic": topic},
            )

        # Check for overly long topics
        if len(topic) > 256:
            raise SubscriptionError(
                f"Topic too long: {len(topic)} characters (max 256)",
                {"topic_length": len(topic)},
            )

        return True

    # ------------------------------------------------------------------
    # Rate Limiting
    # ------------------------------------------------------------------

    async def _check_rate_limit(self, client_id: str) -> None:
        """Check rate limit for a client.

        Args:
            client_id: Client to check

        Raises:
            RateLimitExceededError: If rate limit exceeded
        """
        now = time.monotonic()
        window_start = now - self._rate_window

        async with self._lock:
            times = self._client_message_times.get(client_id, [])

            # Remove old entries outside the window
            times = [t for t in times if t > window_start]
            self._client_message_times[client_id] = times

            if len(times) >= self._rate_limit:
                oldest = times[0] if times else now
                wait = max(0, oldest + self._rate_window - now)
                raise RateLimitExceededError(
                    client_id, self._rate_limit, self._rate_window,
                    {
                        "current_count": len(times),
                        "wait_seconds": round(wait, 1),
                    },
                )

            times.append(now)
            self._client_message_times[client_id] = times

    async def reset_rate_limit(self, client_id: str) -> None:
        """Reset the rate limit counter for a client.

        Args:
            client_id: Client to reset
        """
        async with self._lock:
            self._client_message_times.pop(client_id, None)

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    async def cleanup_rate_limits(self) -> int:
        """Clean up stale rate limit entries.

        Returns:
            Number of entries removed
        """
        now = time.monotonic()
        window_start = now - self._rate_window - 10  # buffer
        removed = 0

        async with self._lock:
            stale_ids = [
                cid for cid, times in self._client_message_times.items()
                if not times or max(times) < window_start
            ]
            for cid in stale_ids:
                del self._client_message_times[cid]
                removed += 1

        return removed
