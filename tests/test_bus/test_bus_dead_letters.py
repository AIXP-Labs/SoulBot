"""Tests for EventBus dead letter queue."""

import pytest

from soulbot.bus.events import BusEvent
from soulbot.bus.event_bus import EventBus


class TestDeadLetters:
    async def test_handler_exception_recorded(self):
        bus = EventBus()

        async def bad_handler(event: BusEvent):
            raise ValueError("oops")

        bus.subscribe("test", bad_handler)
        count = await bus.publish(BusEvent(type="test"))

        assert count == 0
        letters = bus.get_dead_letters()
        assert len(letters) == 1
        assert "oops" in letters[0].error
        assert letters[0].event.type == "test"

    async def test_good_handlers_still_work(self):
        bus = EventBus()
        received = []

        async def good(event: BusEvent):
            received.append("ok")

        async def bad(event: BusEvent):
            raise RuntimeError("fail")

        bus.subscribe("test", good)
        bus.subscribe("test", bad)
        count = await bus.publish(BusEvent(type="test"))

        assert count == 1  # only good handler
        assert len(received) == 1
        assert len(bus.get_dead_letters()) == 1

    async def test_dead_letter_limit(self):
        bus = EventBus(dead_letter_size=3)

        async def bad(event: BusEvent):
            raise ValueError("fail")

        bus.subscribe("test", bad)

        for i in range(5):
            await bus.publish(BusEvent(type="test", data={"i": i}))

        letters = bus.get_dead_letters()
        assert len(letters) == 3  # oldest 2 evicted

    async def test_get_dead_letters_last_n(self):
        bus = EventBus()

        async def bad(event: BusEvent):
            raise ValueError("fail")

        bus.subscribe("test", bad)

        for i in range(5):
            await bus.publish(BusEvent(type="test", data={"i": i}))

        last_2 = bus.get_dead_letters(last_n=2)
        assert len(last_2) == 2

    async def test_clear_dead_letters(self):
        bus = EventBus()

        async def bad(event: BusEvent):
            raise ValueError("fail")

        bus.subscribe("test", bad)
        await bus.publish(BusEvent(type="test"))
        assert len(bus.get_dead_letters()) == 1

        cleared = bus.clear_dead_letters()
        assert cleared == 1
        assert len(bus.get_dead_letters()) == 0

    async def test_dead_letter_handler_name(self):
        bus = EventBus()

        async def my_failing_handler(event: BusEvent):
            raise TypeError("type error")

        bus.subscribe("test", my_failing_handler)
        await bus.publish(BusEvent(type="test"))

        letters = bus.get_dead_letters()
        assert letters[0].handler_name == "my_failing_handler"
