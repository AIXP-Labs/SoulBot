"""Tests for CronScheduler EventBus integration."""

import asyncio

import pytest

from soulbot.bus.event_bus import EventBus
from soulbot.bus.events import BusEvent
from soulbot.scheduler.cron import CronScheduler
from soulbot.scheduler.triggers import IntervalTrigger, OnceTrigger


def _collector(target: list[BusEvent]):
    """Return an async handler that appends events to *target*."""
    async def _handler(event: BusEvent) -> None:
        target.append(event)
    return _handler


class TestCronEvents:
    async def test_registered_event(self):
        events: list[BusEvent] = []
        bus = EventBus()
        bus.subscribe("cron.job.registered", _collector(events))

        scheduler = CronScheduler(bus=bus)
        scheduler.add_job("j1", lambda: None, IntervalTrigger(seconds=10))

        await asyncio.sleep(0.1)
        assert any(e.data["job_id"] == "j1" for e in events)

    async def test_removed_event(self):
        events: list[BusEvent] = []
        bus = EventBus()
        bus.subscribe("cron.job.removed", _collector(events))

        scheduler = CronScheduler(bus=bus)
        scheduler.add_job("j1", lambda: None, IntervalTrigger(seconds=10))
        scheduler.remove_job("j1")

        await asyncio.sleep(0.1)
        assert any(e.data["job_id"] == "j1" for e in events)

    async def test_paused_resumed_events(self):
        events: list[BusEvent] = []
        bus = EventBus()
        bus.subscribe("cron.job.*", _collector(events))

        scheduler = CronScheduler(bus=bus)
        scheduler.add_job("j1", lambda: None, IntervalTrigger(seconds=10))
        scheduler.pause_job("j1")
        scheduler.resume_job("j1")

        await asyncio.sleep(0.1)
        types = [e.type for e in events]
        assert "cron.job.paused" in types
        assert "cron.job.resumed" in types

    async def test_fired_and_completed_events(self):
        events: list[BusEvent] = []
        bus = EventBus()
        bus.subscribe("cron.job.*", _collector(events))

        scheduler = CronScheduler(bus=bus)
        scheduler.add_job("j1", lambda: None, OnceTrigger(delay=0))

        await scheduler.start()
        await asyncio.sleep(1.5)
        await scheduler.stop()

        await asyncio.sleep(0.1)
        types = [e.type for e in events]
        assert "cron.job.fired" in types
        assert "cron.job.completed" in types

    async def test_failed_event(self):
        events: list[BusEvent] = []
        bus = EventBus()
        bus.subscribe("cron.job.failed", _collector(events))

        def bad():
            raise ValueError("fail")

        scheduler = CronScheduler(bus=bus)
        scheduler.add_job("j1", bad, OnceTrigger(delay=0))

        await scheduler.start()
        await asyncio.sleep(1.5)
        await scheduler.stop()

        await asyncio.sleep(0.1)
        assert any(e.data.get("error") == "fail" for e in events)

    async def test_no_bus_no_error(self):
        """Scheduler works fine without EventBus."""
        results = []
        scheduler = CronScheduler(bus=None)
        scheduler.add_job("j1", lambda: results.append(1), OnceTrigger(delay=0))

        await scheduler.start()
        await asyncio.sleep(1.5)
        await scheduler.stop()

        assert 1 in results
