"""Tests for CronScheduler cleanup and completion behaviour."""

import asyncio

import pytest

from soulbot.scheduler.cron import CronScheduler
from soulbot.scheduler.triggers import IntervalTrigger, OnceTrigger


class TestCleanup:
    async def test_once_trigger_marks_completed(self):
        scheduler = CronScheduler()
        scheduler.add_job("j1", lambda: None, OnceTrigger(delay=0))

        await scheduler.start()
        await asyncio.sleep(1.5)
        await scheduler.stop()

        job = scheduler.get_job("j1")
        assert job.status == "completed"

    async def test_completed_job_not_re_executed(self):
        count = 0

        def inc():
            nonlocal count
            count += 1

        scheduler = CronScheduler()
        scheduler.add_job("j1", inc, OnceTrigger(delay=0))

        await scheduler.start()
        await asyncio.sleep(2.5)
        await scheduler.stop()

        assert count == 1

    async def test_interval_keeps_running(self):
        count = 0

        def inc():
            nonlocal count
            count += 1

        scheduler = CronScheduler()
        scheduler.add_job("j1", inc, IntervalTrigger(seconds=1))

        await scheduler.start()
        await asyncio.sleep(2.5)
        await scheduler.stop()

        assert count >= 2

    async def test_paused_job_not_executed(self):
        count = 0

        def inc():
            nonlocal count
            count += 1

        scheduler = CronScheduler()
        scheduler.add_job("j1", inc, IntervalTrigger(seconds=1))
        scheduler.pause_job("j1")

        await scheduler.start()
        await asyncio.sleep(2.0)
        await scheduler.stop()

        assert count == 0

    async def test_stats_after_execution(self):
        scheduler = CronScheduler()
        scheduler.add_job("j1", lambda: None, OnceTrigger(delay=0))

        await scheduler.start()
        await asyncio.sleep(1.5)
        await scheduler.stop()

        stats = scheduler.get_stats()
        assert stats["total_runs"] >= 1
        assert stats["completed"] >= 1
