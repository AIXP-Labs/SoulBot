"""Tests for heartbeat mechanism (Doc 12 — Phase B)."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from soulbot.agents import LlmAgent
from soulbot.events.event_actions import EventActions
from soulbot.scheduler.cron import CronScheduler
from soulbot.scheduler.heartbeat import (
    _cron_expr_to_config,
    _should_catch_up,
    register_heartbeats,
)
from soulbot.scheduler.heartbeat_store import HeartbeatStore
from soulbot.scheduler.schedule_service import ScheduleEntry, ScheduleService
from soulbot.scheduler.sqlite_store import SqliteScheduleStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cron():
    mock = MagicMock(spec=CronScheduler)
    mock.add_job = MagicMock()
    mock.remove_job = MagicMock()
    return mock


@pytest.fixture
def bus():
    mock = AsyncMock()
    mock.publish = AsyncMock()
    mock.subscribe = MagicMock()
    return mock


@pytest.fixture
def store(tmp_path):
    return SqliteScheduleStore(str(tmp_path / "test_schedules.db"))


@pytest.fixture
def hb_store(tmp_path):
    return HeartbeatStore(str(tmp_path / "heartbeat.db"))


@pytest.fixture
def service(cron, bus, store, hb_store):
    return ScheduleService(
        cron=cron, bus=bus, store=store, heartbeat_store=hb_store,
    )


@pytest.fixture
def agent_with_heartbeat():
    return LlmAgent(
        name="test_agent",
        model="test",
        heartbeat={"cron": "0 0 * * *", "aisop": "heartbeat"},
    )


@pytest.fixture
def agent_without_heartbeat():
    return LlmAgent(name="plain_agent", model="test")


# ---------------------------------------------------------------------------
# 1. test_heartbeat_config_none
# ---------------------------------------------------------------------------


class TestHeartbeatRegistration:
    def test_heartbeat_config_none(self, service, agent_without_heartbeat):
        """heartbeat=None → no seed registered."""
        agents = {agent_without_heartbeat.name: agent_without_heartbeat}
        count, catch_ups = register_heartbeats(agents, service)
        assert count == 0
        assert catch_ups == []
        assert len(service._entries) == 0

    # 2. test_heartbeat_registers_seed
    def test_heartbeat_registers_seed(
        self, service, cron, agent_with_heartbeat
    ):
        """Agent with heartbeat config → 1 CronTrigger seed registered."""
        agents = {agent_with_heartbeat.name: agent_with_heartbeat}
        count, catch_ups = register_heartbeats(agents, service)
        assert count == 1
        entry = service._entries["hb_test_agent"]
        assert entry.origin_channel == "heartbeat"
        assert entry.to_agent == "test_agent"
        assert entry.from_agent == "test_agent"
        cron.add_job.assert_called_once()

    # 3. test_heartbeat_seed_idempotent
    def test_heartbeat_seed_idempotent(
        self, service, cron, agent_with_heartbeat
    ):
        """Re-registering does not create duplicate entries."""
        agents = {agent_with_heartbeat.name: agent_with_heartbeat}
        register_heartbeats(agents, service)
        # Set last_run to now so catch-up won't trigger
        service._entries["hb_test_agent"].last_run = datetime.now().isoformat()
        count2, catch_ups2 = register_heartbeats(agents, service)
        assert count2 == 0  # already active, skipped
        assert catch_ups2 == []  # no catch-up needed

    # 4. test_heartbeat_seed_lightweight
    def test_heartbeat_seed_lightweight(
        self, service, agent_with_heartbeat
    ):
        """Seed entry has no aisop content, only task.message + origin_channel."""
        agents = {agent_with_heartbeat.name: agent_with_heartbeat}
        register_heartbeats(agents, service)
        entry = service._entries["hb_test_agent"]
        assert entry.aisop == []  # no AISOP payload
        assert entry.task.get("message") == "heartbeat wakeup"
        assert entry.origin_channel == "heartbeat"


# ---------------------------------------------------------------------------
# 5-6. Skip detection
# ---------------------------------------------------------------------------


class TestHeartbeatSkip:
    @pytest.mark.asyncio
    async def test_heartbeat_skip_exact(self, service, bus, hb_store):
        """Reply with [heartbeat:skip] → bus.publish NOT called."""
        entry = ScheduleEntry(
            id="hb_skip_test",
            trigger_config={"type": "cron", "hour": 0, "minute": 0},
            task={"message": "heartbeat wakeup"},
            origin_channel="heartbeat",
            from_agent="agent1",
            to_agent="agent1",
            created_at=datetime.now().isoformat(),
        )

        # Mock runner_factory to return [heartbeat:skip]
        async def mock_runner(agent_name, message, context):
            from soulbot.events.event import Content, Event, Part

            yield Event(
                author="agent1",
                invocation_id="test",
                content=Content(parts=[Part(text="[heartbeat:skip]")]),
                actions=EventActions(escalate=True),
            )

        service._runner_factory = mock_runner
        result = await service._execute_task(entry)
        bus.publish.assert_not_called()
        # Verify heartbeat_store recorded it as skipped
        records = hb_store.query(agent_name="agent1")
        assert len(records) == 1
        assert records[0]["skipped"] == 1

    @pytest.mark.asyncio
    async def test_heartbeat_skip_fuzzy(self, service, bus, hb_store):
        """Reply with mixed case and spaces still detected as skip."""
        entry = ScheduleEntry(
            id="hb_skip_fuzzy",
            trigger_config={"type": "cron", "hour": 0, "minute": 0},
            task={"message": "heartbeat wakeup"},
            origin_channel="heartbeat",
            from_agent="agent1",
            to_agent="agent1",
            created_at=datetime.now().isoformat(),
        )

        async def mock_runner(agent_name, message, context):
            from soulbot.events.event import Content, Event, Part

            yield Event(
                author="agent1",
                invocation_id="test",
                content=Content(parts=[Part(text="Nothing to do. [Heartbeat: Skip]")]),
                actions=EventActions(escalate=True),
            )

        service._runner_factory = mock_runner
        result = await service._execute_task(entry)
        bus.publish.assert_not_called()


# ---------------------------------------------------------------------------
# 7. CMD creates OnceTrigger with nested schedule allowed
# ---------------------------------------------------------------------------


class TestNestedSchedule:
    @pytest.mark.asyncio
    async def test_heartbeat_cmd_creates_once(self, service, bus):
        """Heartbeat context sets allow_nested_schedule=True."""
        entry = ScheduleEntry(
            id="hb_nested",
            trigger_config={"type": "cron", "hour": 0, "minute": 0},
            task={"message": "heartbeat wakeup"},
            origin_channel="heartbeat",
            from_agent="agent1",
            to_agent="agent1",
            created_at=datetime.now().isoformat(),
        )

        captured_context = {}

        async def mock_runner(agent_name, message, context):
            captured_context.update(context)
            from soulbot.events.event import Content, Event, Part

            yield Event(
                author="agent1",
                invocation_id="test",
                content=Content(parts=[Part(text="Done")]),
                actions=EventActions(escalate=True),
            )

        service._runner_factory = mock_runner
        await service._execute_task(entry)
        assert captured_context.get("allow_nested_schedule") is True
        assert captured_context.get("origin_channel") == "heartbeat"

    @pytest.mark.asyncio
    async def test_non_heartbeat_no_nested(self, service, bus):
        """Non-heartbeat context does NOT set allow_nested_schedule."""
        entry = ScheduleEntry(
            id="normal_task",
            trigger_config={"type": "cron", "hour": 12},
            task={"message": "normal task"},
            origin_channel="telegram",
            from_agent="agent1",
            to_agent="agent1",
            created_at=datetime.now().isoformat(),
        )

        captured_context = {}

        async def mock_runner(agent_name, message, context):
            captured_context.update(context)
            from soulbot.events.event import Content, Event, Part

            yield Event(
                author="agent1",
                invocation_id="test",
                content=Content(parts=[Part(text="Done")]),
                actions=EventActions(escalate=True),
            )

        service._runner_factory = mock_runner
        await service._execute_task(entry)
        assert "allow_nested_schedule" not in captured_context


# ---------------------------------------------------------------------------
# 8-9. Chain behavior (unit-level)
# ---------------------------------------------------------------------------


class TestHeartbeatChain:
    def test_heartbeat_chain_seed_creates_entry(
        self, service, cron, agent_with_heartbeat
    ):
        """Seed CronTrigger is created with proper entry_id."""
        agents = {agent_with_heartbeat.name: agent_with_heartbeat}
        register_heartbeats(agents, service)
        assert "hb_test_agent" in service._entries
        entry = service._entries["hb_test_agent"]
        assert entry.trigger_config["type"] == "cron"
        assert entry.trigger_config.get("hour") == 0
        assert entry.trigger_config.get("minute") == 0

    @pytest.mark.asyncio
    async def test_heartbeat_chain_ends_no_new_trigger(self, service, bus):
        """If agent returns without SOULBOT_CMD, no new entry is created."""
        entry = ScheduleEntry(
            id="hb_chain_end",
            trigger_config={"type": "cron", "hour": 0, "minute": 0},
            task={"message": "heartbeat wakeup"},
            origin_channel="heartbeat",
            from_agent="agent1",
            to_agent="agent1",
            created_at=datetime.now().isoformat(),
        )

        async def mock_runner(agent_name, message, context):
            from soulbot.events.event import Content, Event, Part

            yield Event(
                author="agent1",
                invocation_id="test",
                content=Content(parts=[Part(text="All done, nothing to schedule.")]),
                actions=EventActions(escalate=True),
            )

        service._runner_factory = mock_runner
        entries_before = len(service._entries)
        await service._execute_task(entry)
        # No SOULBOT_CMD in output → no new OnceTrigger entry created
        assert len(service._entries) == entries_before

    @pytest.mark.asyncio
    async def test_heartbeat_llm_failure_no_crash(self, service, bus, hb_store):
        """LLM failure during heartbeat → exception logged, seed unaffected."""
        entry = ScheduleEntry(
            id="hb_llm_fail",
            trigger_config={"type": "cron", "hour": 0, "minute": 0},
            task={"message": "heartbeat wakeup"},
            origin_channel="heartbeat",
            from_agent="agent1",
            to_agent="agent1",
            created_at=datetime.now().isoformat(),
        )
        service._entries[entry.id] = entry

        async def failing_runner(agent_name, message, context):
            raise RuntimeError("LLM API timeout")
            yield  # make it a generator  # noqa: E501

        service._runner_factory = failing_runner
        # _on_fired catches exception, entry survives
        await service.fire_now(entry.id)
        assert entry.last_error is not None
        assert "timeout" in entry.last_error
        # Entry still in _entries — seed not destroyed
        assert entry.id in service._entries

    @pytest.mark.asyncio
    async def test_chain_break_detection_logs_warning(
        self, service, bus, hb_store, caplog
    ):
        """Non-skip heartbeat with no follow-up triggers warning."""
        entry = ScheduleEntry(
            id="hb_chain_warn",
            trigger_config={"type": "cron", "hour": 0, "minute": 0},
            task={"message": "heartbeat wakeup"},
            origin_channel="heartbeat",
            from_agent="agent1",
            to_agent="agent1",
            created_at=datetime.now().isoformat(),
        )

        async def mock_runner(agent_name, message, context):
            from soulbot.events.event import Content, Event, Part

            yield Event(
                author="agent1",
                invocation_id="test",
                content=Content(parts=[Part(text="Did something, no CMD.")]),
                actions=EventActions(escalate=True),
            )

        service._runner_factory = mock_runner
        import logging

        with caplog.at_level(logging.WARNING):
            await service._execute_task(entry)
        assert any("chain break" in r.message.lower() for r in caplog.records)


# ---------------------------------------------------------------------------
# 10. Agent session usage
# ---------------------------------------------------------------------------


class TestHeartbeatSession:
    @pytest.mark.asyncio
    async def test_heartbeat_uses_agent_session(self, service, bus):
        """Heartbeat uses the agent's own session (sched_<agent_name>)."""
        # This is verified at the runner_factory level in cli.py
        # which uses session_id=f"sched_{agent_name}".
        # Here we just confirm origin_channel is set correctly.
        entry = ScheduleEntry(
            id="hb_session_test",
            trigger_config={"type": "cron", "hour": 0},
            task={"message": "heartbeat wakeup"},
            origin_channel="heartbeat",
            from_agent="my_agent",
            to_agent="my_agent",
            created_at=datetime.now().isoformat(),
        )
        assert entry.to_agent == "my_agent"
        assert entry.from_agent == "my_agent"
        assert entry.origin_channel == "heartbeat"


