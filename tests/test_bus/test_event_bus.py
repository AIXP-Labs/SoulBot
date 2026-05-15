"""Tests for EventBus exact, prefix, and wildcard subscriptions."""

import pytest

from soulbot.bus.events import BusEvent
from soulbot.bus.event_bus import EventBus


class TestExactSubscription:
    async def test_exact_match(self):
        bus = EventBus()
        received = []

        async def handler(event: BusEvent):
            received.append(event)

        bus.subscribe("agent.response", handler)
        await bus.publish(BusEvent(type="agent.response", data={"text": "hi"}))

        assert len(received) == 1
        assert received[0].data["text"] == "hi"

    async def test_no_match(self):
        bus = EventBus()
        received = []

        async def handler(event: BusEvent):
            received.append(event)

        bus.subscribe("agent.response", handler)
        await bus.publish(BusEvent(type="llm.request"))

        assert len(received) == 0

    async def test_multiple_handlers(self):
        bus = EventBus()
        results = []

        async def handler_a(event: BusEvent):
            results.append("a")

        async def handler_b(event: BusEvent):
            results.append("b")

        bus.subscribe("test.event", handler_a)
        bus.subscribe("test.event", handler_b)
        count = await bus.publish(BusEvent(type="test.event"))

        assert count == 2
        assert set(results) == {"a", "b"}

    async def test_returns_delivery_count(self):
        bus = EventBus()

        async def handler(event: BusEvent):
            pass

        bus.subscribe("x", handler)
        count = await bus.publish(BusEvent(type="x"))
        assert count == 1

    async def test_no_subscribers_returns_zero(self):
        bus = EventBus()
        count = await bus.publish(BusEvent(type="orphan.event"))
        assert count == 0


class TestPrefixSubscription:
    async def test_prefix_match(self):
        bus = EventBus()
        received = []

        async def handler(event: BusEvent):
            received.append(event.type)

        bus.subscribe("agent.*", handler)
        await bus.publish(BusEvent(type="agent.start"))
        await bus.publish(BusEvent(type="agent.response"))
        await bus.publish(BusEvent(type="llm.request"))

        assert received == ["agent.start", "agent.response"]

    async def test_deep_prefix_match(self):
        bus = EventBus()
        received = []

        async def handler(event: BusEvent):
            received.append(event.type)

        bus.subscribe("cron.*", handler)
        await bus.publish(BusEvent(type="cron.job.fired"))
        await bus.publish(BusEvent(type="cron.job.completed"))

        assert len(received) == 2

    async def test_prefix_no_partial_match(self):
        """'agent' prefix should not match 'agent_extra.something'."""
        bus = EventBus()
        received = []

        async def handler(event: BusEvent):
            received.append(event.type)

        bus.subscribe("agent.*", handler)
        # "agent" prefix only matches events starting with "agent."
        await bus.publish(BusEvent(type="agent_extra.event"))

        assert len(received) == 0


class TestWildcardSubscription:
    async def test_wildcard_receives_all(self):
        bus = EventBus()
        received = []

        async def handler(event: BusEvent):
            received.append(event.type)

        bus.subscribe("*", handler)
        await bus.publish(BusEvent(type="agent.start"))
        await bus.publish(BusEvent(type="llm.request"))
        await bus.publish(BusEvent(type="tool.call"))

        assert len(received) == 3

    async def test_mixed_subscriptions(self):
        """Exact + prefix + wildcard all receive the same event."""
        bus = EventBus()
        received = []

        async def exact(event: BusEvent):
            received.append("exact")

        async def prefix(event: BusEvent):
            received.append("prefix")

        async def wildcard(event: BusEvent):
            received.append("wildcard")

        bus.subscribe("agent.response", exact)
        bus.subscribe("agent.*", prefix)
        bus.subscribe("*", wildcard)

        count = await bus.publish(BusEvent(type="agent.response"))

        assert count == 3
        assert set(received) == {"exact", "prefix", "wildcard"}


class TestUnsubscribe:
    async def test_unsubscribe_exact(self):
        bus = EventBus()
        received = []

        async def handler(event: BusEvent):
            received.append(event)

        bus.subscribe("test", handler)
        assert bus.unsubscribe("test", handler) is True

        await bus.publish(BusEvent(type="test"))
        assert len(received) == 0

    async def test_unsubscribe_prefix(self):
        bus = EventBus()
        received = []

        async def handler(event: BusEvent):
            received.append(event)

        bus.subscribe("agent.*", handler)
        assert bus.unsubscribe("agent.*", handler) is True

        await bus.publish(BusEvent(type="agent.start"))
        assert len(received) == 0

    async def test_unsubscribe_wildcard(self):
        bus = EventBus()
        received = []

        async def handler(event: BusEvent):
            received.append(event)

        bus.subscribe("*", handler)
        assert bus.unsubscribe("*", handler) is True

        await bus.publish(BusEvent(type="anything"))
        assert len(received) == 0

    async def test_unsubscribe_not_found(self):
        bus = EventBus()

        async def handler(event: BusEvent):
            pass

        assert bus.unsubscribe("nonexistent", handler) is False
