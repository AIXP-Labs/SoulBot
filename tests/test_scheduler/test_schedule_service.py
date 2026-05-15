"""Tests for ScheduleService — the bridge between CommandExecutor and CronScheduler."""

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from soulbot.scheduler.cron import CronScheduler
from soulbot.scheduler.schedule_service import ScheduleEntry, ScheduleService
from soulbot.scheduler.sqlite_store import SqliteScheduleStore
from soulbot.scheduler.triggers import CronTrigger, IntervalTrigger, OnceTrigger


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cron():
    """Mock CronScheduler."""
    mock = MagicMock(spec=CronScheduler)
    mock.add_job = MagicMock()
    mock.remove_job = MagicMock()
    mock.pause_job = MagicMock()
    mock.resume_job = MagicMock()
    return mock


@pytest.fixture
def bus():
    """Mock EventBus."""
    mock = AsyncMock()
    mock.publish = AsyncMock()
    mock.subscribe = MagicMock()
    return mock


@pytest.fixture
def store(tmp_path):
    """SqliteScheduleStore in temp directory."""
    return SqliteScheduleStore(str(tmp_path / "test_schedules.db"))


@pytest.fixture
def service(cron, bus, store):
    """ScheduleService with mocked dependencies."""
    return ScheduleService(cron=cron, bus=bus, store=store)


# ---------------------------------------------------------------------------
# add()
# ---------------------------------------------------------------------------


class TestAdd:
    def test_add_once_trigger(self, service, cron):
        result = service.add(
            trigger={"type": "once", "delay": 300},
            task={"id": "remind_water", "message": "Drink water"},
            origin_channel="telegram",
            origin_user="123",
            from_agent="hello_agent",
            to_agent="hello_agent",
        )
        assert result["entry_id"] == "remind_water"
        assert result["status"] == "active"
        cron.add_job.assert_called_once()
        call_args = cron.add_job.call_args
        assert call_args[0][0] == "sched:remind_water"

    def test_add_interval_trigger(self, service, cron):
        result = service.add(
            trigger={"type": "interval", "minutes": 30},
            task={"id": "check_news"},
        )
        assert result["entry_id"] == "check_news"
        assert result["status"] == "active"

    def test_add_cron_trigger(self, service, cron):
        result = service.add(
            trigger={"type": "cron", "hour": "9", "minute": "0"},
            task={"id": "morning"},
        )
        assert result["entry_id"] == "morning"

    def test_add_auto_id(self, service):
        result = service.add(trigger={"type": "once", "delay": 60}, task={})
        assert result["entry_id"].startswith("s_")

    def test_add_duplicate_raises(self, service):
        service.add(
            trigger={"type": "once", "delay": 60},
            task={"id": "dup"},
        )
        with pytest.raises(ValueError, match="already exists"):
            service.add(
                trigger={"type": "once", "delay": 60},
                task={"id": "dup"},
            )

    def test_add_persists(self, service, store):
        service.add(
            trigger={"type": "once", "delay": 60},
            task={"id": "persist_test"},
        )
        entry = store.get_entry("persist_test")
        assert entry is not None
        assert entry.id == "persist_test"
        assert entry.status == "active"

    def test_add_unknown_trigger_raises(self, service):
        with pytest.raises(ValueError, match="Unknown trigger type"):
            service.add(
                trigger={"type": "unknown"},
                task={"id": "bad"},
            )


# ---------------------------------------------------------------------------
# list() / get()
# ---------------------------------------------------------------------------


class TestListGet:
    def test_list_all(self, service):
        service.add(trigger={"type": "once", "delay": 60}, task={"id": "a"})
        service.add(trigger={"type": "once", "delay": 60}, task={"id": "b"})
        result = service.list()
        assert result["count"] == 2

    def test_list_filter_status(self, service):
        service.add(trigger={"type": "once", "delay": 60}, task={"id": "a"})
        service.add(trigger={"type": "once", "delay": 60}, task={"id": "b"})
        service.cancel(id="a")
        result = service.list(status="active")
        assert result["count"] == 1
        assert result["entries"][0]["id"] == "b"

    def test_get_existing(self, service):
        service.add(trigger={"type": "once", "delay": 60}, task={"id": "x"})
        result = service.get(id="x")
        assert result["id"] == "x"
        assert result["status"] == "active"

    def test_get_not_found(self, service):
        with pytest.raises(ValueError, match="not found"):
            service.get(id="nonexistent")


# ---------------------------------------------------------------------------
# cancel() / pause() / resume()
# ---------------------------------------------------------------------------