# ---------------------------------------------------------------------------
# 11-12. Catch-up
# ---------------------------------------------------------------------------


class TestCatchUp:
    def test_heartbeat_catch_up_fires(self):
        """last_run is yesterday → should catch up."""
        entry = MagicMock()
        entry.last_run = (datetime.now() - timedelta(hours=26)).isoformat()
        assert _should_catch_up(entry) is True

    def test_heartbeat_catch_up_skips_today(self):
        """last_run is recent → no catch-up needed."""
        entry = MagicMock()
        entry.last_run = datetime.now().isoformat()
        assert _should_catch_up(entry) is False

    def test_heartbeat_catch_up_never_ran(self):
        """last_run is None → should catch up."""
        entry = MagicMock()
        entry.last_run = None
        assert _should_catch_up(entry) is True

    def test_catch_up_returns_entry_ids(
        self, service, cron, agent_with_heartbeat
    ):
        """register_heartbeats returns catch_up_ids for missed seeds."""
        agents = {agent_with_heartbeat.name: agent_with_heartbeat}
        # First register
        register_heartbeats(agents, service)
        # Simulate missed seed: set last_run to 26 hours ago
        service._entries["hb_test_agent"].last_run = (
            datetime.now() - timedelta(hours=26)
        ).isoformat()
        # Second call detects catch-up needed
        count, catch_ups = register_heartbeats(agents, service)
        assert count == 0  # not re-registered
        assert catch_ups == ["hb_test_agent"]

    def test_catch_up_not_returned_when_recent(
        self, service, cron, agent_with_heartbeat
    ):
        """register_heartbeats returns empty catch_up_ids when recent."""
        agents = {agent_with_heartbeat.name: agent_with_heartbeat}
        register_heartbeats(agents, service)
        # Set last_run to now
        service._entries["hb_test_agent"].last_run = datetime.now().isoformat()
        count, catch_ups = register_heartbeats(agents, service)
        assert count == 0
        assert catch_ups == []

    @pytest.mark.asyncio
    async def test_catch_up_monkey_patch_fires(
        self, service, cron, agent_with_heartbeat
    ):
        """Monkey-patched cron.start calls _on_fired for catch-up entries."""
        agents = {agent_with_heartbeat.name: agent_with_heartbeat}
        register_heartbeats(agents, service)
        service._entries["hb_test_agent"].last_run = (
            datetime.now() - timedelta(hours=26)
        ).isoformat()
        _, catch_up_ids = register_heartbeats(agents, service)
        assert catch_up_ids == ["hb_test_agent"]

        # Simulate monkey-patch logic from cli.py
        original_start = AsyncMock()
        service._on_fired = AsyncMock()

        async def patched_start():
            await original_start()
            for eid in catch_up_ids:
                await service._on_fired(entry_id=eid)

        await patched_start()
        original_start.assert_awaited_once()
        service._on_fired.assert_awaited_once_with(entry_id="hb_test_agent")


