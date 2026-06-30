"""WebSocket infrastructure for real-time event streaming.

Provides:
- Connection management (connect, disconnect, reconnect, graceful shutdown)
- Subscription management (projects, system, topics)
- Strongly typed event bus (publish, broadcast, emit)
- Serialization with datetime/UUID/enum support and schema versioning
- Heartbeat with ping/pong, dead connection detection, timeout cleanup
- Progress streaming for pipeline stages
- Payload validation, rate limiting, and size limits
- FastAPI WebSocket endpoint integration

Architecture:
- Pure infrastructure layer — no business logic
- No dependency on Services, FFmpeg, HAL, Plugins, or AI pipeline
- Integrates with A2 (Configuration), A3 (Logging), B1 (Domain Events)
"""

from __future__ import annotations

from backend.infrastructure.websocket.connection import ConnectionManager
from backend.infrastructure.websocket.event_bus import EventBus
from backend.infrastructure.websocket.exceptions import (
    ConnectionClosedError,
    HeartbeatTimeoutError,
    InvalidMessageError,
    MaxClientsReachedError,
    MessageTooLargeError,
    RateLimitExceededError,
    SubscriptionError,
    WebSocketError,
)
from backend.infrastructure.websocket.handlers import WebSocketHandler
from backend.infrastructure.websocket.heartbeat import HeartbeatMonitor
from backend.infrastructure.websocket.manager import WebSocketManager
from backend.infrastructure.websocket.models import (
    ClientInfo,
    MessageEnvelope,
    ProgressUpdate,
    SubscriptionTopic,
    WebSocketEvent,
    WebSocketMessage,
    WebSocketMessageType,
)
from backend.infrastructure.websocket.serializer import Serializer
from backend.infrastructure.websocket.subscription import SubscriptionManager

__all__ = [
    # Models
    "ClientInfo",
    # Exceptions
    "ConnectionClosedError",
    "ConnectionManager",
    "EventBus",
    "HeartbeatMonitor",
    "HeartbeatTimeoutError",
    "InvalidMessageError",
    "MaxClientsReachedError",
    "MessageEnvelope",
    "MessageTooLargeError",
    "ProgressUpdate",
    "RateLimitExceededError",
    "Serializer",
    "SubscriptionError",
    "SubscriptionManager",
    "SubscriptionTopic",
    "WebSocketError",
    "WebSocketEvent",
    "WebSocketHandler",
    "WebSocketManager",
    "WebSocketMessage",
    "WebSocketMessageType",
]
