"""Tests for command security — nested scheduling prevention."""

import pytest

from soulbot.commands.parser import ParsedCommand
from soulbot.commands.executor import CommandExecutor


class ScheduleService:
    def add(self, cron: str, task: str) -> dict:
        return {"scheduled": True, "cron": cron, "task": task}

    def remove(self, job_id: str) -> dict:
        return {"removed": job_id}


class OtherService:
    def run(self) -> str:
        return "ok"


def _cmd(service: str, action: str, **params) -> ParsedCommand:
    return ParsedCommand(service=service, action=action, params=params, raw="")


class TestNestedSchedulingBlock:
    async def test_schedule_from_scheduled_context_blocked(self):
        executor = CommandExecutor()
        executor.register_service("schedule", ScheduleService())

        cmd = _cmd("schedule", "add", cron="0 9 * * *", task="test")
        context = {"type": "scheduled"}
        results = await executor.execute_all([cmd], context)

        assert len(results) == 1
        assert results[0]["success"] is False
        assert "Nested scheduling blocked" in results[0]["error"]

    async def test_schedule_from_normal_context_allowed(self):
        executor = CommandExecutor()
        executor.register_service("schedule", ScheduleService())

        cmd = _cmd("schedule", "add", cron="0 9 * * *", task="test")
        context = {"type": "user"}
        results = await executor.execute_all([cmd], context)

        assert len(results) == 1
        assert results[0]["success"] is True

    async def test_non_schedule_from_scheduled_context_allowed(self):
        executor = CommandExecutor()
        executor.register_service("other", OtherService())

        cmd = _cmd("other", "run")
        context = {"type": "scheduled"}
        results = await executor.execute_all([cmd], context)

        assert len(results) == 1
        assert results[0]["success"] is True

    async def test_schedule_without_context_allowed(self):
        executor = CommandExecutor()
        executor.register_service("schedule", ScheduleService())

        cmd = _cmd("schedule", "add", cron="* * * * *", task="test")
        results = await executor.execute_all([cmd])

        assert results[0]["success"] is True

    async def test_mixed_commands_partial_block(self):
        executor = CommandExecutor()
        executor.register_service("schedule", ScheduleService())
        executor.register_service("other", OtherService())

        commands = [
            _cmd("other", "run"),
            _cmd("schedule", "add", cron="0 9 * * *", task="bad"),
            _cmd("other", "run"),
        ]
        context = {"type": "scheduled"}
        results = await executor.execute_all(commands, context)

        assert results[0]["success"] is True
        assert results[1]["success"] is False  # blocked
        assert results[2]["success"] is True


class TestHeartbeatChainPreservation:
    """Heartbeat origin_channel + to_agent auto-injection (Doc 13 §3.2)."""

    async def test_heartbeat_auto_injects_origin_channel(self):
        """schedule.add from heartbeat context auto-injects origin_channel."""
        captured = {}

        class CaptureScheduleService:
            def add(self, **kwargs):
                captured.update(kwargs)
                return {"id": "test"}

        executor = CommandExecutor()
        executor.register_service("schedule", CaptureScheduleService())

        # LLM omits origin_channel in CMD params
        cmd = _cmd("schedule", "add", cron="0 9 * * *", task="wakeup")
        context = {
            "type": "scheduled",
            "origin_channel": "heartbeat",
            "to_agent": "my_agent",
            "allow_nested_schedule": True,
        }
        results = await executor.execute_all([cmd], context)

        assert results[0]["success"] is True
        assert captured["origin_channel"] == "heartbeat"
        assert captured["to_agent"] == "my_agent"

    async def test_heartbeat_does_not_overwrite_explicit_origin(self):
        """If LLM explicitly sets origin_channel, it is preserved."""
        captured = {}

        class CaptureScheduleService:
            def add(self, **kwargs):
                captured.update(kwargs)
                return {"id": "test"}

        executor = CommandExecutor()
        executor.register_service("schedule", CaptureScheduleService())

        cmd = _cmd(
            "schedule", "add",
            cron="0 9 * * *", task="wakeup",
            origin_channel="heartbeat", to_agent="explicit_agent",
        )
        context = {
            "type": "scheduled",
            "origin_channel": "heartbeat",
            "to_agent": "context_agent",
            "allow_nested_schedule": True,
        }
        results = await executor.execute_all([cmd], context)

        assert results[0]["success"] is True
        # Explicit params preserved (setdefault doesn't overwrite)
        assert captured["origin_channel"] == "heartbeat"
        assert captured["to_agent"] == "explicit_agent"

    async def test_non_heartbeat_no_injection(self):
        """Non-heartbeat context doesn't inject origin_channel."""
        captured = {}

        class CaptureScheduleService:
            def add(self, **kwargs):
                captured.update(kwargs)
                return {"id": "test"}

        executor = CommandExecutor()
        executor.register_service("schedule", CaptureScheduleService())

        cmd = _cmd("schedule", "add", cron="0 9 * * *", task="normal")
        context = {"type": "user"}
        results = await executor.execute_all([cmd], context)

        assert results[0]["success"] is True
        assert "origin_channel" not in captured