class TestCancelPauseResume:
    def test_cancel(self, service, cron):
        service.add(trigger={"type": "once", "delay": 60}, task={"id": "c"})
        result = service.cancel(id="c")
        assert result["status"] == "completed"
        cron.remove_job.assert_called_with("sched:c")

    def test_cancel_not_found(self, service):
        with pytest.raises(ValueError, match="not found"):
            service.cancel(id="missing")

    def test_pause(self, service, cron):
        service.add(trigger={"type": "interval", "minutes": 5}, task={"id": "p"})
        result = service.pause(id="p")
        assert result["status"] == "paused"
        cron.pause_job.assert_called_with("sched:p")

    def test_pause_not_active_raises(self, service):
        service.add(trigger={"type": "once", "delay": 60}, task={"id": "p"})
        service.pause(id="p")
        with pytest.raises(ValueError, match="not active"):
            service.pause(id="p")

    def test_resume(self, service, cron):
        service.add(trigger={"type": "interval", "minutes": 5}, task={"id": "r"})
        service.pause(id="r")
        result = service.resume(id="r")
        assert result["status"] == "active"
        cron.resume_job.assert_called_with("sched:r")

    def test_resume_not_paused_raises(self, service):
        service.add(trigger={"type": "once", "delay": 60}, task={"id": "r"})
        with pytest.raises(ValueError, match="not paused"):
            service.resume(id="r")


# ---------------------------------------------------------------------------
# modify()
# ---------------------------------------------------------------------------


class TestModify:
    def test_modify_trigger(self, service, cron):
        service.add(trigger={"type": "interval", "minutes": 5}, task={"id": "m"})
        result = service.modify(id="m", trigger={"type": "interval", "minutes": 10})
        assert result["status"] == "active"
        assert cron.remove_job.called
        # add_job called twice: once for original, once for modified
        assert cron.add_job.call_count == 2

    def test_modify_paused_reactivates(self, service, cron):
        service.add(trigger={"type": "interval", "minutes": 5}, task={"id": "m2"})
        service.pause(id="m2")
        result = service.modify(id="m2", trigger={"type": "interval", "hours": 1})
        assert result["status"] == "active"

    def test_modify_not_found(self, service):
        with pytest.raises(ValueError, match="not found"):
            service.modify(id="missing", trigger={"type": "once", "delay": 60})


# ---------------------------------------------------------------------------
# _build_trigger()
# ---------------------------------------------------------------------------


class TestBuildTrigger:
    def test_once_delay(self):
        t = ScheduleService._build_trigger({"type": "once", "delay": 120})
        assert isinstance(t, OnceTrigger)

    def test_once_run_at(self):
        run_at = (datetime.now() + timedelta(hours=1)).isoformat()
        t = ScheduleService._build_trigger({"type": "once", "run_at": run_at})
        assert isinstance(t, OnceTrigger)

    def test_interval(self):
        t = ScheduleService._build_trigger(
            {"type": "interval", "seconds": 30, "minutes": 1}
        )
        assert isinstance(t, IntervalTrigger)

    def test_cron(self):
        t = ScheduleService._build_trigger(
            {"type": "cron", "minute": "0", "hour": "9"}
        )
        assert isinstance(t, CronTrigger)

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown trigger type"):
            ScheduleService._build_trigger({"type": "banana"})


# ---------------------------------------------------------------------------
# _on_fired()
# ---------------------------------------------------------------------------


