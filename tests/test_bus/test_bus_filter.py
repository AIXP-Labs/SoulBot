"""Tests for EventBus filter_func and unsubscribe."""

import pytest

from soulbot.bus.events import BusEvent
from soulbot.bus.event_bus import EventBus


class TestFilterFunc:
    async def test_filter_allows_matching(self):
        bus = EventBus()
        received = []

        async def handler(event: BusEvent):
            received.append(event.data)

        bus.subscribe(
            "test",
            handler,
            filter_func=lambda e: e.data.get("important") is True,
        )

        await bus.publish(BusEvent(type="test", data={"important": True, "msg": "yes"}))
        await bus.publish(BusEvent(type="test", data={"important": False, "msg": "no"}))
        await bus.publish(BusEvent(type="test", data={"msg": "missing"}))

        assert len(received) == 1
        assert received[0]["msg"] == "yes"

    async def test_filter_blocks_all(self):
        bus = EventBus()
        received = []

        async def handler(event: BusEvent):
            received.append(event)

        bus.subscribe("test", handler, filter_func=lambda e: False)

        count = await bus.publish(BusEvent(type="test"))
        assert count == 0
        assert len(received) == 0

    async def test_filter_on_prefix_subscription(self):
        bus = EventBus()
        received = []

        async def handler(event: BusEvent):
            received.append(event.type)

        bus.subscribe(
            "agent.*",
            handler,
            filter_func=lambda e: "error" not in e.type,
        )

        await bus.publish(BusEvent(type="agent.start"))
        await bus.publish(BusEvent(type="agent.error"))
        await bus.publish(BusEvent(type="agent.response"))

        assert received == ["agent.start", "agent.response"]

    async def test_filter_on_wildcard(self):
        bus = EventBus()
        received = []

        async def handler(event: BusEvent):
            received.append(event.type)

        bus.subscribe(
            "*",
            handler,
            filter_func=lambda e: e.source == "runner",
        )

        await bus.publish(BusEvent(type="a", source="runner"))
        await bus.publish(BusEvent(type="b", source="agent"))
        await bus.publish(BusEvent(type="c", source="runner"))

        assert received == ["a", "c"]

    async def test_filter_with_priority(self):
        bus = EventBus()
        received = []

        async def high_handler(event: BusEvent):
            received.append("high")

        async def low_handler(event: BusEvent):
            received.append("low")

        bus.subscribe(
            "test",
            high_handler,
            priority=10,
            filter_func=lambda e: e.data.get("level") == "high",
        )
        bus.subscribe("test", low_handler, priority=1)

        # Only low should fire (filter blocks high)
        count = await bus.publish(BusEvent(type="test", data={"level": "low"}))
        assert count == 1
        assert received == ["low"]


class TestUnsubscribeWithFilter:
    async def test_unsubscribe_filtered_handler(self):
        bus = EventBus()
        received = []

        async def handler(event: BusEvent):
            received.append(event)

        bus.subscribe("test", handler, filter_func=lambda e: True)
        bus.unsubscribe("test", handler)

        await bus.publish(BusEvent(type="test"))
        assert len(received) == 0
