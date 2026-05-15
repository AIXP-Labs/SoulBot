"""ScheduleService — bridge between CommandExecutor and CronScheduler.

Receives parsed schedule commands from AI output, creates CronJobs,
and publishes results back via EventBus when tasks fire.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable

from .triggers import BaseTrigger, CronTrigger, IntervalTrigger, OnceTrigger

if TYPE_CHECKING:
    from .cron import CronScheduler
    from .heartbeat_store import HeartbeatStore
    from .sqlite_store import SqliteScheduleStore
    from ..bus.event_bus import EventBus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class ScheduleEntry:
    """A scheduled task entry."""

    id: str
    trigger_config: dict
    aisop: list = field(default_factory=list)
    task: dict = field(default_factory=dict)
    status: str = "active"
    origin_channel: str = ""
    origin_user: str = ""
    from_agent: str = ""
    to_agent: str = ""
    created_at: str = ""
    last_run: str | None = None
    run_count: int = 0
    last_result: str | None = None
    last_error: str | None = None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class ScheduleService:
    """Schedule service registered with CommandExecutor as 'schedule'.

    Methods correspond to schedule_guide.md actions:
    add, list, get, cancel, pause, resume, modify.
    """

    def __init__(
        self,
        cron: CronScheduler,
        bus: EventBus | None = None,
        runner_factory: Callable | None = None,
        store: SqliteScheduleStore | None = None,
        heartbeat_store: HeartbeatStore | None = None,
    ) -> None:
        self._cron = cron
        self._bus = bus
        self._runner_factory = runner_factory
        self._store = store
        self._heartbeat_store = heartbeat_store
        self._entries: dict[str, ScheduleEntry] = {}
        self._entry_locks: dict[str, asyncio.Lock] = {}

    # ------------------------------------------------------------------
    # CRUD actions (called by CommandExecutor)
    # ------------------------------------------------------------------

    def add(
        self,
        trigger: dict,
        aisop: list | None = None,
        task: dict | None = None,
        origin_channel: str = "",
        origin_user: str = "",
        from_agent: str = "",
        to_agent: str = "",
        **kwargs: Any,
    ) -> dict:
        """Create a scheduled task."""
        aisop = aisop or []
        task = task or {}

        # Default: to_agent falls back to from_agent (self-to-self)
        if not to_agent:
            to_agent = from_agent

        # Extract ID from AISOP describe or task dict
        entry_id = task.get("id") or _extract_aisop_id(aisop) or (
            f"s_{int(time.time() * 1000) % 100000000:08d}"
        )

        if entry_id in self._entries and self._entries[entry_id].status in (
            "active",
            "paused",
        ):
            raise ValueError(f"Schedule '{entry_id}' already exists")

        trigger_obj = self._build_trigger(trigger)

        entry = ScheduleEntry(
            id=entry_id,
            trigger_config=trigger,
            aisop=aisop,
            task=task,
            origin_channel=origin_channel,
            origin_user=origin_user,
            from_agent=from_agent,
            to_agent=to_agent,
            created_at=datetime.now().isoformat(),
        )
        self._entries[entry_id] = entry

        self._cron.add_job(
            f"sched:{entry_id}",
            self._on_fired,
            trigger_obj,
            kwargs={"entry_id": entry_id},
            replace_existing=True,
        )

        self._persist(entry)
        self._emit("schedule.created", {"entry_id": entry_id})
        logger.info("Schedule created: %s (%s)", entry_id, trigger)
        return {"entry_id": entry_id, "status": "active"}

    def list(self, status: str | None = None, **kwargs: Any) -> dict:
        """List scheduled tasks."""
        entries = list(self._entries.values())
        if status:
            entries = [e for e in entries if e.status == status]
        return {
            "entries": [asdict(e) for e in entries],
            "count": len(entries),
        }

    def get(self, id: str, **kwargs: Any) -> dict:
        """Get a single scheduled task."""
        entry = self._entries.get(id)
        if not entry:
            raise ValueError(f"Schedule '{id}' not found")
        return asdict(entry)

    def cancel(self, id: str, **kwargs: Any) -> dict:
        """Cancel a scheduled task."""
        entry = self._entries.get(id)
        if not entry:
            raise ValueError(f"Schedule '{id}' not found")
        entry.status = "completed"
        self._cron.remove_job(f"sched:{id}")
        self._persist(entry)
        self._emit("schedule.cancelled", {"entry_id": id})
        logger.info("Schedule cancelled: %s", id)
        return {"entry_id": id, "status": "completed"}

    def pause(self, id: str, **kwargs: Any) -> dict:
        """Pause a scheduled task."""
        entry = self._entries.get(id)
        if not entry or entry.status != "active":
            raise ValueError(f"Schedule '{id}' not active")
        entry.status = "paused"
        self._cron.pause_job(f"sched:{id}")
        self._persist(entry)
        return {"entry_id": id, "status": "paused"}

    def resume(self, id: str, **kwargs: Any) -> dict:
        """Resume a paused scheduled task."""
        entry = self._entries.get(id)
        if not entry or entry.status != "paused":
            raise ValueError(f"Schedule '{id}' not paused")
        entry.status = "active"
        self._cron.resume_job(f"sched:{id}")
        self._persist(entry)
        return {"entry_id": id, "status": "active"}

    def modify(self, id: str, trigger: dict, **kwargs: Any) -> dict:
        """Modify the trigger of a scheduled task."""
        entry = self._entries.get(id)
        if not entry:
            raise ValueError(f"Schedule '{id}' not found")
        # Remove old job, create new trigger
        self._cron.remove_job(f"sched:{id}")
        trigger_obj = self._build_trigger(trigger)
        entry.trigger_config = trigger
        self._cron.add_job(
            f"sched:{id}",
            self._on_fired,
            trigger_obj,
            kwargs={"entry_id": id},
        )
        if entry.status == "paused":
            entry.status = "active"
        self._persist(entry)
        return {"entry_id": id, "status": entry.status}

    # ------------------------------------------------------------------
    # Cron callback
    # ------------------------------------------------------------------

    async def fire_now(self, entry_id: str) -> None:
        """Manually fire a schedule entry (for catch-up, debug, etc.)."""
        await self._on_fired(entry_id=entry_id)

    async def _on_fired(self, entry_id: str) -> None:
        """Called by CronScheduler when a job fires."""
        lock = self._entry_locks.setdefault(entry_id, asyncio.Lock())
        if lock.locked():
            logger.warning("Entry %s already executing, skipping", entry_id)
            return
        async with lock:
            await self._on_fired_inner(entry_id)

    async def _on_fired_inner(self, entry_id: str) -> None:
        """Inner implementation — must be called under per-entry lock."""
        entry = self._entries.get(entry_id)
        if not entry:
            return

        entry.run_count += 1
        entry.last_run = datetime.now().isoformat()

        try:
            result = await self._execute_task(entry)
            entry.last_result = result[:2000] if result else None
            entry.last_error = None
        except Exception as exc:
            entry.last_error = str(exc)
            logger.error("Schedule %s execution failed: %s", entry_id, exc)
            self._emit("schedule.failed", {
                "entry_id": entry_id,
                "error": str(exc),
            })

        # OnceTrigger → mark completed
        if entry.trigger_config.get("type") == "once":
            entry.status = "completed"
            self._cron.remove_job(f"sched:{entry_id}")

        self._persist(entry)

    async def _execute_task(self, entry: ScheduleEntry) -> str | None:
        """Execute the task via runner_factory and publish result.

        If the entry has an ``aisop`` payload, it is serialized to JSON
        and sent as the user message (matching newsoulbot's approach).
        Falls back to ``task.message`` for backward compatibility.
        """
        if not self._runner_factory:
            logger.warning("Schedule %s: no runner_factory, cannot execute", entry.id)
            return None

        # AISOP payload takes priority
        if entry.aisop:
            message = json.dumps(entry.aisop, ensure_ascii=False)
        else:
            message = entry.task.get("message", entry.task.get("description", ""))

        if not message:
            logger.warning("Schedule %s: no aisop or message in task", entry.id)
            return None

        is_heartbeat = entry.origin_channel == "heartbeat"

        context = {
            "type": "scheduled",
            "entry_id": entry.id,
            "origin_channel": entry.origin_channel,
            "origin_user": entry.origin_user,
            "to_agent": entry.to_agent,
        }
        # Allow heartbeat tasks to create follow-up OnceTriggers
        if is_heartbeat:
            context["allow_nested_schedule"] = True

        result_text = ""
        async for event in self._runner_factory(
            entry.to_agent, message, context
        ):
            if event.is_final_response() and event.content:
                result_text = " ".join(
                    p.text for p in event.content.parts if p.text
                )

        # Heartbeat skip check
        is_skipped = (
            is_heartbeat
            and "[heartbeat:skip]" in result_text.lower().replace(" ", "")
        )

        # Write heartbeat history
        if is_heartbeat and self._heartbeat_store:
            self._heartbeat_store.record(
                agent_name=entry.to_agent,
                entry_id=entry.id,
                result=result_text[:2000] if result_text else "",
                skipped=is_skipped,
            )

        if is_skipped:
            logger.info("Heartbeat skipped for %s (entry=%s)", entry.to_agent, entry.id)
            return result_text

        # Chain break detection: non-skip heartbeat should create follow-up
        if is_heartbeat:
            has_follow_up = any(
                e.origin_channel == "heartbeat"
                and e.to_agent == entry.to_agent
                and e.id != entry.id
                and e.status == "active"
                for e in self._entries.values()
            )
            if not has_follow_up:
                logger.warning(
                    "Heartbeat chain break: %s produced no follow-up OnceTrigger. "
                    "Next daily seed will recover.",
                    entry.to_agent,
                )

        # Publish result for channel delivery
        if self._bus:
            from ..bus.events import BusEvent

            await self._bus.publish(BusEvent(
                type="schedule.executed",
                data={
                    "entry_id": entry.id,
                    "from_agent": entry.from_agent,
                    "to_agent": entry.to_agent,
                    "origin_channel": entry.origin_channel,
                    "origin_user": entry.origin_user,
                    "result": result_text[:2000] if result_text else None,
                },
                source="schedule_service",
            ))

        return result_text

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _persist(self, entry: ScheduleEntry) -> None:
        """Save a single entry to the store (if available)."""
        if self._store:
            self._store.save_entry(entry)

    def restore(self) -> int:
        """Restore active schedules from store after restart."""
        if not self._store:
            return 0

        for entry in self._store.list_entries():
            self._entries[entry.id] = entry

        now = datetime.now()
        restored = 0

        for entry_id, entry in list(self._entries.items()):
            if entry.status != "active":
                continue

            tc = entry.trigger_config
            # Skip expired OnceTriggers
            if tc.get("type") == "once":
                if "run_at" in tc:
                    run_at = datetime.fromisoformat(tc["run_at"])
                    if run_at < now:
                        entry.status = "completed"
                        self._persist(entry)
                        continue
                elif "delay" in tc:
                    # Relative delay cannot be recovered
                    entry.status = "completed"
                    self._persist(entry)
                    continue

            try:
                trigger = self._build_trigger(tc)
                self._cron.add_job(
                    f"sched:{entry_id}",
                    self._on_fired,
                    trigger,
                    kwargs={"entry_id": entry_id},
                    replace_existing=True,
                )
                restored += 1
            except Exception as exc:
                logger.warning("Failed to restore schedule %s: %s", entry_id, exc)
                entry.status = "completed"
                self._persist(entry)

        if restored:
            logger.info("Restored %d scheduled tasks", restored)
        return restored

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_trigger(config: dict) -> BaseTrigger:
        """Build a Trigger object from JSON config."""
        trigger_type = config.get("type", "")
        if trigger_type == "once":
            if "run_at" in config:
                return OnceTrigger(run_at=datetime.fromisoformat(config["run_at"]))
            return OnceTrigger(delay=config.get("delay", 60))
        if trigger_type == "interval":
            return IntervalTrigger(
                seconds=config.get("seconds", 0),
                minutes=config.get("minutes", 0),
                hours=config.get("hours", 0),
            )
        if trigger_type == "cron":
            return CronTrigger(
                minute=config.get("minute"),
                hour=config.get("hour"),
                day_of_week=config.get("day_of_week"),
            )
        raise ValueError(f"Unknown trigger type: {trigger_type}")

    def _emit(self, event_type: str, data: dict) -> None:
        """Fire-and-forget event publish."""
        if not self._bus:
            return
        import asyncio
        from ..bus.events import BusEvent

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._bus.publish(BusEvent(
                type=event_type,
                data=data,
                source="schedule_service",
            )))
        except RuntimeError:
            pass


def _extract_aisop_id(aisop: list) -> str | None:
    """Extract the schedule ID from AISOP system content ``id`` field."""
    for msg in aisop:
        if msg.get("role") == "system":
            content = msg.get("content", {})
            if isinstance(content, dict) and content.get("id"):
                return content["id"]
    return None
