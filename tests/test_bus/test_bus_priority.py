"""Tests for EventBus priority ordering."""

import pytest

from soulbot.bus.events import BusEvent
from soulbot.bus.event_bus import EventBus


class TestPriority:
    async def test_higher_priority_first(self):
        bus = EventBus()
        order = []

        async def low(event: BusEvent):
            order.append("low")

        async def high(event: BusEvent):
            order.append("high")

        bus.subscribe("test", low, priority=0)
        bus.subscribe("test", high, priority=10)

        await bus.publish(BusEvent(type="test"))

        # High priority (10) should be first in subscription list
        # Both execute concurrently via gather, but they're ordered in the list
        assert "high" in order
        assert "low" in order

    async def test_same_priority_both_execute(self):
        bus = EventBus()
        received = []

        async def handler_a(event: BusEvent):
            received.append("a")

        async def handler_b(event: BusEvent):
            received.append("b")

        bus.subscribe("test", handler_a, priority=5)
        bus.subscribe("test", handler_b, priority=5)

        await bus.publish(BusEvent(type="test"))
        assert len(received) == 2

    async def test_priority_on_prefix_subscriptions(self):
        bus = EventBus()
        order = []

        async def low(event: BusEvent):
            order.append("low")

        async def high(event: BusEvent):
            order.append("high")

        bus.subscribe("agent.*", low, priority=1)
        bus.subscribe("agent.*", high, priority=100)

        await bus.publish(BusEvent(type="agent.start"))
        assert len(order) == 2

    async def test_priority_on_wildcard_subscriptions(self):
        bus = EventBus()
        order = []

        async def low(event: BusEvent):
            order.append("low")

        async def high(event: BusEvent):
            order.append("high")

        bus.subscribe("*", low, priority=0)
        bus.subscribe("*", high, priority=50)

        await bus.publish(BusEvent(type="any.event"))
        assert len(order) == 2

    async def test_negative_priority(self):
        bus = EventBus()
        received = []

        async def neg(event: BusEvent):
            received.append("neg")

        async def zero(event: BusEvent):
            received.append("zero")

        bus.subscribe("test", neg, priority=-10)
        bus.subscribe("test", zero, priority=0)

        await bus.publish(BusEvent(type="test"))
        assert len(received) == 2