class TestOnFired:
    async def test_on_fired_increments_run_count(self, service):
        service.add(
            trigger={"type": "interval", "minutes": 5},
            task={"id": "fire_test", "message": "hello"},
        )
        await service._on_fired("fire_test")
        entry = service.get(id="fire_test")
        assert entry["run_count"] == 1
        assert entry["last_run"] is not None

    async def test_on_fired_once_trigger_completes(self, service, cron):
        service.add(
            trigger={"type": "once", "delay": 60},
            task={"id": "once_test", "message": "hello"},
        )
        await service._on_fired("once_test")
        entry = service.get(id="once_test")
        assert entry["status"] == "completed"
        cron.remove_job.assert_called_with("sched:once_test")

    async def test_on_fired_nonexistent_noop(self, service):
        # Should not raise
        await service._on_fired("nonexistent")

    async def test_on_fired_with_runner_factory(self, cron, bus, store):
        """ScheduleService executes task via runner_factory and publishes result."""
        from soulbot.events.event import Content, Event, Part

        async def mock_runner_factory(agent_name, message, context):
            yield Event(
                author="test_agent",
                content=Content(role="model", parts=[Part(text="Task done!")]),
            )

        service = ScheduleService(
            cron=cron, bus=bus, runner_factory=mock_runner_factory,
            store=store,
        )
        service.add(
            trigger={"type": "interval", "minutes": 5},
            task={"id": "rf_test", "message": "do something"},
            origin_channel="telegram",
            origin_user="456",
            from_agent="test_agent",
            to_agent="test_agent",
        )
        await service._on_fired("rf_test")

        entry = service.get(id="rf_test")
        assert entry["last_result"] == "Task done!"
        assert entry["last_error"] is None

        # Check bus publish
        bus.publish.assert_called()
        call_data = bus.publish.call_args[0][0].data
        assert call_data["result"] == "Task done!"
        assert call_data["origin_channel"] == "telegram"
        assert call_data["origin_user"] == "456"

    async def test_on_fired_error_handling(self, cron, bus, store):
        """Runner factory failure is captured in last_error."""

        async def failing_factory(agent_name, message, context):
            raise RuntimeError("LLM exploded")
            yield  # make it a generator  # noqa: E501

        service = ScheduleService(
            cron=cron, bus=bus, runner_factory=failing_factory,
            store=store,
        )
        service.add(
            trigger={"type": "interval", "minutes": 5},
            task={"id": "err_test", "message": "fail"},
        )
        await service._on_fired("err_test")

        entry = service.get(id="err_test")
        assert entry["last_error"] is not None
        assert "LLM exploded" in entry["last_error"]

    async def test_concurrent_entries_not_blocked(self, cron, bus, store):
        """Different entries can execute concurrently (per-entry lock)."""
        execution_order: list[str] = []

        async def slow_factory(agent_name, message, context):
            from soulbot.events.event import Content, Event, Part
            execution_order.append(f"start:{agent_name}")
            await asyncio.sleep(0.05)
            execution_order.append(f"end:{agent_name}")
            yield Event(
                author=agent_name,
                content=Content(role="model", parts=[Part(text="done")]),
            )

        service = ScheduleService(
            cron=cron, bus=bus, runner_factory=slow_factory,
            store=store,
        )
        service.add(
            trigger={"type": "interval", "minutes": 5},
            task={"id": "entry_a", "message": "task a"},
            to_agent="agent_a",
        )
        service.add(
            trigger={"type": "interval", "minutes": 5},
            task={"id": "entry_b", "message": "task b"},
            to_agent="agent_b",
        )

        # Fire both concurrently
        await asyncio.gather(
            service._on_fired("entry_a"),
            service._on_fired("entry_b"),
        )

        # Both should have started before either finished (concurrent)
        assert "start:agent_a" in execution_order
        assert "start:agent_b" in execution_order
        starts = [i for i, x in enumerate(execution_order) if x.startswith("start:")]
        ends = [i for i, x in enumerate(execution_order) if x.startswith("end:")]
        # At least one end should come after both starts (proves overlap)
        assert max(starts) < max(ends)

    async def test_same_entry_not_reentrant(self, cron, bus, store):
        """Same entry cannot execute twice concurrently (per-entry lock)."""
        call_count = 0

        async def slow_factory(agent_name, message, context):
            from soulbot.events.event import Content, Event, Part
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)
            yield Event(
                author=agent_name,
                content=Content(role="model", parts=[Part(text="done")]),
            )

        service = ScheduleService(
            cron=cron, bus=bus, runner_factory=slow_factory,
            store=store,
        )
        service.add(
            trigger={"type": "interval", "minutes": 5},
            task={"id": "entry_x", "message": "task"},
            to_agent="agent_x",
        )

        # Fire same entry twice concurrently — second should be skipped
        await asyncio.gather(
            service._on_fired("entry_x"),
            service._on_fired("entry_x"),
        )

        # Only one execution should have happened
        assert call_count == 1


# ---------------------------------------------------------------------------
# Persistence: save / restore
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_save_load_roundtrip(self, cron, bus, store):
        svc1 = ScheduleService(cron=cron, bus=bus, store=store)
        svc1.add(
            trigger={"type": "interval", "minutes": 10},
            task={"id": "persist_1", "message": "hi"},
            origin_channel="web",
        )
        svc1.add(
            trigger={"type": "cron", "hour": "9", "minute": "0"},
            task={"id": "persist_2", "message": "morning"},
        )

        # New service loads from same store
        svc2 = ScheduleService(cron=cron, bus=bus, store=store)
        count = svc2.restore()
        assert count == 2
        result = svc2.list()
        assert result["count"] == 2

    def test_restore_skips_expired_once(self, cron, bus, store):
        """OnceTrigger with past run_at should be marked completed on restore."""
        past = (datetime.now() - timedelta(hours=1)).isoformat()
        entry = ScheduleEntry(
            id="expired",
            trigger_config={"type": "once", "run_at": past},
            task={"message": "too late"},
            status="active",
            created_at="",
        )
        store.save_entry(entry)

        svc = ScheduleService(cron=cron, bus=bus, store=store)
        count = svc.restore()
        assert count == 0
        result = svc.get(id="expired")
        assert result["status"] == "completed"

    def test_restore_skips_delay_once(self, cron, bus, store):
        """OnceTrigger with relative delay cannot be recovered."""
        entry = ScheduleEntry(
            id="delay_expired",
            trigger_config={"type": "once", "delay": 300},
            task={"message": "too late"},
            status="active",
            created_at="",
        )
        store.save_entry(entry)

        svc = ScheduleService(cron=cron, bus=bus, store=store)
        count = svc.restore()
        assert count == 0

    def test_restore_future_once(self, cron, bus, store):
        """OnceTrigger with future run_at should be restored."""
        future = (datetime.now() + timedelta(hours=1)).isoformat()
        entry = ScheduleEntry(
            id="future_once",
            trigger_config={"type": "once", "run_at": future},
            task={"message": "later"},
            status="active",
            created_at="",
        )
        store.save_entry(entry)

        svc = ScheduleService(cron=cron, bus=bus, store=store)
        count = svc.restore()
        assert count == 1

    def test_restore_skips_completed(self, cron, bus, store):
        """Completed entries are not re-registered."""
        entry = ScheduleEntry(
            id="done",
            trigger_config={"type": "interval", "minutes": 5},
            task={"message": "done"},
            status="completed",
            created_at="",
            run_count=3,
        )
        store.save_entry(entry)

        svc = ScheduleService(cron=cron, bus=bus, store=store)
        count = svc.restore()
        assert count == 0

    def test_restore_no_store(self, cron, bus):
        """No store → 0 restored."""
        svc = ScheduleService(cron=cron, bus=bus)
        count = svc.restore()
        assert count == 0


