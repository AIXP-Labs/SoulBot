"""Tests for CommandExecutor."""

import asyncio

import pytest

from soulbot.commands.parser import ParsedCommand
from soulbot.commands.executor import CommandExecutor


class SyncService:
    def add(self, a: int, b: int) -> int:
        return a + b

    def greet(self, name: str) -> str:
        return f"Hello, {name}!"

    def fail(self):
        raise ValueError("intentional error")


class AsyncService:
    async def fetch(self, url: str) -> dict:
        return {"url": url, "status": 200}

    async def process(self, data: list) -> int:
        return len(data)


def _cmd(service: str, action: str, **params) -> ParsedCommand:
    return ParsedCommand(service=service, action=action, params=params, raw="")


class TestServiceRegistration:
    def test_register_service(self):
        executor = CommandExecutor()
        executor.register_service("math", SyncService())
        assert "math" in executor.services

    def test_unregister_service(self):
        executor = CommandExecutor()
        executor.register_service("math", SyncService())
        assert executor.unregister_service("math") is True
        assert "math" not in executor.services

    def test_unregister_not_found(self):
        executor = CommandExecutor()
        assert executor.unregister_service("missing") is False


class TestSyncExecution:
    async def test_sync_method(self):
        executor = CommandExecutor()
        executor.register_service("math", SyncService())

        result = await executor.execute(_cmd("math", "add", a=3, b=4))
        assert result["success"] is True
        assert result["data"] == 7

    async def test_sync_string_method(self):
        executor = CommandExecutor()
        executor.register_service("util", SyncService())

        result = await executor.execute(_cmd("util", "greet", name="World"))
        assert result["success"] is True
        assert result["data"] == "Hello, World!"

    async def test_sync_method_error(self):
        executor = CommandExecutor()
        executor.register_service("util", SyncService())

        result = await executor.execute(_cmd("util", "fail"))
        assert result["success"] is False
        assert "intentional error" in result["error"]


class TestAsyncExecution:
    async def test_async_method(self):
        executor = CommandExecutor()
        executor.register_service("http", AsyncService())

        result = await executor.execute(_cmd("http", "fetch", url="https://example.com"))
        assert result["success"] is True
        assert result["data"]["status"] == 200

    async def test_async_list_method(self):
        executor = CommandExecutor()
        executor.register_service("data", AsyncService())

        result = await executor.execute(_cmd("data", "process", data=[1, 2, 3]))
        assert result["success"] is True
        assert result["data"] == 3


class TestErrorHandling:
    async def test_unknown_service(self):
        executor = CommandExecutor()
        result = await executor.execute(_cmd("missing", "action"))
        assert result["success"] is False
        assert "Unknown service" in result["error"]

    async def test_unknown_action(self):
        executor = CommandExecutor()
        executor.register_service("math", SyncService())
        result = await executor.execute(_cmd("math", "nonexistent"))
        assert result["success"] is False
        assert "Unknown action" in result["error"]


class TestExecuteAll:
    async def test_batch_execution(self):
        executor = CommandExecutor()
        executor.register_service("math", SyncService())

        commands = [
            _cmd("math", "add", a=1, b=2),
            _cmd("math", "add", a=3, b=4),
            _cmd("math", "greet", name="Test"),
        ]
        results = await executor.execute_all(commands)
        assert len(results) == 3
        assert results[0]["data"] == 3
        assert results[1]["data"] == 7
        assert results[2]["data"] == "Hello, Test!"

    async def test_batch_with_per_cmd_timeout(self):
        """timeout in params triggers per-command timeout."""

        class SlowService:
            async def slow(self, **kw):
                await asyncio.sleep(10)
                return "done"

        executor = CommandExecutor()
        executor.register_service("svc", SlowService())

        cmd = ParsedCommand(
            service="svc", action="slow",
            params={"timeout": 0.1}, raw="",
        )
        result = await executor.execute(cmd)
        assert result["success"] is False
        assert "Timed out" in result["error"]

    async def test_timeout_not_passed_to_service(self):
        """timeout is popped from params, not forwarded to service method."""

        class StrictService:
            def echo(self, msg: str) -> str:
                return msg

        executor = CommandExecutor()
        executor.register_service("svc", StrictService())

        cmd = ParsedCommand(
            service="svc", action="echo",
            params={"msg": "hi", "timeout": 5}, raw="",
        )
        result = await executor.execute(cmd)
        assert result["success"] is True
        assert result["data"] == "hi"

    async def test_batch_with_failure(self):
        executor = CommandExecutor()
        executor.register_service("math", SyncService())

        commands = [
            _cmd("math", "add", a=1, b=2),
            _cmd("missing", "action"),
            _cmd("math", "add", a=5, b=5),
        ]
        results = await executor.execute_all(commands)
        assert results[0]["success"] is True
        assert results[1]["success"] is False
        assert results[2]["success"] is True
