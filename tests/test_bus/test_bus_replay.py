"""Tests for EventBus history replay."""

import pytest

from soulbot.bus.events import BusEvent
from soulbot.bus.event_bus import EventBus


class TestReplay:
    async def test_replay_all(self):
        bus = EventBus()

        async def noop(event: BusEvent):
            pass

        bus.subscribe("*", noop)

        await bus.publish(BusEvent(type="a", data={"i": 1}))
        await bus.publish(BusEvent(type="b", data={"i": 2}))
        await bus.publish(BusEvent(type="c", data={"i": 3}))

        replayed = []

        async def collector(event: BusEvent):
            replayed.append(event.type)

        count = await bus.replay(collector)
        assert count == 3
        assert replayed == ["a", "b", "c"]

    async def test_replay_by_type(self):
        bus = EventBus()

        async def noop(event: BusEvent):
            pass

        bus.subscribe("*", noop)

        await bus.publish(BusEvent(type="agent.start"))
        await bus.publish(BusEvent(type="llm.request"))
        await bus.publish(BusEvent(type="agent.start"))

        replayed = []

        async def collector(event: BusEvent):
            replayed.append(event.type)

        count = await bus.replay(collector, event_type="agent.start")
        assert count == 2

    async def test_replay_last_n(self):
        bus = EventBus()

        async def noop(event: BusEvent):
            pass

        bus.subscribe("*", noop)

        for i in range(10):
            await bus.publish(BusEvent(type="test", data={"i": i}))

        replayed = []

        async def collector(event: BusEvent):
            replayed.append(event.data["i"])

        count = await bus.replay(collector, last_n=3)
        assert count == 3
        assert replayed == [7, 8, 9]

    async def test_replay_type_and_last_n(self):
        bus = EventBus()

        async def noop(event: BusEvent):
            pass

        bus.subscribe("*", noop)

        await bus.publish(BusEvent(type="a"))
        await bus.publish(BusEvent(type="b"))
        await bus.publish(BusEvent(type="a"))
        await bus.publish(BusEvent(type="a"))
        await bus.publish(BusEvent(type="b"))

        replayed = []

        async def collector(event: BusEvent):
            replayed.append(event.type)

        count = await bus.replay(collector, event_type="a", last_n=2)
        assert count == 2

    async def test_replay_empty_history(self):
        bus = EventBus()
        received = []

        async def handler(event: BusEvent):
            received.append(event)

        count = await bus.replay(handler)
        assert count == 0
        assert len(received) == 0

    async def test_history_size_limit(self):
        bus = EventBus(history_size=5)

        async def noop(event: BusEvent):
            pass

        bus.subscribe("*", noop)

        for i in range(10):
            await bus.publish(BusEvent(type="test", data={"i": i}))

        replayed = []

        async def collector(event: BusEvent):
            replayed.append(event.data["i"])

        count = await bus.replay(collector)
        assert count == 5
        assert replayed == [5, 6, 7, 8, 9]  # oldest 5 evicted

    async def test_replay_handler_exception_skipped(self):
        bus = EventBus()

        async def noop(event: BusEvent):
            pass

        bus.subscribe("*", noop)

        await bus.publish(BusEvent(type="ok", data={"i": 1}))
        await bus.publish(BusEvent(type="bad", data={"i": 2}))
        await bus.publish(BusEvent(type="ok", data={"i": 3}))

        replayed = []

        async def fragile(event: BusEvent):
            if event.type == "bad":
                raise ValueError("skip")
            replayed.append(event.data["i"])

        count = await bus.replay(fragile)
        assert count == 2
        assert replayed == [1, 3]
