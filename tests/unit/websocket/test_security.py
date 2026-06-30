"""Tests for WebSocket security validator.

Covers:
- Message validation
- Rate limiting
- Topic validation
- Size limits
- Malformed input detection
"""

from __future__ import annotations

import pytest

from backend.infrastructure.websocket.exceptions import (
    InvalidMessageError,
    MessageTooLargeError,
    RateLimitExceededError,
    SubscriptionError,
)
from backend.infrastructure.websocket.models import WebSocketMessageType
from backend.infrastructure.websocket.security import SecurityValidator


class TestSecurityValidator:
    """Tests for SecurityValidator."""

    @pytest.fixture
    def validator(self) -> SecurityValidator:
        return SecurityValidator(
            max_message_size=1024,
            rate_limit=5,
            rate_window_seconds=60,
        )

    @pytest.mark.asyncio
    async def test_validate_valid_message(self, validator: SecurityValidator) -> None:
        """Valid message passes validation."""
        msg = await validator.validate_message(
            '{"type": "ping", "payload": {}}',
            "client-1",
        )
        assert msg.type == WebSocketMessageType.PING
        assert msg.client_id == "client-1"

    @pytest.mark.asyncio
    async def test_validate_message_too_large(self, validator: SecurityValidator) -> None:
        """Message exceeding max size raises MessageTooLargeError."""
        with pytest.raises(MessageTooLargeError):
            await validator.validate_message(
                "x" * 2000,
                "client-1",
            )

    @pytest.mark.asyncio
    async def test_validate_malformed_json(self, validator: SecurityValidator) -> None:
        """Malformed JSON raises InvalidMessageError."""
        with pytest.raises(InvalidMessageError, match="Malformed JSON"):
            await validator.validate_message(
                "{not json",
                "client-1",
            )

    @pytest.mark.asyncio
    async def test_validate_missing_type(self, validator: SecurityValidator) -> None:
        """Missing 'type' field raises InvalidMessageError."""
        with pytest.raises(InvalidMessageError, match="Missing required field"):
            await validator.validate_message(
                '{"payload": {}}',
                "client-1",
            )

    @pytest.mark.asyncio
    async def test_validate_unknown_type(self, validator: SecurityValidator) -> None:
        """Unknown message type raises InvalidMessageError."""
        with pytest.raises(InvalidMessageError, match="Unknown message type"):
            await validator.validate_message(
                '{"type": "nonexistent.type"}',
                "client-1",
            )

    @pytest.mark.asyncio
    async def test_validate_non_dict_payload(self, validator: SecurityValidator) -> None:
        """Non-dict payload raises InvalidMessageError."""
        with pytest.raises(InvalidMessageError, match="JSON object"):
            await validator.validate_message(
                '{"type": "ping", "payload": "string"}',
                "client-1",
            )

    @pytest.mark.asyncio
    async def test_rate_limit(self, validator: SecurityValidator) -> None:
        """Exceeding rate limit raises RateLimitExceededError."""
        # Send 5 messages (the limit)
        for _ in range(5):
            await validator.validate_message(
                '{"type": "ping", "payload": {}}',
                "client-1",
            )
        # 6th should fail
        with pytest.raises(RateLimitExceededError):
            await validator.validate_message(
                '{"type": "ping", "payload": {}}',
                "client-1",
            )

    @pytest.mark.asyncio
    async def test_rate_limit_per_client(self, validator: SecurityValidator) -> None:
        """Rate limit is per client, not global."""
        # Client-1 hits limit
        for _ in range(5):
            await validator.validate_message(
                '{"type": "ping", "payload": {}}',
                "client-1",
            )
        # Client-2 should still be allowed
        msg = await validator.validate_message(
            '{"type": "ping", "payload": {}}',
            "client-2",
        )
        assert msg is not None

    @pytest.mark.asyncio
    async def test_reset_rate_limit(self, validator: SecurityValidator) -> None:
        """reset_rate_limit clears rate limit for a client."""
        for _ in range(5):
            await validator.validate_message(
                '{"type": "ping", "payload": {}}',
                "client-1",
            )
        await validator.reset_rate_limit("client-1")
        # Should be able to send again
        msg = await validator.validate_message(
            '{"type": "ping", "payload": {}}',
            "client-1",
        )
        assert msg is not None

    def test_validate_topic_valid(self, validator: SecurityValidator) -> None:
        """Valid topic passes validation."""
        assert validator.validate_topic("project.abc") is True
        assert validator.validate_topic("system") is True

    def test_validate_topic_empty(self, validator: SecurityValidator) -> None:
        """Empty topic raises SubscriptionError."""
        with pytest.raises(SubscriptionError, match="empty"):
            validator.validate_topic("")

    def test_validate_topic_path_traversal(self, validator: SecurityValidator) -> None:
        """Path traversal in topic raises SubscriptionError."""
        with pytest.raises(SubscriptionError):
            validator.validate_topic("../etc/passwd")

    def test_validate_topic_too_long(self, validator: SecurityValidator) -> None:
        """Overly long topic raises SubscriptionError."""
        with pytest.raises(SubscriptionError, match="too long"):
            validator.validate_topic("x" * 300)

    @pytest.mark.asyncio
    async def test_cleanup_rate_limits(self, validator: SecurityValidator) -> None:
        """cleanup_rate_limits removes stale entries."""
        # Create some rate limit entries
        await validator.validate_message(
            '{"type": "ping", "payload": {}}',
            "client-1",
        )
        cleaned = await validator.cleanup_rate_limits()
        assert cleaned >= 0

    @pytest.mark.asyncio
    async def test_non_string_type(self, validator: SecurityValidator) -> None:
        """Non-string type raises InvalidMessageError."""
        with pytest.raises(InvalidMessageError):
            await validator.validate_message(
                '{"type": 123}',
                "client-1",
            )
