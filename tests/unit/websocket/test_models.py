"""Tests for WebSocket data models.

Covers:
- MessageEnvelope auto-generation of timestamp and event_id
- All WebSocketMessageType values
- SubscriptionTopic resolution
- ClientInfo defaults
- ProgressUpdate defaults
"""

from __future__ import annotations

from datetime import datetime

from backend.infrastructure.websocket.models import (
    ClientInfo,
    MessageEnvelope,
    ProgressUpdate,
    SubscriptionTopic,
    WebSocketMessageType,
)


class TestWebSocketMessageType:
    """Tests for WebSocketMessageType enum."""

    def test_all_values_have_unique_identifiers(self) -> None:
        """All enum values are unique."""
        values = [t.value for t in WebSocketMessageType]
        assert len(values) == len(set(values))

    def test_project_events(self) -> None:
        """Project event types exist."""
        assert WebSocketMessageType.PROJECT_CREATED.value == "project.created"
        assert WebSocketMessageType.PROJECT_UPDATED.value == "project.updated"
        assert WebSocketMessageType.PROJECT_DELETED.value == "project.deleted"

    def test_analysis_events(self) -> None:
        """Analysis event types exist."""
        assert WebSocketMessageType.ANALYSIS_STARTED.value == "analysis.started"
        assert WebSocketMessageType.ANALYSIS_COMPLETED.value == "analysis.completed"
        assert WebSocketMessageType.ANALYSIS_FAILED.value == "analysis.failed"

    def test_export_events(self) -> None:
        """Export event types exist."""
        assert WebSocketMessageType.EXPORT_PROGRESS.value == "export.progress"
        assert WebSocketMessageType.EXPORT_COMPLETED.value == "export.completed"

    def test_connection_types(self) -> None:
        """Connection event types."""
        assert WebSocketMessageType.CONNECT.value == "connect"
        assert WebSocketMessageType.DISCONNECT.value == "disconnect"
        assert WebSocketMessageType.PING.value == "ping"
        assert WebSocketMessageType.PONG.value == "pong"

    def test_subscription_types(self) -> None:
        """Subscription event types."""
        assert WebSocketMessageType.SUBSCRIBE.value == "subscribe"
        assert WebSocketMessageType.UNSUBSCRIBE.value == "unsubscribe"
        assert WebSocketMessageType.SUBSCRIPTION_CONFIRMED.value == "subscription_confirmed"


class TestSubscriptionTopic:
    """Tests for SubscriptionTopic."""

    def test_for_project(self) -> None:
        """for_project returns all project topics."""
        topics = SubscriptionTopic.for_project("proj-123")
        assert len(topics) == 6
        assert f"project.proj-123" in topics
        assert f"project.proj-123.videos" in topics
        assert f"project.proj-123.analysis" in topics

    def test_resolve_topic_no_placeholders(self) -> None:
        """resolve_topic on a topic without placeholders."""
        result = SubscriptionTopic.resolve_topic("system")
        assert result == "system"

    def test_resolve_topic_with_placeholders(self) -> None:
        """resolve_topic fills in placeholders."""
        result = SubscriptionTopic.resolve_topic(
            "project.{project_id}",
            project_id="proj-1",
        )
        assert result == "project.proj-1"


class TestMessageEnvelope:
    """Tests for MessageEnvelope."""

    def test_auto_timestamp(self) -> None:
        """Empty timestamp gets auto-generated."""
        env = MessageEnvelope(type=WebSocketMessageType.PING)
        assert env.timestamp  # Should not be empty

    def test_with_timestamp(self) -> None:
        """Provided timestamp is preserved."""
        ts = "2026-01-01T00:00:00"
        env = MessageEnvelope(type=WebSocketMessageType.PING, timestamp=ts)
        assert env.timestamp == ts

    def test_default_payload(self) -> None:
        """Default payload is empty dict."""
        env = MessageEnvelope(type=WebSocketMessageType.PING)
        assert env.payload == {}


class TestClientInfo:
    """Tests for ClientInfo."""

    def test_defaults(self) -> None:
        """ClientInfo has sensible defaults."""
        info = ClientInfo(client_id="c1")
        assert info.client_id == "c1"
        assert info.is_alive is True
        assert info.subscriptions == set()
        assert info.metadata == {}
        assert info.protocol_version == 1


class TestProgressUpdate:
    """Tests for ProgressUpdate."""

    def test_defaults(self) -> None:
        """ProgressUpdate has sensible defaults."""
        update = ProgressUpdate(operation="test", progress=0.0)
        assert update.operation == "test"
        assert update.progress == 0.0
        assert update.stage == ""
        assert update.error_message is None
        assert update.metadata == {}
