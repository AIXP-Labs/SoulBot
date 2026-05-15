"""Tests for CronScheduler — add/remove/pause/resume, tick, concurrency."""

import asyncio

import pytest

from soulbot.scheduler.cron import CronJob, CronScheduler
from soulbot.scheduler.triggers import IntervalTrigger, OnceTrigger


class TestJobManagement:
    def test_add_job(self):
        scheduler = CronScheduler()
        job_id = scheduler.add_job("j1", lambda: None, IntervalTrigger(seconds=10))
        assert job_id == "j1"
        assert scheduler.get_job("j1") is not None

    def test_add_duplicate_raises(self):
        scheduler = CronScheduler()
        scheduler.add_job("j1", lambda: None, IntervalTrigger(seconds=10))
        with pytest.raises(ValueError, match="already exists"):
            scheduler.add_job("j1", lambda: None, IntervalTrigger(seconds=10))

    def test_add_duplicate_replace(self):
        scheduler = CronScheduler()
        scheduler.add_job("j1", lambda: None, IntervalTrigger(seconds=10))
        scheduler.add_job("j1", lambda: None, IntervalTrigger(seconds=20), replace_existing=True)
        assert scheduler.get_job("j1").trigger.interval == 20

    def test_remove_job(self):
        scheduler = CronScheduler()
        scheduler.add_job("j1", lambda: None, IntervalTrigger(seconds=10))
        assert scheduler.remove_job("j1") is True
        assert scheduler.get_job("j1") is None

    def test_remove_nonexistent(self):
        scheduler = CronScheduler()
        assert scheduler.remove_job("nope") is False

    def test_pause_job(self):
        scheduler = CronScheduler()
        scheduler.add_job("j1", lambda: None, IntervalTrigger(seconds=10))
        assert scheduler.pause_job("j1") is True
        assert scheduler.get_job("j1").status == "paused"

    def test_pause_already_paused(self):
        scheduler = CronScheduler()
        scheduler.add_job("j1", lambda: None, IntervalTrigger(seconds=10))
        scheduler.pause_job("j1")
        assert scheduler.pause_job("j1") is False

    def test_resume_job(self):
        scheduler = CronScheduler()
        scheduler.add_job("j1", lambda: None, IntervalTrigger(seconds=10))
        scheduler.pause_job("j1")
        assert scheduler.resume_job("j1") is True
        job = scheduler.get_job("j1")
        assert job.status == "active"
        assert job.next_run is None  # recalculate

    def test_resume_active_noop(self):
        scheduler = CronScheduler()
        scheduler.add_job("j1", lambda: None, IntervalTrigger(seconds=10))
        assert scheduler.resume_job("j1") is False

    def test_get_jobs(self):
        scheduler = CronScheduler()
        scheduler.add_job("a", lambda: None, IntervalTrigger(seconds=5))
        scheduler.add_job("b", lambda: None, IntervalTrigger(seconds=10))
        assert len(scheduler.get_jobs()) == 2

    def test_get_stats(self):
        scheduler = CronScheduler()
        scheduler.add_job("a", lambda: None, IntervalTrigger(seconds=5))
        scheduler.add_job("b", lambda: None, IntervalTrigger(seconds=10))
        scheduler.pause_job("b")
        stats = scheduler.get_stats()
        assert stats["total_jobs"] == 2
        assert stats["active"] == 1
        assert stats["paused"] == 1


class TestSchedulerExecution:
    async def test_sync_job_execution(self):
        results = []
        scheduler = CronScheduler()
        scheduler.add_job("j1", lambda: results.append("done"), OnceTrigger(delay=0))

        await scheduler.start()
        await asyncio.sleep(1.5)
        await scheduler.stop()

        assert "done" in results

    async def test_async_job_execution(self):
        results = []

        async def async_task():
            results.append("async_done")

        scheduler = CronScheduler()
        scheduler.add_job("j1", async_task, OnceTrigger(delay=0))

        await scheduler.start()
        await asyncio.sleep(1.5)
        await scheduler.stop()

        assert "async_done" in results

    async def test_job_with_args(self):
        results = []

        def adder(a, b):
            results.append(a + b)

        scheduler = CronScheduler()
        scheduler.add_job(
            "j1", adder, OnceTrigger(delay=0),
            args=(3, 4),
        )

        await scheduler.start()
        await asyncio.sleep(1.5)
        await scheduler.stop()

        assert 7 in results

    async def test_job_error_increments_count(self):
        def bad():
            raise RuntimeError("boom")

        scheduler = CronScheduler()
        scheduler.add_job("j1", bad, OnceTrigger(delay=0))

        await scheduler.start()
        await asyncio.sleep(1.5)
        await scheduler.stop()

        job = scheduler.get_job("j1")
        assert job.error_count >= 1
        assert job.last_error == "boom"

    async def test_concurrency_guard(self):
        """A slow job should not be started again while running."""
        call_count = 0

        async def slow_task():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(3)

        scheduler = CronScheduler()
        scheduler.add_job("j1", slow_task, IntervalTrigger(seconds=1))

        await scheduler.start()
        await asyncio.sleep(2.5)
        await scheduler.stop()

        # Should only fire once because is_running blocks re-entry
        assert call_count == 1

    async def test_start_stop(self):
        scheduler = CronScheduler()
        assert scheduler.is_running is False
        await scheduler.start()
        assert scheduler.is_running is True
        await scheduler.stop()
        assert scheduler.is_running is False

    async def test_once_trigger_completes(self):
        scheduler = CronScheduler()
        scheduler.add_job("j1", lambda: None, OnceTrigger(delay=0))

        await scheduler.start()
        await asyncio.sleep(1.5)
        await scheduler.stop()

        job = scheduler.get_job("j1")
        assert job.status == "completed"
