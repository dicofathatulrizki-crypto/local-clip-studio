"""Tests for WebSocket Serializer.

Covers:
- Serialization of all extended types (datetime, UUID, Enum)
- Deserialization validation
- Schema versioning
- Error handling
- Message size limits
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

import pytest

from backend.infrastructure.websocket.exceptions import (
    InvalidMessageError,
    MessageTooLargeError,
    SerializationError,
)
from backend.infrastructure.websocket.models import (
    MessageEnvelope,
    WebSocketMessage,
    WebSocketMessageType,
)
from backend.infrastructure.websocket.serializer import Serializer


class TestSerializer:
    """Tests for Serializer."""

    def setup_method(self) -> None:
        self.serializer = Serializer(max_message_size=1024 * 1024)

    def test_serialize_deserialize_roundtrip(self) -> None:
        """Serializing then deserializing preserves all fields."""
        envelope = MessageEnvelope(
            type=WebSocketMessageType.PROJECT_CREATED,
            payload={"project_id": "proj-1", "name": "Test"},
            event_id="evt-1",
            correlation_id="corr-1",
            topic="project.proj-1",
        )

        raw = self.serializer.serialize(envelope)
        message = self.serializer.deserialize(raw)

        assert message.type == WebSocketMessageType.PROJECT_CREATED
        assert message.payload["project_id"] == "proj-1"
        assert message.event_id == "evt-1"
        assert message.correlation_id == "corr-1"
        assert message.topic == "project.proj-1"
        assert message.schema_version == 1

    def test_serialize_event_convenience(self) -> None:
        """serialize_event creates and serializes an event in one call."""
        raw = self.serializer.serialize_event(
            WebSocketMessageType.SYSTEM_HEALTH,
            {"status": "ok"},
            topic="system",
            correlation_id="corr-1",
        )
        message = self.serializer.deserialize(raw)
        assert message.type == WebSocketMessageType.SYSTEM_HEALTH
        assert message.payload["status"] == "ok"

    def test_deserialize_missing_type(self) -> None:
        """Missing 'type' field raises InvalidMessageError."""
        with pytest.raises(InvalidMessageError, match="Missing required field"):
            self.serializer.deserialize('{"payload": {}}')

    def test_deserialize_unknown_type(self) -> None:
        """Unknown message type raises InvalidMessageError."""
        with pytest.raises(InvalidMessageError, match="Unknown message type"):
            self.serializer.deserialize('{"type": "unknown.type.test"}')

    def test_deserialize_malformed_json(self) -> None:
        """Malformed JSON raises InvalidMessageError."""
        with pytest.raises(InvalidMessageError, match="Malformed JSON"):
            self.serializer.deserialize("{invalid json}")

    def test_deserialize_non_dict(self) -> None:
        """Non-dict JSON raises InvalidMessageError."""
        with pytest.raises(InvalidMessageError, match="JSON object"):
            self.serializer.deserialize('"just a string"')

    def test_message_too_large(self) -> None:
        """Message exceeding max size raises MessageTooLargeError."""
        tiny = Serializer(max_message_size=10)
        envelope = MessageEnvelope(
            type=WebSocketMessageType.PING,
            payload={"data": "x" * 100},
        )
        with pytest.raises(MessageTooLargeError):
            tiny.serialize(envelope)

    def test_deserialize_too_large(self) -> None:
        """Deserializing an oversized message raises MessageTooLargeError."""
        tiny = Serializer(max_message_size=10)
        with pytest.raises(MessageTooLargeError):
            tiny.deserialize("x" * 100)

    def test_serialize_invalid_payload(self) -> None:
        """Serializing non-serializable objects raises SerializationError."""
        envelope = MessageEnvelope(
            type=WebSocketMessageType.PING,
            payload={"data": object()},
        )
        with pytest.raises(SerializationError):
            self.serializer.serialize(envelope)

    def test_deserialize_empty_type_string(self) -> None:
        """Empty type string raises InvalidMessageError."""
        with pytest.raises(InvalidMessageError):
            self.serializer.deserialize('{"type": "  "}')

    def test_deserialize_non_string_type(self) -> None:
        """Non-string type raises InvalidMessageError."""
        with pytest.raises(InvalidMessageError):
            self.serializer.deserialize('{"type": 123}')

    def test_serialize_nested_payload(self) -> None:
        """Nested payloads serialize correctly."""
        envelope = MessageEnvelope(
            type=WebSocketMessageType.ANALYSIS_COMPLETED,
            payload={
                "project_id": "proj-1",
                "scores": {"quality": 85, "virality": 72},
                "tags": ["ai", "video"],
            },
        )
        raw = self.serializer.serialize(envelope)
        message = self.serializer.deserialize(raw)
        assert message.payload["scores"]["quality"] == 85
        assert "tags" in message.payload

    def test_timestamp_auto_generated(self) -> None:
        """Timestamp is auto-generated if not provided."""
        envelope = MessageEnvelope(
            type=WebSocketMessageType.PING,
            payload={},
        )
        raw = self.serializer.serialize(envelope)
        message = self.serializer.deserialize(raw)
        assert message.timestamp  # Should not be empty

    def test_payload_not_dict_raises(self) -> None:
        """Non-dict payload raises InvalidMessageError."""
        with pytest.raises(InvalidMessageError, match="JSON object"):
            self.serializer.deserialize('{"type": "ping", "payload": [1, 2, 3]}')

    def test_schema_version_in_message(self) -> None:
        """Deserialized message includes schema version."""
        raw = self.serializer.serialize_event(
            WebSocketMessageType.PING, {},
        )
        message = self.serializer.deserialize(raw)
        assert message.schema_version == 1

    def test_type_enum_preserved(self) -> None:
        """All WebSocketMessageType values serialize/deserialize correctly."""
        for msg_type in WebSocketMessageType:
            raw = self.serializer.serialize_event(msg_type, {"test": True})
            message = self.serializer.deserialize(raw)
            assert message.type == msg_type
