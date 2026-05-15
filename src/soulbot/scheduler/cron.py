"""CronScheduler — AI-driven task scheduler with concurrent protection."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable

from .triggers import BaseTrigger, OnceTrigger

if TYPE_CHECKING:
    from ..bus.event_bus import EventBus

logger = logging.getLogger(__name__)


DEFAULT_JOB_TIMEOUT: float = 300.0  # 5 minutes


@dataclass
class CronJob:
    """A scheduled job."""

    id: str
    func: Callable
    trigger: BaseTrigger
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    timeout: float = DEFAULT_JOB_TIMEOUT
    status: str = "active"  # active / paused / completed
    created_at: float = field(default_factory=time.time)
    last_run: float | None = None
    next_run: datetime | None = None
    run_count: int = 0
    error_count: int = 0
    last_error: str | None = None
    is_running: bool = False  # concurrency guard


class CronScheduler:
    """Async task scheduler with interval, cron, and one-shot triggers.

    Features:
    - Three trigger types (Interval, Cron, Once)
    - Concurrency protection (same job won't run twice)
    - EventBus integration
    - Pause/resume support
    """

    def __init__(self, bus: EventBus | None = None) -> None:
        self._jobs: dict[str, CronJob] = {}
        self._bus = bus
        self._running = False
        self._tick_task: asyncio.Task | None = None

    # ------------------------------------------------------------------
    # Job management
    # ------------------------------------------------------------------

    def add_job(
        self,
        job_id: str,
        func: Callable,
        trigger: BaseTrigger,
        *,
        args: tuple = (),
        kwargs: dict[str, Any] | None = None,
        replace_existing: bool = False,
    ) -> str:
        """Add a job to the scheduler.

        Raises:
            ValueError: Job already exists and *replace_existing* is False.
        """
        if job_id in self._jobs and not replace_existing:
            raise ValueError(f"Job already exists: {job_id}")
        job = CronJob(
            id=job_id,
            func=func,
            trigger=trigger,
            args=args,
            kwargs=kwargs or {},
        )
        self._jobs[job_id] = job
        self._emit("cron.job.registered", {"job_id": job_id})
        return job_id

    def remove_job(self, job_id: str) -> bool:
        """Remove a job. Returns True if found."""
        if job_id in self._jobs:
            del self._jobs[job_id]
            self._emit("cron.job.removed", {"job_id": job_id})
            return True
        return False

    def pause_job(self, job_id: str) -> bool:
        """Pause an active job."""
        job = self._jobs.get(job_id)
        if job and job.status == "active":
            job.status = "paused"
            self._emit("cron.job.paused", {"job_id": job_id})
            return True
        return False

    def resume_job(self, job_id: str) -> bool:
        """Resume a paused job."""
        job = self._jobs.get(job_id)
        if job and job.status == "paused":
            job.status = "active"
            job.next_run = None  # recalculate on next tick
            self._emit("cron.job.resumed", {"job_id": job_id})
            return True
        return False

    def get_jobs(self) -> list[CronJob]:
        """Return all jobs."""
        return list(self._jobs.values())

    def get_job(self, job_id: str) -> CronJob | None:
        """Get a job by ID."""
        return self._jobs.get(job_id)

    def get_stats(self) -> dict[str, Any]:
        """Return scheduler statistics."""
        jobs = list(self._jobs.values())
        return {
            "total_jobs": len(jobs),
            "active": sum(1 for j in jobs if j.status == "active"),
            "paused": sum(1 for j in jobs if j.status == "paused"),
            "completed": sum(1 for j in jobs if j.status == "completed"),
            "total_runs": sum(j.run_count for j in jobs),
            "total_errors": sum(j.error_count for j in jobs),
            "running": self._running,
        }

    # ------------------------------------------------------------------
    # Scheduler loop
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the scheduler tick loop (idempotent)."""
        if self._running:
            return
        self._running = True
        self._tick_task = asyncio.create_task(self._tick_loop())

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        if self._tick_task:
            self._tick_task.cancel()
            try:
                await self._tick_task
            except asyncio.CancelledError:
                pass
            self._tick_task = None

    @property
    def is_running(self) -> bool:
        return self._running

    async def _tick_loop(self) -> None:
        """Check every second for jobs that are due."""
        while self._running:
            tick_start = time.time()
            now = datetime.now()

            for job in list(self._jobs.values()):
                if job.status != "active" or job.is_running:
                    continue

                # Calculate next fire time
                if job.next_run is None:
                    job.next_run = job.trigger.next_fire_time(now)

                if job.next_run is None:
                    job.status = "completed"
                    continue

                if now >= job.next_run:
                    asyncio.create_task(self._execute_job(job))

            elapsed = time.time() - tick_start
            await asyncio.sleep(max(0, 1.0 - elapsed))

    async def _execute_job(self, job: CronJob) -> None:
        """Execute a single job with concurrency guard and timeout."""
        job.is_running = True
        self._emit("cron.job.fired", {"job_id": job.id})

        try:
            if asyncio.iscoroutinefunction(job.func):
                await asyncio.wait_for(
                    job.func(*job.args, **job.kwargs),
                    timeout=job.timeout,
                )
            else:
                # Run sync functions in executor to avoid blocking the loop
                loop = asyncio.get_running_loop()
                await asyncio.wait_for(
                    loop.run_in_executor(
                        None, lambda: job.func(*job.args, **job.kwargs)
                    ),
                    timeout=job.timeout,
                )

            job.run_count += 1
            job.last_run = time.time()
            self._emit("cron.job.completed", {
                "job_id": job.id,
                "run_count": job.run_count,
            })

            # Notify trigger via public interface
            job.trigger.mark_fired(job.last_run)
            if isinstance(job.trigger, OnceTrigger):
                job.status = "completed"

            job.next_run = job.trigger.next_fire_time(datetime.now())

        except asyncio.TimeoutError:
            job.error_count += 1
            job.last_error = f"Job timed out after {job.timeout}s"
            job.next_run = job.trigger.next_fire_time(datetime.now())
            self._emit("cron.job.failed", {
                "job_id": job.id,
                "error": job.last_error,
            })
            logger.error("Job %s timed out after %.0fs", job.id, job.timeout)
        except Exception as exc:
            job.error_count += 1
            job.last_error = str(exc)
            job.next_run = job.trigger.next_fire_time(datetime.now())
            self._emit("cron.job.failed", {
                "job_id": job.id,
                "error": str(exc),
            })
            logger.warning("Job %s failed: %s", job.id, exc)
        finally:
            job.is_running = False

    # ------------------------------------------------------------------
    # EventBus
    # ------------------------------------------------------------------

    def _emit(self, event_type: str, data: dict[str, Any]) -> None:
        """Publish event to bus (fire-and-forget)."""
        if self._bus is None:
            return
        from ..bus.events import BusEvent

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(
                self._bus.publish(BusEvent(
                    type=event_type,
                    data=data,
                    source="cron_scheduler",
                ))
            )
        except RuntimeError:
            pass  # no running loop
