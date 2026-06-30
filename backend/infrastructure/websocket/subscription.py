"""Subscription manager — client topic subscriptions.

Responsibilities:
- Client subscription to named topics
- Project-level subscriptions (auto-subscribe to all project events)
- Dynamic subscription changes
- Subscription validation
- Efficient topic→client lookup for event routing
- Max subscription enforcement per client

Thread-safe via asyncio.Lock.
"""

from __future__ import annotations

import asyncio
from typing import Any

from backend.infrastructure.logging.logger import get_logger
from backend.infrastructure.websocket.exceptions import (
    InvalidMessageError,
    SubscriptionError,
)
from backend.infrastructure.websocket.models import SubscriptionTopic

logger = get_logger(__name__)


class SubscriptionManager:
    """Manages topic-based subscriptions for WebSocket clients.

    Maintains bidirectional mappings:
    - client_id → set of subscribed topics
    - topic → set of subscribed client_ids

    Supports project-level bulk subscriptions and dynamic changes.

    Usage:
        mgr = SubscriptionManager(max_subscriptions_per_client=50)
        await mgr.subscribe("client-1", "project.abc")
        await mgr.unsubscribe("client-1", "project.abc")
        clients = mgr.get_subscribers("project.abc")
    """

    def __init__(self, max_subscriptions_per_client: int = 50) -> None:
        self._max_per_client = max_subscriptions_per_client
        self._client_topics: dict[str, set[str]] = {}
        self._topic_clients: dict[str, set[str]] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def total_subscriptions(self) -> int:
        """Total number of client-topic subscriptions."""
        return sum(len(topics) for topics in self._client_topics.values())

    @property
    def unique_topics(self) -> list[str]:
        """List of all topics that have subscribers."""
        return list(self._topic_clients.keys())

    # ------------------------------------------------------------------
    # Subscription Management
    # ------------------------------------------------------------------

    async def subscribe(
        self,
        client_id: str,
        topic: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Subscribe a client to a topic.

        Args:
            client_id: The client to subscribe
            topic: The topic to subscribe to
            metadata: Optional metadata (unused, reserved for future use)

        Returns:
            True if subscription was new, False if already subscribed

        Raises:
            InvalidMessageError: If topic is empty or malformed
            SubscriptionError: If max subscriptions per client reached
        """
        if not topic or not topic.strip():
            msg = "Topic cannot be empty"
            raise InvalidMessageError(
                msg,
                {"client_id": client_id},
            )

        async with self._lock:
            if client_id not in self._client_topics:
                self._client_topics[client_id] = set()

            if topic in self._client_topics[client_id]:
                return False

            if len(self._client_topics[client_id]) >= self._max_per_client:
                msg = f"Max subscriptions ({self._max_per_client}) reached for client"
                raise SubscriptionError(
                    msg,
                    {
                        "client_id": client_id,
                        "current": len(self._client_topics[client_id]),
                        "max": self._max_per_client,
                    },
                )

            self._client_topics[client_id].add(topic)

            if topic not in self._topic_clients:
                self._topic_clients[topic] = set()
            self._topic_clients[topic].add(client_id)

            logger.debug(
                "client_subscribed",
                extra={
                    "client_id": client_id,
                    "topic": topic,
                    "total_subscriptions": self.total_subscriptions,
                },
            )
            return True

    async def unsubscribe(
        self,
        client_id: str,
        topic: str,
    ) -> bool:
        """Unsubscribe a client from a topic.

        Args:
            client_id: The client to unsubscribe
            topic: The topic to unsubscribe from

        Returns:
            True if was subscribed, False if not
        """
        async with self._lock:
            if client_id not in self._client_topics:
                return False

            if topic not in self._client_topics[client_id]:
                return False

            self._client_topics[client_id].discard(topic)

            if topic in self._topic_clients:
                self._topic_clients[topic].discard(client_id)
                if not self._topic_clients[topic]:
                    del self._topic_clients[topic]

            logger.debug(
                "client_unsubscribed",
                extra={
                    "client_id": client_id,
                    "topic": topic,
                    "total_subscriptions": self.total_subscriptions,
                },
            )
            return True

    async def unsubscribe_all(self, client_id: str) -> int:
        """Unsubscribe a client from all topics.

        Args:
            client_id: The client to fully unsubscribe

        Returns:
            Number of topics unsubscribed from
        """
        async with self._lock:
            topics = self._client_topics.pop(client_id, set())
            for topic in topics:
                if topic in self._topic_clients:
                    self._topic_clients[topic].discard(client_id)
                    if not self._topic_clients[topic]:
                        del self._topic_clients[topic]
            return len(topics)

    async def subscribe_to_project(
        self,
        client_id: str,
        project_id: str,
    ) -> int:
        """Subscribe a client to all project-related topics.

        Args:
            client_id: The client to subscribe
            project_id: The project to subscribe to

        Returns:
            Number of topics subscribed to
        """
        topics = SubscriptionTopic.for_project(project_id)
        count = 0
        for topic in topics:
            try:
                if await self.subscribe(client_id, topic):
                    count += 1
            except (SubscriptionError, InvalidMessageError):
                break
        return count

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_subscribers(self, topic: str) -> set[str]:
        """Get all client IDs subscribed to a topic.

        Args:
            topic: The topic to look up

        Returns:
            Set of client IDs (empty if none)
        """
        return self._topic_clients.get(topic, set()).copy()

    def get_client_topics(self, client_id: str) -> set[str]:
        """Get all topics a client is subscribed to.

        Args:
            client_id: The client to look up

        Returns:
            Set of topic strings (empty if none)
        """
        return self._client_topics.get(client_id, set()).copy()

    def has_subscriber(self, topic: str) -> bool:
        """Check if a topic has any subscribers.

        Args:
            topic: The topic to check

        Returns:
            True if at least one subscriber
        """
        return topic in self._topic_clients and bool(self._topic_clients[topic])

    def is_subscribed(self, client_id: str, topic: str) -> bool:
        """Check if a client is subscribed to a specific topic.

        Args:
            client_id: Client to check
            topic: Topic to check

        Returns:
            True if subscribed
        """
        return (
            client_id in self._client_topics
            and topic in self._client_topics[client_id]
        )

    def get_subscriber_count(self, topic: str) -> int:
        """Get the number of subscribers for a topic.

        Args:
            topic: The topic to check

        Returns:
            Subscriber count
        """
        return len(self._topic_clients.get(topic, set()))

    def get_all_topic_subscribers(self) -> dict[str, int]:
        """Get a summary of all topics with subscriber counts.

        Returns:
            Dict mapping topic → subscriber count
        """
        return {
            topic: len(clients)
            for topic, clients in self._topic_clients.items()
        }

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    async def remove_client(self, client_id: str) -> None:
        """Remove all subscriptions for a disconnected client.

        Args:
            client_id: Client that disconnected
        """
        await self.unsubscribe_all(client_id)

    async def clear(self) -> None:
        """Clear all subscriptions (for testing or reset)."""
        async with self._lock:
            self._client_topics.clear()
            self._topic_clients.clear()