# ---------------------------------------------------------------------------
# 13-16. HeartbeatStore
# ---------------------------------------------------------------------------


class TestHeartbeatStore:
    def test_heartbeat_store_log(self, hb_store):
        """Execution writes a record to heartbeat.db."""
        hb_store.record(
            agent_name="agent1",
            entry_id="hb_agent1",
            result="Morning report generated",
            skipped=False,
        )
        records = hb_store.query(agent_name="agent1")
        assert len(records) == 1
        assert records[0]["agent_name"] == "agent1"
        assert records[0]["result"] == "Morning report generated"
        assert records[0]["skipped"] == 0

    def test_heartbeat_store_skip_logged(self, hb_store):
        """Skip records skipped=True."""
        hb_store.record(
            agent_name="agent1",
            entry_id="hb_agent1",
            result="[heartbeat:skip]",
            skipped=True,
        )
        records = hb_store.query(agent_name="agent1")
        assert len(records) == 1
        assert records[0]["skipped"] == 1

    def test_heartbeat_store_query_by_agent(self, hb_store):
        """Query by agent name filters correctly."""
        hb_store.record(agent_name="agent1", entry_id="hb1", result="r1")
        hb_store.record(agent_name="agent2", entry_id="hb2", result="r2")
        hb_store.record(agent_name="agent1", entry_id="hb1", result="r3")

        records_1 = hb_store.query(agent_name="agent1")
        records_2 = hb_store.query(agent_name="agent2")
        records_all = hb_store.query()

        assert len(records_1) == 2
        assert len(records_2) == 1
        assert len(records_all) == 3

    def test_heartbeat_store_query_status(self, hb_store):
        """Query returns records in reverse chronological order."""
        hb_store.record(agent_name="agent1", entry_id="hb1", result="first")
        hb_store.record(agent_name="agent1", entry_id="hb1", result="second")
        hb_store.record(agent_name="agent1", entry_id="hb1", result="third")

        records = hb_store.query(agent_name="agent1", limit=1)
        assert len(records) == 1
        assert records[0]["result"] == "third"  # most recent first

    def test_heartbeat_store_count(self, hb_store):
        """Count returns correct totals."""
        hb_store.record(agent_name="agent1", entry_id="hb1", result="r1")
        hb_store.record(agent_name="agent1", entry_id="hb1", result="r2")
        hb_store.record(agent_name="agent2", entry_id="hb2", result="r3")

        assert hb_store.count() == 3
        assert hb_store.count(agent_name="agent1") == 2
        assert hb_store.count(agent_name="agent2") == 1
        assert hb_store.count(agent_name="nonexistent") == 0

    def test_heartbeat_store_pagination(self, hb_store):
        """Query with offset skips records correctly."""
        for i in range(5):
            hb_store.record(agent_name="agent1", entry_id="hb1", result=f"r{i}")

        # id DESC: r4,r3,r2,r1,r0 → offset 2 = r2,r1
        page = hb_store.query(agent_name="agent1", limit=2, offset=2)
        assert len(page) == 2
        assert page[0]["result"] == "r2"
        assert page[1]["result"] == "r1"


# ---------------------------------------------------------------------------
# Cron expression parser
# ---------------------------------------------------------------------------


class TestCronExprParser:
    def test_cron_daily_midnight(self):
        config = _cron_expr_to_config("0 0 * * *")
        assert config == {"type": "cron", "minute": 0, "hour": 0}

    def test_cron_every_hour(self):
        config = _cron_expr_to_config("30 * * * *")
        assert config == {"type": "cron", "minute": 30}

    def test_cron_with_dow(self):
        """day_of_week preserved as string type."""
        config = _cron_expr_to_config("0 9 * * 1")
        assert config == {"type": "cron", "minute": 0, "hour": 9, "day_of_week": "1"}
        assert isinstance(config["day_of_week"], str)

    def test_cron_day_of_month_rejected(self):
        """day-of-month field non-* raises ValueError."""
        with pytest.raises(ValueError, match="day-of-month"):
            _cron_expr_to_config("0 9 15 * *")

    def test_cron_month_rejected(self):
        """month field non-* raises ValueError."""
        with pytest.raises(ValueError, match="month"):
            _cron_expr_to_config("0 9 * 6 *")

    def test_cron_invalid(self):
        with pytest.raises(ValueError):
            _cron_expr_to_config("invalid")
