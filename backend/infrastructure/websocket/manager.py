"""WebSocket Manager — facade integrating all WebSocket components.

Coordinates:
- ConnectionManager (connect/disconnect lifecycle)
- SubscriptionManager (topic subscriptions)
- EventBus (event publishing and routing)
- HeartbeatMonitor (ping/pong, dead detection)
- SecurityValidator (rate limiting, payload validation)
- Serializer (JSON with extended types)

Architecture:
- Pure infrastructure — no business logic
- Integrates A2 (Config), A3 (Logging), B1 (Domain Events)
- Delegates to specialized managers for each concern
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any

from backend.infrastructure.logging.logger import get_logger
from backend.infrastructure.websocket.connection import ConnectionManager
from backend.infrastructure.websocket.event_bus import EventBus
from backend.infrastructure.websocket.exceptions import (
    ConnectionClosedError,
    InvalidMessageError,
    MessageTooLargeError,
    RateLimitExceededError,
    SubscriptionError,
    WebSocketError,
)
from backend.infrastructure.websocket.heartbeat import HeartbeatMonitor
from backend.infrastructure.websocket.models import (
    ClientInfo,
    MessageEnvelope,
    ProgressUpdate,
    SubscriptionTopic,
    WebSocketEvent,
    WebSocketMessage,
    WebSocketMessageType,
)
from backend.infrastructure.websocket.security import SecurityValidator
from backend.infrastructure.websocket.serializer import Serializer
from backend.infrastructure.websocket.subscription import SubscriptionManager

logger = get_logger(__name__)

# Type for a WebSocket send callable
SendCallable = Callable[[str, str | bytes], Coroutine[Any, Any, None]]


class WebSocketManager:
    """Central facade for all WebSocket infrastructure.

    Integrates connection, subscription, event bus, heartbeat,
    security, and serialization into a single interface.

    Usage:
        manager = WebSocketManager()
        await manager.handle_connect("client-1", send_fn)
        await manager.handle_message("client-1", raw_message)
        await manager.handle_disconnect("client-1")
        await manager.broadcast_event(event)
        await manager.shutdown()
    """

    def __init__(
        self,
        *,
        max_clients: int = 100,
        max_subscriptions_per_client: int = 50,
        heartbeat_interval: float = 30.0,
        heartbeat_timeout: float = 120.0,
        max_message_size: int = 256 * 1024,
        rate_limit: int = 100,
        rate_window_seconds: int = 60,
        ordered_delivery: bool = True,
    ) -> None:
        # Create sub-components
        self.serializer = Serializer(max_message_size=max_message_size)
        self.connection_manager = ConnectionManager(max_clients=max_clients)
        self.subscription_manager = SubscriptionManager(
            max_subscriptions_per_client=max_subscriptions_per_client,
        )
        self.security = SecurityValidator(
            max_message_size=max_message_size,
            rate_limit=rate_limit,
            rate_window_seconds=rate_window_seconds,
        )

        # Event bus (requires send function — set in handle_connect)
        self.event_bus = EventBus(
            serializer=self.serializer,
            send_function=self._send_to_client,
            ordered_delivery=ordered_delivery,
        )

        # Heartbeat monitor (requires send and disconnect functions)
        self.heartbeat = HeartbeatMonitor(
            send_function=self._send_envelope_to_client,
            disconnect_function=self._handle_timeout_disconnect,
            interval_seconds=heartbeat_interval,
            timeout_seconds=heartbeat_timeout,
        )

        # Client send function storage
        self._client_send_fns: dict[str, SendCallable] = {}
        self._lock = asyncio.Lock()
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._cleanup_task: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------
    # Connection Lifecycle
    # ------------------------------------------------------------------

    async def handle_connect(
        self,
        client_id: str,
        send_function: SendCallable,
        *,
        remote_addr: str = "",
        user_agent: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ClientInfo:
        """Handle a new WebSocket connection.

        Args:
            client_id: Unique client identifier
            send_function: Async callable to send data to this client
            remote_addr: Client IP address
            user_agent: Client user agent string
            metadata: Arbitrary client metadata

        Returns:
            ClientInfo for the connected client

        Raises:
            MaxClientsReachedError: If server is at capacity
        """
        async with self._lock:
            self._client_send_fns[client_id] = send_function

        info = await self.connection_manager.connect(
            client_id,
            remote_addr=remote_addr,
            user_agent=user_agent,
            metadata=metadata,
        )

        # Start heartbeat if not running
        await self._ensure_heartbeat_running()

        return info

    async def handle_disconnect(
        self,
        client_id: str,
        *,
        reason: str = "",
    ) -> None:
        """Handle a client disconnect.

        Args:
            client_id: Disconnecting client
            reason: Optional reason for disconnect
        """
        await self.connection_manager.disconnect(client_id, reason=reason)
        await self.subscription_manager.remove_client(client_id)
        await self.security.reset_rate_limit(client_id)

        async with self._lock:
            self._client_send_fns.pop(client_id, None)

        logger.info(
            "client_disconnected_cleanup",
            extra={"client_id": client_id, "reason": reason or "unknown"},
        )

    async def handle_message(
        self,
        client_id: str,
        raw_message: str,
    ) -> WebSocketMessage | None:
        """Handle an incoming message from a client.

        Validates, parses, and routes the message.
        Returns the parsed message for further handling by the event loop.

        Args:
            client_id: Sending client
            raw_message: Raw JSON string from the WebSocket

        Returns:
            Parsed WebSocketMessage, or None if message was handled internally

        Raises:
            Various WebSocketError subclasses for invalid messages
        """
        try:
            # Validate and parse
            message = await self.security.validate_message(raw_message, client_id)

            # Update activity timestamp
            await self.connection_manager.update_activity(client_id)

            # Handle built-in message types (ping, pong, subscribe, unsubscribe)
            # built-in handlers return None when message is handled internally
            # or return the message for application-level handling
            response = await self._handle_builtin(client_id, message)
            if response is not None:
                return response
            return None

        except (InvalidMessageError, MessageTooLargeError, RateLimitExceededError) as exc:
            # Send error back to client
            await self._send_error(client_id, exc)
            return None

        except Exception as exc:
            logger.error(
                "handle_message_error",
                extra={
                    "client_id": client_id,
                    "error": str(exc),
                },
            )
            await self._send_error(client_id, WebSocketError(
                "ERR-WS-INTERNAL",
                f"Internal error processing message: {exc}",
            ))
            return None

    # ------------------------------------------------------------------
    # Event Publishing
    # ------------------------------------------------------------------

    async def publish_event(
        self,
        event: WebSocketEvent,
        *,
        skip_dedup: bool = False,
    ) -> int:
        """Publish an event to all topic subscribers.

        Args:
            event: Event to publish
            skip_dedup: Skip deduplication check

        Returns:
            Number of clients the event was sent to
        """
        topic = event.topic or self._topic_for_type(event.type)
        subscribers = self.subscription_manager.get_subscribers(topic)

        if not subscribers:
            return 0

        # Serialize once, send to all subscribers
        try:
            serialized = self.serializer.serialize_event(
                event.type,
                event.payload,
                topic=topic,
                correlation_id=event.correlation_id,
            )

            sent_count = 0
            for subscriber_id in subscribers:
                try:
                    await self._send_to_client(subscriber_id, serialized)
                    sent_count += 1
                except (ConnectionClosedError, OSError):
                    continue

            return sent_count

        except Exception as exc:
            logger.warning(
                "publish_event_failed",
                extra={
                    "type": event.type.value,
                    "topic": topic,
                    "subscribers": len(subscribers),
                    "error": str(exc),
                },
            )
            return 0

    async def broadcast_event(
        self,
        event: WebSocketEvent,
        *,
        skip_dedup: bool = False,
    ) -> int:
        """Broadcast an event to ALL connected clients.

        Args:
            event: Event to broadcast
            skip_dedup: Skip deduplication check

        Returns:
            Number of clients the event was sent to
        """
        clients = await self.connection_manager.get_alive_clients()
        if not clients:
            return 0

        serialized = self.serializer.serialize_event(
            event.type,
            event.payload,
            topic="*",
            correlation_id=event.correlation_id,
        )

        sent_count = 0
        for client in clients:
            try:
                await self._send_to_client(client.client_id, serialized)
                sent_count += 1
            except (ConnectionClosedError, OSError):
                continue

        logger.debug(
            "event_broadcast",
            extra={
                "type": event.type.value,
                "clients": sent_count,
                "total_clients": len(clients),
            },
        )
        return sent_count

    async def emit_to_client(
        self,
        client_id: str,
        event: WebSocketEvent,
    ) -> bool:
        """Emit an event directly to a specific client.

        Args:
            client_id: Target client
            event: Event to send

        Returns:
            True if sent, False if client not found
        """
        try:
            serialized = self.serializer.serialize_event(
                event.type,
                event.payload,
                topic=event.topic,
                correlation_id=event.correlation_id,
            )
            await self._send_to_client(client_id, serialized)
            return True
        except (ConnectionClosedError, OSError):
            return False

    async def emit_to_project(
        self,
        project_id: str,
        event: WebSocketEvent,
    ) -> int:
        """Emit an event to all subscribers of a project's topics.

        Args:
            project_id: Target project
            event: Event to send

        Returns:
            Number of clients the event was sent to
        """
        project_topics = SubscriptionTopic.for_project(project_id)
        event.topic = project_topics[0] if project_topics else project_id
        return await self.publish_event(event)

    async def emit_progress(
        self,
        project_id: str,
        update: ProgressUpdate,
    ) -> int:
        """Emit a progress update to project subscribers.

        Args:
            project_id: Target project
            update: Progress update data

        Returns:
            Number of clients the update was sent to
        """
        topic = SubscriptionTopic.PROJECT.value.format(project_id=project_id)
        type_map = {
            "analysis": WebSocketMessageType.ANALYSIS_PROGRESS,
            "import": WebSocketMessageType.VIDEO_IMPORT_PROGRESS,
            "clip": WebSocketMessageType.CLIP_GENERATION_PROGRESS,
            "caption": WebSocketMessageType.CAPTION_GENERATION_PROGRESS,
            "export": WebSocketMessageType.EXPORT_PROGRESS,
            "model": WebSocketMessageType.MODEL_DOWNLOAD_PROGRESS,
            "queue": WebSocketMessageType.QUEUE_JOB_PROGRESS,
        }
        msg_type = type_map.get(update.operation, WebSocketMessageType.SYSTEM_EVENT)

        event = WebSocketEvent(
            type=msg_type,
            payload={
                "operation": update.operation,
                "progress": update.progress,
                "stage": update.stage,
                "message": update.message or "",
                "stage_progress": update.stage_progress,
                "estimated_remaining_seconds": update.estimated_remaining_seconds,
                "items_completed": update.items_completed,
                "items_total": update.items_total,
                "error_message": update.error_message,
                "metadata": update.metadata,
            },
            topic=topic,
        )
        return await self.publish_event(event)

    # ------------------------------------------------------------------
    # Subscription Management
    # ------------------------------------------------------------------

    async def subscribe(
        self,
        client_id: str,
        topic: str,
    ) -> bool:
        """Subscribe a client to a topic.

        Args:
            client_id: Client to subscribe
            topic: Topic to subscribe to

        Returns:
            True if subscription was new
        """
        self.security.validate_topic(topic)
        return await self.subscription_manager.subscribe(client_id, topic)

    async def unsubscribe(
        self,
        client_id: str,
        topic: str,
    ) -> bool:
        """Unsubscribe a client from a topic.

        Args:
            client_id: Client to unsubscribe
            topic: Topic to unsubscribe from

        Returns:
            True if was subscribed
        """
        return await self.subscription_manager.unsubscribe(client_id, topic)

    async def subscribe_to_project(
        self,
        client_id: str,
        project_id: str,
    ) -> int:
        """Subscribe a client to all project topics.

        Args:
            client_id: Client to subscribe
            project_id: Project to subscribe to

        Returns:
            Number of topics subscribed to
        """
        return await self.subscription_manager.subscribe_to_project(
            client_id, project_id,
        )

    # ------------------------------------------------------------------
    # Heartbeat
    # ------------------------------------------------------------------

    async def send_ping(self, client_id: str) -> bool:
        """Send a ping to a specific client.

        Args:
            client_id: Client to ping

        Returns:
            True if ping was sent
        """
        envelope = MessageEnvelope(
            type=WebSocketMessageType.PING,
            payload={"timestamp": datetime.now(UTC).isoformat()},
        )
        try:
            serialized = self.serializer.serialize(envelope)
            await self._send_to_client(client_id, serialized)
            return True
        except (ConnectionClosedError, OSError):
            return False

    async def handle_pong(self, client_id: str) -> None:
        """Record a pong response from a client.

        Args:
            client_id: Client that responded
        """
        await self.heartbeat.record_pong(client_id)

    # ------------------------------------------------------------------
    # Shutdown & Maintenance
    # ------------------------------------------------------------------

    async def shutdown(self) -> None:
        """Gracefully shut down all WebSocket infrastructure."""
        logger.info("ws_manager_shutdown_started")

        self.heartbeat.stop()
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()

        await self.connection_manager.shutdown()
        async with self._lock:
            self._client_send_fns.clear()

        logger.info("ws_manager_shutdown_complete")

    async def cleanup(self) -> dict[str, int]:
        """Run periodic maintenance tasks.

        Returns:
            Dict with counts of cleaned resources
        """
        stale = await self.connection_manager.cleanup_stale()
        rate_cleaned = await self.security.cleanup_rate_limits()
        dedup_trimmed = await self.event_bus.trim_delivered_events()

        return {
            "stale_connections_removed": stale,
            "rate_limit_entries_cleaned": rate_cleaned,
            "dedup_events_trimmed": dedup_trimmed,
        }

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    async def get_stats(self) -> dict[str, Any]:
        """Get current WebSocket manager statistics.

        Returns:
            Dict with connection, subscription, and heartbeat stats
        """
        return {
            "active_connections": await self.connection_manager.get_client_count(),
            "total_connections": self.connection_manager.total_count,
            "total_subscriptions": self.subscription_manager.total_subscriptions,
            "unique_topics": len(self.subscription_manager.unique_topics),
            "heartbeat_running": self.heartbeat.is_running,
            "max_clients": self.connection_manager.max_clients,
            "is_shutting_down": self.connection_manager.is_shutting_down,
            "topic_summary": self.subscription_manager.get_all_topic_subscribers(),
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _send_to_client(self, client_id: str, data: str | bytes) -> None:
        """Send serialized data to a client.

        Args:
            client_id: Target client
            data: Serialized data (JSON string or bytes)

        Raises:
            ConnectionClosedError: If client not found or send fails
        """
        send_fn = self._client_send_fns.get(client_id)
        if send_fn is None:
            raise ConnectionClosedError(client_id)

        try:
            await send_fn(client_id, data)
        except (ConnectionClosedError, OSError) as exc:
            # Client disconnected
            await self.handle_disconnect(client_id, reason=str(exc))
            raise

    async def _send_envelope_to_client(
        self,
        client_id: str,
        envelope: MessageEnvelope,
    ) -> None:
        """Serialize and send a MessageEnvelope to a client.

        Args:
            client_id: Target client
            envelope: Message to send
        """
        serialized = self.serializer.serialize(envelope)
        await self._send_to_client(client_id, serialized)

    async def _handle_builtin(
        self,
        client_id: str,
        message: WebSocketMessage,
    ) -> WebSocketMessage | None:
        """Handle built-in message types (ping, subscribe, etc.).

        Args:
            client_id: Sending client
            message: Parsed message

        Returns:
            The message for further processing, or None if handled
        """
        if message.type == WebSocketMessageType.PING:
            # Respond with pong
            pong = MessageEnvelope(
                type=WebSocketMessageType.PONG,
                payload=message.payload,
                correlation_id=message.correlation_id,
            )
            serialized = self.serializer.serialize(pong)
            await self._send_to_client(client_id, serialized)
            return None

        if message.type == WebSocketMessageType.PONG:
            await self.heartbeat.record_pong(client_id)
            return None

        if message.type == WebSocketMessageType.SUBSCRIBE:
            topic = message.payload.get("topic", "")
            try:
                self.security.validate_topic(topic)
                new_sub = await self.subscribe(client_id, topic)
                # Send confirmation
                confirm = MessageEnvelope(
                    type=WebSocketMessageType.SUBSCRIPTION_CONFIRMED,
                    payload={"topic": topic, "new": new_sub},
                    correlation_id=message.correlation_id,
                )
                serialized = self.serializer.serialize(confirm)
                await self._send_to_client(client_id, serialized)
            except (SubscriptionError, InvalidMessageError) as exc:
                await self._send_error(client_id, exc)
            return None

        if message.type == WebSocketMessageType.UNSUBSCRIBE:
            topic = message.payload.get("topic", "")
            removed = await self.unsubscribe(client_id, topic)
            confirm = MessageEnvelope(
                type=WebSocketMessageType.SUBSCRIPTION_REMOVED,
                payload={"topic": topic, "removed": removed},
                correlation_id=message.correlation_id,
            )
            serialized = self.serializer.serialize(confirm)
            await self._send_to_client(client_id, serialized)
            return None

        # All other messages pass through for application handling
        return message

    async def _handle_timeout_disconnect(self, client_id: str) -> None:
        """Handle a heartbeat timeout disconnect.

        Args:
            client_id: Client to disconnect
        """
        logger.warning(
            "heartbeat_timeout_disconnect",
            extra={"client_id": client_id},
        )
        await self.handle_disconnect(client_id, reason="heartbeat_timeout")

    async def _send_error(
        self,
        client_id: str,
        error: WebSocketError,
    ) -> None:
        """Send an error message to a client.

        Args:
            client_id: Target client
            error: Error to send
        """
        try:
            envelope = MessageEnvelope(
                type=WebSocketMessageType.ERROR,
                payload=error.to_dict(),
            )
            serialized = self.serializer.serialize(envelope)
            await self._send_to_client(client_id, serialized)
        except (ConnectionClosedError, OSError):
            pass

    @staticmethod
    def _topic_for_type(msg_type: WebSocketMessageType) -> str:
        """Get the default topic for a message type."""
        type_to_topic: dict[WebSocketMessageType, str] = {
            WebSocketMessageType.PROJECT_CREATED: "projects",
            WebSocketMessageType.PROJECT_UPDATED: "projects",
            WebSocketMessageType.PROJECT_DELETED: "projects",
            WebSocketMessageType.SYSTEM_HEALTH: "system",
            WebSocketMessageType.SYSTEM_SETTINGS_CHANGED: "settings",
            WebSocketMessageType.PLUGIN_LOADED: "plugins",
            WebSocketMessageType.PLUGIN_UNLOADED: "plugins",
        }
        return type_to_topic.get(msg_type, "system")

    async def _ensure_heartbeat_running(self) -> None:
        """Start heartbeat monitoring if not already running."""
        if not self.heartbeat.is_running:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def _heartbeat_loop(self) -> None:
        """Periodic heartbeat check for all connected clients."""
        self.heartbeat.start()
        try:
            while self.heartbeat.is_running:
                await asyncio.sleep(self.heartbeat.interval_seconds)

                # Send pings to all alive clients
                clients = await self.connection_manager.get_alive_clients()
                for client in clients:
                    await self.heartbeat.mark_ping_sent(client.client_id)
                    with contextlib.suppress(Exception):
                        await self.send_ping(client.client_id)

                # Check for timeouts
                for client in clients:
                    try:
                        timed_out = await self.heartbeat.check_timeout(
                            client.client_id,
                        )
                        if timed_out:
                            await self._handle_timeout_disconnect(client.client_id)
                    except Exception:
                        pass

                # Periodic cleanup
                await self.cleanup()

        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error(
                "heartbeat_loop_error",
                extra={"error": str(exc)},
            )
