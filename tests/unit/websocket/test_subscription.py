"""Tests for WebSocket subscription manager.

Covers:
- Subscribe/unsubscribe
- Max subscriptions per client
- Duplicate subscription
- Project-level subscriptions
- Topic→client lookup
- Unsubscribe all
- Clear
"""

from __future__ import annotations

import pytest

from backend.infrastructure.websocket.exceptions import (
    InvalidMessageError,
    SubscriptionError,
)
from backend.infrastructure.websocket.subscription import SubscriptionManager


class TestSubscriptionManager:
    """Tests for SubscriptionManager."""

    @pytest.fixture
    def mgr(self) -> SubscriptionManager:
        return SubscriptionManager(max_subscriptions_per_client=5)

    @pytest.mark.asyncio
    async def test_subscribe(self, mgr: SubscriptionManager) -> None:
        """Subscribe adds a client to a topic."""
        await mgr.subscribe("c1", "project.abc")
        assert mgr.is_subscribed("c1", "project.abc") is True

    @pytest.mark.asyncio
    async def test_subscribe_duplicate(self, mgr: SubscriptionManager) -> None:
        """Subscribing to the same topic twice returns False."""
        assert await mgr.subscribe("c1", "topic") is True
        assert await mgr.subscribe("c1", "topic") is False

    @pytest.mark.asyncio
    async def test_unsubscribe(self, mgr: SubscriptionManager) -> None:
        """Unsubscribe removes a client from a topic."""
        await mgr.subscribe("c1", "topic")
        assert await mgr.unsubscribe("c1", "topic") is True
        assert mgr.is_subscribed("c1", "topic") is False

    @pytest.mark.asyncio
    async def test_unsubscribe_not_subscribed(self, mgr: SubscriptionManager) -> None:
        """Unsubscribing from a not-subscribed topic returns False."""
        assert await mgr.unsubscribe("c1", "nonexistent") is False

    @pytest.mark.asyncio
    async def test_unsubscribe_unknown_client(self, mgr: SubscriptionManager) -> None:
        """Unsubscribing an unknown client returns False."""
        assert await mgr.unsubscribe("unknown", "topic") is False

    @pytest.mark.asyncio
    async def test_get_subscribers(self, mgr: SubscriptionManager) -> None:
        """get_subscribers returns all clients for a topic."""
        await mgr.subscribe("c1", "topic")
        await mgr.subscribe("c2", "topic")
        subscribers = mgr.get_subscribers("topic")
        assert subscribers == {"c1", "c2"}

    def test_get_subscribers_empty(self, mgr: SubscriptionManager) -> None:
        """get_subscribers for a topic with no subscribers returns empty set."""
        assert mgr.get_subscribers("nonexistent") == set()

    @pytest.mark.asyncio
    async def test_get_client_topics(self, mgr: SubscriptionManager) -> None:
        """get_client_topics returns all topics for a client."""
        await mgr.subscribe("c1", "t1")
        await mgr.subscribe("c1", "t2")
        topics = mgr.get_client_topics("c1")
        assert topics == {"t1", "t2"}

    def test_get_client_topics_unknown(self, mgr: SubscriptionManager) -> None:
        """get_client_topics for unknown client returns empty set."""
        assert mgr.get_client_topics("unknown") == set()

    @pytest.mark.asyncio
    async def test_has_subscriber(self, mgr: SubscriptionManager) -> None:
        """has_subscriber returns True if topic has subscribers."""
        await mgr.subscribe("c1", "topic")
        assert mgr.has_subscriber("topic") is True
        assert mgr.has_subscriber("empty") is False

    @pytest.mark.asyncio
    async def test_unsubscribe_all(self, mgr: SubscriptionManager) -> None:
        """unsubscribe_all removes all subscriptions for a client."""
        await mgr.subscribe("c1", "t1")
        await mgr.subscribe("c1", "t2")
        await mgr.subscribe("c1", "t3")
        count = await mgr.unsubscribe_all("c1")
        assert count == 3
        assert mgr.get_client_topics("c1") == set()
        assert mgr.has_subscriber("t1") is False

    @pytest.mark.asyncio
    async def test_max_subscriptions(self, mgr: SubscriptionManager) -> None:
        """Exceeding max subscriptions raises SubscriptionError."""
        for i in range(5):
            await mgr.subscribe("c1", f"topic-{i}")
        with pytest.raises(SubscriptionError):
            await mgr.subscribe("c1", "too-many")

    @pytest.mark.asyncio
    async def test_empty_topic(self, mgr: SubscriptionManager) -> None:
        """Subscribing to an empty topic raises InvalidMessageError."""
        with pytest.raises(InvalidMessageError):
            await mgr.subscribe("c1", "")

    @pytest.mark.asyncio
    async def test_subscribe_to_project(self, mgr: SubscriptionManager) -> None:
        """subscribe_to_project subscribes to all project topics."""
        from backend.infrastructure.websocket.models import SubscriptionTopic

        topics = SubscriptionTopic.for_project("proj-1")
        count = await mgr.subscribe_to_project("c1", "proj-1")
        assert count >= 5  # At least 5 of 6 should succeed (max is 5 per client)
        # At minimum the main project topic is subscribed
        assert mgr.is_subscribed("c1", "project.proj-1") is True

    @pytest.mark.asyncio
    async def test_get_subscriber_count(self, mgr: SubscriptionManager) -> None:
        """get_subscriber_count returns correct count."""
        await mgr.subscribe("c1", "topic")
        await mgr.subscribe("c2", "topic")
        assert mgr.get_subscriber_count("topic") == 2

    @pytest.mark.asyncio
    async def test_get_all_topic_subscribers(self, mgr: SubscriptionManager) -> None:
        """get_all_topic_subscribers returns summary."""
        await mgr.subscribe("c1", "t1")
        await mgr.subscribe("c2", "t1")
        await mgr.subscribe("c1", "t2")
        summary = mgr.get_all_topic_subscribers()
        assert summary["t1"] == 2
        assert summary["t2"] == 1

    @pytest.mark.asyncio
    async def test_clear(self, mgr: SubscriptionManager) -> None:
        """Clear removes all subscriptions."""
        await mgr.subscribe("c1", "t1")
        await mgr.subscribe("c2", "t2")
        await mgr.clear()
        assert mgr.total_subscriptions == 0
        assert mgr.unique_topics == []

    @pytest.mark.asyncio
    async def test_remove_client(self, mgr: SubscriptionManager) -> None:
        """remove_client cleans up after disconnect."""
        await mgr.subscribe("c1", "t1")
        await mgr.remove_client("c1")
        assert mgr.get_client_topics("c1") == set()
        assert mgr.has_subscriber("t1") is False

    @pytest.mark.asyncio
    async def test_total_subscriptions(self, mgr: SubscriptionManager) -> None:
        """total_subscriptions returns correct count."""
        await mgr.subscribe("c1", "t1")
        await mgr.subscribe("c1", "t2")
        await mgr.subscribe("c2", "t1")
        assert mgr.total_subscriptions == 3
