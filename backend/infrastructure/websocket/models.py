"""WebSocket data models and message types.

Defines strongly typed message envelopes, event payloads, client metadata,
subscription topics, and progress update structures.

Architecture:
- Pure data models with no business logic
- All payloads are typed — no stringly-typed content
- Schema versioning for forward/backward compatibility
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

# ---------------------------------------------------------------------------
# Message Types
# ---------------------------------------------------------------------------


class WebSocketMessageType(str, Enum):
    """All supported WebSocket message types.

    Follows pattern: ACTION_DIRECTION or DOMAIN_EVENT
    """

    # Connection lifecycle
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    RECONNECT = "reconnect"
    ERROR = "error"
    ACK = "ack"

    # Heartbeat
    PING = "ping"
    PONG = "pong"

    # Subscription management
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    SUBSCRIPTION_CONFIRMED = "subscription_confirmed"
    SUBSCRIPTION_REMOVED = "subscription_removed"

    # Project events
    PROJECT_CREATED = "project.created"
    PROJECT_UPDATED = "project.updated"
    PROJECT_DELETED = "project.deleted"
    PROJECT_ARCHIVED = "project.archived"
    PROJECT_RESTORED = "project.restored"

    # Video import events
    VIDEO_IMPORT_STARTED = "video.import.started"
    VIDEO_IMPORT_PROGRESS = "video.import.progress"
    VIDEO_IMPORT_COMPLETED = "video.import.completed"
    VIDEO_IMPORT_FAILED = "video.import.failed"

    # Analysis pipeline events
    ANALYSIS_STARTED = "analysis.started"
    ANALYSIS_PROGRESS = "analysis.progress"
    ANALYSIS_STAGE_COMPLETED = "analysis.stage_completed"
    ANALYSIS_COMPLETED = "analysis.completed"
    ANALYSIS_FAILED = "analysis.failed"

    # Clip generation events
    CLIP_GENERATION_STARTED = "clip.generation.started"
    CLIP_GENERATION_PROGRESS = "clip.generation.progress"
    CLIP_GENERATED = "clip.generated"
    CLIP_ACCEPTED = "clip.accepted"
    CLIP_REJECTED = "clip.rejected"

    # Caption events
    CAPTION_GENERATION_STARTED = "caption.generation.started"
    CAPTION_GENERATION_PROGRESS = "caption.generation.progress"
    CAPTIONS_GENERATED = "caption.generated"

    # Export events
    EXPORT_STARTED = "export.started"
    EXPORT_PROGRESS = "export.progress"
    EXPORT_COMPLETED = "export.completed"
    EXPORT_FAILED = "export.failed"

    # Plugin events
    PLUGIN_LOADED = "plugin.loaded"
    PLUGIN_UNLOADED = "plugin.unloaded"
    PLUGIN_ERROR = "plugin.error"

    # System events
    SYSTEM_EVENT = "system.event"
    SYSTEM_HEALTH = "system.health"
    SYSTEM_SETTINGS_CHANGED = "system.settings.changed"
    SYSTEM_MAINTENANCE = "system.maintenance"

    # Model download events
    MODEL_DOWNLOAD_STARTED = "model.download.started"
    MODEL_DOWNLOAD_PROGRESS = "model.download.progress"
    MODEL_DOWNLOAD_COMPLETED = "model.download.completed"
    MODEL_DOWNLOAD_FAILED = "model.download.failed"

    # Queue events
    QUEUE_JOB_STARTED = "queue.job.started"
    QUEUE_JOB_PROGRESS = "queue.job.progress"
    QUEUE_JOB_COMPLETED = "queue.job.completed"
    QUEUE_JOB_FAILED = "queue.job.failed"

    # Settings events
    SETTINGS_CHANGED = "settings.changed"


# ---------------------------------------------------------------------------
# Subscription Topics
# ---------------------------------------------------------------------------


class SubscriptionTopic(str, Enum):
    """Topics that clients can subscribe to for receiving events."""

    # Global system topics
    SYSTEM = "system"
    SETTINGS = "settings"
    PLUGINS = "plugins"

    # Per-project topics (requires project_id)
    PROJECT = "project.{project_id}"
    PROJECT_VIDEOS = "project.{project_id}.videos"
    PROJECT_ANALYSIS = "project.{project_id}.analysis"
    PROJECT_CLIPS = "project.{project_id}.clips"
    PROJECT_EXPORTS = "project.{project_id}.exports"
    PROJECT_CAPTIONS = "project.{project_id}.captions"

    # Global pipeline topics
    ANALYSIS_ALL = "analysis"
    EXPORTS_ALL = "exports"
    MODELS = "models"
    QUEUE = "queue"

    @classmethod
    def for_project(cls, project_id: str) -> list[str]:
        """Get all topic patterns for a specific project.

        Args:
            project_id: The project UUID

        Returns:
            List of resolved topic strings for this project
        """
        return [
            cls.PROJECT.value.format(project_id=project_id),
            cls.PROJECT_VIDEOS.value.format(project_id=project_id),
            cls.PROJECT_ANALYSIS.value.format(project_id=project_id),
            cls.PROJECT_CLIPS.value.format(project_id=project_id),
            cls.PROJECT_EXPORTS.value.format(project_id=project_id),
            cls.PROJECT_CAPTIONS.value.format(project_id=project_id),
        ]

    @classmethod
    def resolve_topic(cls, topic: str, **kwargs: str) -> str:
        """Resolve a topic template with parameters.

        Args:
            topic: Topic string, possibly with {placeholders}
            **kwargs: Values for placeholders

        Returns:
            Resolved topic string
        """
        if "{" in topic:
            return topic.format(**kwargs)
        return topic


# ---------------------------------------------------------------------------
# Message Envelope
# ---------------------------------------------------------------------------


@dataclass
class MessageEnvelope:
    """Envelope wrapping every WebSocket message.

    Provides schema versioning, deduplication via event_id,
    and correlation for request-response patterns.
    """

    type: WebSocketMessageType
    payload: dict[str, Any] = field(default_factory=dict)
    event_id: str = ""
    correlation_id: str = ""
    timestamp: str = ""
    schema_version: int = 1
    topic: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            object.__setattr__(
                self, "timestamp", datetime.now(UTC).isoformat()
            )


@dataclass
class WebSocketMessage:
    """A decoded/deserialized WebSocket message ready for dispatch."""

    type: WebSocketMessageType
    payload: dict[str, Any]
    client_id: str = ""
    event_id: str = ""
    correlation_id: str = ""
    timestamp: str = ""
    schema_version: int = 1
    topic: str = ""


@dataclass
class WebSocketEvent:
    """An event to be published through the event bus.

    Carries typed payload data and routing metadata.
    """

    type: WebSocketMessageType
    payload: dict[str, Any] = field(default_factory=dict)
    topic: str = ""
    project_id: str = ""
    client_id: str = ""
    event_id: str = ""
    correlation_id: str = ""
    timestamp: str = ""


# ---------------------------------------------------------------------------
# Client Metadata
# ---------------------------------------------------------------------------


@dataclass
class ClientInfo:
    """Metadata about a connected WebSocket client."""

    client_id: str
    connected_at: datetime = field(default_factory=datetime.now)
    last_activity_at: datetime = field(default_factory=datetime.now)
    user_agent: str = ""
    remote_addr: str = ""
    subscriptions: set[str] = field(default_factory=set)
    metadata: dict[str, Any] = field(default_factory=dict)
    is_alive: bool = True
    protocol_version: int = 1


# ---------------------------------------------------------------------------
# Progress Update
# ---------------------------------------------------------------------------


@dataclass
class ProgressUpdate:
    """Standard progress update for long-running operations.

    Used across all pipeline stages for consistent progress reporting.
    """

    operation: str
    progress: float  # 0.0 to 1.0
    stage: str = ""
    message: str = ""
    stage_progress: float | None = None  # 0.0 to 1.0 per-stage
    estimated_remaining_seconds: float | None = None
    items_completed: int = 0
    items_total: int = 0
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""
