"""Tests for EventBus statistics."""

import pytest

from soulbot.bus.events import BusEvent
from soulbot.bus.event_bus import EventBus


class TestStats:
    async def test_initial_stats(self):
        bus = EventBus()
        stats = bus.get_stats()
        assert stats["published"] == 0
        assert stats["delivered"] == 0
        assert stats["failed"] == 0
        assert stats["history_size"] == 0
        assert stats["dead_letter_size"] == 0

    async def test_published_count(self):
        bus = EventBus()
        await bus.publish(BusEvent(type="a"))
        await bus.publish(BusEvent(type="b"))
        await bus.publish(BusEvent(type="c"))

        stats = bus.get_stats()
        assert stats["published"] == 3

    async def test_delivered_count(self):
        bus = EventBus()
        received = []

        async def handler(event: BusEvent):
            received.append(event)

        bus.subscribe("test", handler)
        await bus.publish(BusEvent(type="test"))
        await bus.publish(BusEvent(type="test"))

        stats = bus.get_stats()
        assert stats["delivered"] == 2

    async def test_failed_count(self):
        bus = EventBus()

        async def bad(event: BusEvent):
            raise ValueError("fail")

        bus.subscribe("test", bad)
        await bus.publish(BusEvent(type="test"))
        await bus.publish(BusEvent(type="test"))

        stats = bus.get_stats()
        assert stats["failed"] == 2
        assert stats["delivered"] == 0

    async def test_mixed_success_failure(self):
        bus = EventBus()

        async def good(event: BusEvent):
            pass

        async def bad(event: BusEvent):
            raise ValueError("fail")

        bus.subscribe("test", good)
        bus.subscribe("test", bad)

        await bus.publish(BusEvent(type="test"))

        stats = bus.get_stats()
        assert stats["published"] == 1
        assert stats["delivered"] == 1
        assert stats["failed"] == 1

    async def test_subscription_counts(self):
        bus = EventBus()

        async def h(event: BusEvent):
            pass

        bus.subscribe("exact.event", h)
        bus.subscribe("prefix.*", h)
        bus.subscribe("*", h)

        stats = bus.get_stats()
        assert stats["exact_subscriptions"] == 1
        assert stats["prefix_subscriptions"] == 1
        assert stats["wildcard_subscriptions"] == 1

    async def test_history_size_in_stats(self):
        bus = EventBus(history_size=100)

        async def noop(event: BusEvent):
            pass

        bus.subscribe("*", noop)

        for i in range(5):
            await bus.publish(BusEvent(type="test"))

        stats = bus.get_stats()
        assert stats["history_size"] == 5

    async def test_dead_letter_size_in_stats(self):
        bus = EventBus()

        async def bad(event: BusEvent):
            raise ValueError("fail")

        bus.subscribe("test", bad)

        for i in range(3):
            await bus.publish(BusEvent(type="test"))

        stats = bus.get_stats()
        assert stats["dead_letter_size"] == 3


class TestBusEventModel:
    def test_default_fields(self):
        event = BusEvent(type="test")
        assert event.type == "test"
        assert event.data == {}
        assert event.source == ""
        assert event.timestamp > 0

    def test_custom_fields(self):
        event = BusEvent(
            type="agent.response",
            data={"text": "hello"},
            source="runner",
        )
        assert event.data["text"] == "hello"
        assert event.source == "runner"

    def test_event_type_constants(self):
        from soulbot.bus.events import (
            AGENT_START,
            AGENT_RESPONSE,
            LLM_REQUEST,
            TOOL_CALL,
            SESSION_UPDATED,
        )

        assert AGENT_START == "agent.start"
        assert AGENT_RESPONSE == "agent.response"
        assert LLM_REQUEST == "llm.request"
        assert TOOL_CALL == "tool.call"
        assert SESSION_UPDATED == "session.updated"