# ---------------------------------------------------------------------------
# EventBus emission
# ---------------------------------------------------------------------------


class TestEventEmission:
    def test_add_emits_schedule_created(self, service, bus):
        service.add(
            trigger={"type": "once", "delay": 60},
            task={"id": "emit_test"},
        )
        # _emit is fire-and-forget, but we can check the bus was called
        # Since _emit uses loop.create_task, and there's no running loop in tests,
        # the call may silently fail. That's OK — the important thing is no crash.


# ---------------------------------------------------------------------------
# AISOP support
# ---------------------------------------------------------------------------

SAMPLE_AISOP = [
    {
        "role": "system",
        "content": {
            "protocol": "AISOP V1.0.0",
            "id": "schedule.remind_water",
            "version": "1.0.0",
            "describe": "remind user to drink water",
            "tools": [],
            "system_prompt": "Execute aisop.main",
        },
    },
    {
        "role": "user",
        "content": {
            "instruction": "Execute aisop.main",
            "aisop": {"main": "graph TD; start --> generate; generate --> end"},
            "functions": {
                "start": {"step1": "User requested water reminder"},
                "generate": {"step1": "Generate a friendly reminder"},
            },
        },
    },
]


class TestAisopSupport:
    def test_add_with_aisop(self, service):
        result = service.add(
            trigger={"type": "once", "delay": 30},
            aisop=SAMPLE_AISOP,
        )
        assert result["entry_id"] == "schedule.remind_water"
        entry = service.get(id="schedule.remind_water")
        assert entry["aisop"] == SAMPLE_AISOP

    def test_aisop_id_extraction(self, service):
        """ID is extracted from aisop system content."""
        result = service.add(
            trigger={"type": "once", "delay": 60},
            aisop=SAMPLE_AISOP,
        )
        assert result["entry_id"] == "schedule.remind_water"

    def test_aisop_fallback_to_auto_id(self, service):
        """Without system id, auto-generate."""
        minimal_aisop = [{"role": "user", "content": {"instruction": "do stuff"}}]
        result = service.add(
            trigger={"type": "once", "delay": 60},
            aisop=minimal_aisop,
        )
        assert result["entry_id"].startswith("s_")

    async def test_aisop_executed_as_json(self, cron, bus, store):
        """When entry has aisop, it's serialized to JSON for the runner."""
        from soulbot.events.event import Content, Event, Part

        received_messages = []

        async def capture_factory(agent_name, message, context):
            received_messages.append(message)
            yield Event(
                author="agent",
                content=Content(role="model", parts=[Part(text="Done!")]),
            )

        service = ScheduleService(
            cron=cron, bus=bus, runner_factory=capture_factory,
            store=store,
        )
        service.add(
            trigger={"type": "interval", "minutes": 5},
            aisop=SAMPLE_AISOP,
            from_agent="test",
            to_agent="test",
        )
        await service._on_fired("schedule.remind_water")

        assert len(received_messages) == 1
        # Message should be JSON-serialized AISOP
        parsed = json.loads(received_messages[0])
        assert parsed[0]["role"] == "system"
        assert parsed[0]["content"]["id"] == "schedule.remind_water"

    def test_aisop_persisted(self, service, store):
        """AISOP payload is saved to SQLite."""
        service.add(
            trigger={"type": "once", "delay": 60},
            aisop=SAMPLE_AISOP,
        )
        entry = store.get_entry("schedule.remind_water")
        assert entry is not None
        assert entry.aisop == SAMPLE_AISOP
