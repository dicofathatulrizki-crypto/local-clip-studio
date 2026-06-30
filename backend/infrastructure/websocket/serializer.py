"""JSON serialization for WebSocket messages with extended type support.

Handles:
- datetime → ISO 8601 string
- UUID → string
- Enum → value
- Custom objects via to_dict() protocol
- Schema versioning for forward/backward compatibility
- Validation on deserialization
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

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

# Maximum message size in bytes (default 256KB)
_DEFAULT_MAX_MESSAGE_SIZE = 256 * 1024

# Current schema version
_CURRENT_SCHEMA_VERSION = 1

# Supported schema versions (for backward compatibility)
_SUPPORTED_SCHEMA_VERSIONS = {1}


class Serializer:
    """JSON serializer for WebSocket messages.

    Handles extended types (datetime, UUID, Enum) and provides
    schema versioning for forward/backward compatibility.

    Usage:
        serializer = Serializer(max_message_size=256 * 1024)
        data = serializer.serialize(envelope)
        envelope = serializer.deserialize(data)
    """

    def __init__(self, max_message_size: int = _DEFAULT_MAX_MESSAGE_SIZE) -> None:
        self._max_message_size = max_message_size

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def serialize(
        self,
        envelope: MessageEnvelope,
        *,
        validate: bool = True,
    ) -> str:
        """Serialize a MessageEnvelope to a JSON string.

        Args:
            envelope: The message envelope to serialize
            validate: If True, validates payload before serialization

        Returns:
            JSON-encoded string

        Raises:
            MessageTooLargeError: If serialized message exceeds max size
            SerializationError: If serialization fails
        """
        try:
            data = self._envelope_to_dict(envelope)
            raw = json.dumps(data, default=self._json_default, ensure_ascii=False)

            if len(raw) > self._max_message_size:
                raise MessageTooLargeError(
                    len(raw), self._max_message_size,
                    {"type": envelope.type.value},
                )

            return raw
        except MessageTooLargeError:
            raise
        except (TypeError, ValueError) as exc:
            raise SerializationError(
                f"Failed to serialize message: {exc}",
                {"type": envelope.type.value if hasattr(envelope, "type") else "unknown"},
            ) from exc

    def deserialize(
        self,
        raw: str,
        *,
        validate: bool = True,
    ) -> WebSocketMessage:
        """Deserialize a JSON string to a WebSocketMessage.

        Args:
            raw: JSON-encoded message string
            validate: If True, validates message structure

        Returns:
            Parsed WebSocketMessage

        Raises:
            InvalidMessageError: If message is malformed
            SerializationError: If deserialization fails
        """
        try:
            if len(raw) > self._max_message_size:
                raise MessageTooLargeError(
                    len(raw), self._max_message_size,
                )

            data: dict[str, Any] = json.loads(raw)

            if not isinstance(data, dict):
                raise InvalidMessageError(
                    "Message must be a JSON object",
                    {"received_type": type(data).__name__},
                )

            if validate:
                data = self._validate_message(data)

            return self._dict_to_message(data)

        except json.JSONDecodeError as exc:
            raise InvalidMessageError(
                f"Malformed JSON: {exc}",
                {"position": exc.pos, "line": exc.lineno},
            ) from exc
        except MessageTooLargeError:
            raise
        except InvalidMessageError:
            raise
        except (KeyError, ValueError, TypeError) as exc:
            raise SerializationError(
                f"Failed to deserialize message: {exc}",
            ) from exc

    def serialize_event(
        self,
        event_type: WebSocketMessageType,
        payload: dict[str, Any],
        *,
        topic: str = "",
        correlation_id: str = "",
    ) -> str:
        """Convenience: create and serialize an event in one call.

        Args:
            event_type: The message type for the event
            payload: Event payload data
            topic: Optional topic for routing
            correlation_id: Optional correlation ID

        Returns:
            Serialized JSON string
        """
        envelope = MessageEnvelope(
            type=event_type,
            payload=payload,
            topic=topic,
            correlation_id=correlation_id,
        )
        return self.serialize(envelope)

    # ------------------------------------------------------------------
    # Internal: Serialization
    # ------------------------------------------------------------------

    @staticmethod
    def _json_default(obj: Any) -> str:
        """JSON default serializer for extended types."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, Enum):
            return str(obj.value)
        if hasattr(obj, "to_dict"):
            result = obj.to_dict()
            if isinstance(result, str):
                return result
            return str(result)
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    @staticmethod
    def _envelope_to_dict(envelope: MessageEnvelope) -> dict[str, Any]:
        """Convert a MessageEnvelope to a JSON-serializable dict."""
        return {
            "type": envelope.type.value,
            "payload": envelope.payload,
            "event_id": envelope.event_id,
            "correlation_id": envelope.correlation_id,
            "timestamp": envelope.timestamp,
            "schema_version": envelope.schema_version,
            "topic": envelope.topic,
        }

    # ------------------------------------------------------------------
    # Internal: Validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_message(data: dict[str, Any]) -> dict[str, Any]:
        """Validate a deserialized message structure.

        Args:
            data: Parsed JSON dict

        Returns:
            Validated data (possibly with defaults applied)

        Raises:
            InvalidMessageError: If required fields are missing
        """
        # Check required fields
        if "type" not in data:
            raise InvalidMessageError(
                "Missing required field: 'type'",
                {"available_keys": list(data.keys())},
            )

        msg_type = data["type"]
        if not isinstance(msg_type, str) or not msg_type.strip():
            raise InvalidMessageError(
                "'type' must be a non-empty string",
                {"type": msg_type},
            )

        # Validate type is known
        try:
            WebSocketMessageType(msg_type)
        except ValueError:
            raise InvalidMessageError(
                f"Unknown message type: '{msg_type}'",
                {"type": msg_type, "known_types": [t.value for t in WebSocketMessageType]},
            )

        # Check schema version compatibility
        schema_version = data.get("schema_version", _CURRENT_SCHEMA_VERSION)
        if schema_version not in _SUPPORTED_SCHEMA_VERSIONS:
            raise InvalidMessageError(
                f"Unsupported schema version: {schema_version}",
                {
                    "version": schema_version,
                    "supported_versions": sorted(_SUPPORTED_SCHEMA_VERSIONS),
                },
            )

        # Ensure payload is a dict
        if "payload" in data and not isinstance(data["payload"], dict):
            raise InvalidMessageError(
                "'payload' must be a JSON object",
                {"payload_type": type(data["payload"]).__name__},
            )

        return data

    @staticmethod
    def _dict_to_message(data: dict[str, Any]) -> WebSocketMessage:
        """Convert a validated dict to a WebSocketMessage."""
        return WebSocketMessage(
            type=WebSocketMessageType(data["type"]),
            payload=data.get("payload", {}),
            client_id=data.get("client_id", ""),
            event_id=data.get("event_id", ""),
            correlation_id=data.get("correlation_id", ""),
            timestamp=data.get("timestamp", ""),
            schema_version=data.get("schema_version", _CURRENT_SCHEMA_VERSION),
            topic=data.get("topic", ""),
        )
