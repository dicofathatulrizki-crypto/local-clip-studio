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

    def test_subscribe(self, mgr: SubscriptionManager) -> None:
        """Subscribe adds a client to a topic."""
        mgr.subscribe("c1", "project.abc").result()
        assert mgr.is_subscribed("c1", "project.abc") is True

    def test_subscribe_duplicate(self, mgr: SubscriptionManager) -> None:
        """Subscribing to the same topic twice returns False."""
        assert mgr.subscribe("c1", "topic").result() is True
        assert mgr.subscribe("c1", "topic").result() is False

    def test_unsubscribe(self, mgr: SubscriptionManager) -> None:
        """Unsubscribe removes a client from a topic."""
        mgr.subscribe("c1", "topic").result()
        assert mgr.unsubscribe("c1", "topic").result() is True
        assert mgr.is_subscribed("c1", "topic") is False

    def test_unsubscribe_not_subscribed(self, mgr: SubscriptionManager) -> None:
        """Unsubscribing from a not-subscribed topic returns False."""
        assert mgr.unsubscribe("c1", "nonexistent").result() is False

    def test_unsubscribe_unknown_client(self, mgr: SubscriptionManager) -> None:
        """Unsubscribing an unknown client returns False."""
        assert mgr.unsubscribe("unknown", "topic").result() is False

    def test_get_subscribers(self, mgr: SubscriptionManager) -> None:
        """get_subscribers returns all clients for a topic."""
        mgr.subscribe("c1", "topic").result()
        mgr.subscribe("c2", "topic").result()
        subscribers = mgr.get_subscribers("topic")
        assert subscribers == {"c1", "c2"}

    def test_get_subscribers_empty(self, mgr: SubscriptionManager) -> None:
        """get_subscribers for a topic with no subscribers returns empty set."""
        assert mgr.get_subscribers("nonexistent") == set()

    def test_get_client_topics(self, mgr: SubscriptionManager) -> None:
        """get_client_topics returns all topics for a client."""
        mgr.subscribe("c1", "t1").result()
        mgr.subscribe("c1", "t2").result()
        topics = mgr.get_client_topics("c1")
        assert topics == {"t1", "t2"}

    def test_get_client_topics_unknown(self, mgr: SubscriptionManager) -> None:
        """get_client_topics for unknown client returns empty set."""
        assert mgr.get_client_topics("unknown") == set()

    def test_has_subscriber(self, mgr: SubscriptionManager) -> None:
        """has_subscriber returns True if topic has subscribers."""
        mgr.subscribe("c1", "topic").result()
        assert mgr.has_subscriber("topic") is True
        assert mgr.has_subscriber("empty") is False

    def test_unsubscribe_all(self, mgr: SubscriptionManager) -> None:
        """unsubscribe_all removes all subscriptions for a client."""
        mgr.subscribe("c1", "t1").result()
        mgr.subscribe("c1", "t2").result()
        mgr.subscribe("c1", "t3").result()
        count = mgr.unsubscribe_all("c1").result()
        assert count == 3
        assert mgr.get_client_topics("c1") == set()
        assert mgr.has_subscriber("t1") is False

    def test_max_subscriptions(self, mgr: SubscriptionManager) -> None:
        """Exceeding max subscriptions raises SubscriptionError."""
        for i in range(5):
            mgr.subscribe("c1", f"topic-{i}").result()
        with pytest.raises(SubscriptionError):
            mgr.subscribe("c1", "too-many").result()

    def test_empty_topic(self, mgr: SubscriptionManager) -> None:
        """Subscribing to an empty topic raises InvalidMessageError."""
        with pytest.raises(InvalidMessageError):
            mgr.subscribe("c1", "").result()

    def test_subscribe_to_project(self, mgr: SubscriptionManager) -> None:
        """subscribe_to_project subscribes to all project topics."""
        from backend.infrastructure.websocket.models import SubscriptionTopic

        topics = SubscriptionTopic.for_project("proj-1")
        count = mgr.subscribe_to_project("c1", "proj-1").result()
        assert count == len(topics)
        for topic in topics:
            assert mgr.is_subscribed("c1", topic) is True

    def test_get_subscriber_count(self, mgr: SubscriptionManager) -> None:
        """get_subscriber_count returns correct count."""
        mgr.subscribe("c1", "topic").result()
        mgr.subscribe("c2", "topic").result()
        assert mgr.get_subscriber_count("topic") == 2

    def test_get_all_topic_subscribers(self, mgr: SubscriptionManager) -> None:
        """get_all_topic_subscribers returns summary."""
        mgr.subscribe("c1", "t1").result()
        mgr.subscribe("c2", "t1").result()
        mgr.subscribe("c1", "t2").result()
        summary = mgr.get_all_topic_subscribers()
        assert summary["t1"] == 2
        assert summary["t2"] == 1

    def test_clear(self, mgr: SubscriptionManager) -> None:
        """Clear removes all subscriptions."""
        mgr.subscribe("c1", "t1").result()
        mgr.subscribe("c2", "t2").result()
        mgr.clear().result()
        assert mgr.total_subscriptions == 0
        assert mgr.unique_topics == []

    def test_remove_client(self, mgr: SubscriptionManager) -> None:
        """remove_client cleans up after disconnect."""
        mgr.subscribe("c1", "t1").result()
        mgr.remove_client("c1").result()
        assert mgr.get_client_topics("c1") == set()
        assert mgr.has_subscriber("t1") is False

    def test_total_subscriptions(self, mgr: SubscriptionManager) -> None:
        """total_subscriptions returns correct count."""
        mgr.subscribe("c1", "t1").result()
        mgr.subscribe("c1", "t2").result()
        mgr.subscribe("c2", "t1").result()
        assert mgr.total_subscriptions == 3
