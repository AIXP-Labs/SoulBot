"""Tests for plugin lifecycle state transitions."""

import pytest

from soulbot.plugins.interface import PluginInterface, PluginStatus


class SimplePlugin(PluginInterface):
    name = "simple"
    version = "1.0.0"

    def __init__(self):
        super().__init__()
        self.started = False
        self.stopped = False

    async def on_start(self):
        self.started = True

    async def on_stop(self):
        self.stopped = True

    async def execute(self, params):
        return {"echo": params}


class TestPluginLifecycle:
    def test_initial_status(self):
        p = SimplePlugin()
        assert p.status == PluginStatus.CREATED
        assert p.is_running is False

    async def test_initialize(self):
        p = SimplePlugin()
        await p.initialize({"key": "value"})
        assert p.status == PluginStatus.INITIALIZED

    async def test_start_from_created(self):
        """start() auto-calls initialize() if CREATED."""
        p = SimplePlugin()
        result = await p.start()
        assert result is True
        assert p.status == PluginStatus.RUNNING
        assert p.is_running is True
        assert p.started is True

    async def test_start_from_initialized(self):
        p = SimplePlugin()
        await p.initialize()
        assert p.status == PluginStatus.INITIALIZED
        await p.start()
        assert p.status == PluginStatus.RUNNING

    async def test_stop(self):
        p = SimplePlugin()
        await p.start()
        await p.stop()
        assert p.status == PluginStatus.STOPPED
        assert p.is_running is False
        assert p.stopped is True

    async def test_execute(self):
        p = SimplePlugin()
        await p.start()
        result = await p.execute({"msg": "hello"})
        assert result == {"echo": {"msg": "hello"}}

    async def test_execute_not_implemented(self):
        p = PluginInterface()
        with pytest.raises(NotImplementedError):
            await p.execute({})

    async def test_start_failure_sets_error(self):
        class FailPlugin(PluginInterface):
            name = "fail"

            async def on_start(self):
                raise RuntimeError("boom")

        p = FailPlugin()
        with pytest.raises(RuntimeError, match="boom"):
            await p.start()
        assert p.status == PluginStatus.ERROR

    async def test_cleanup(self):
        p = SimplePlugin()
        await p.start()
        await p.cleanup()  # should not raise

    def test_supported_actions_default(self):
        p = PluginInterface()
        assert p.get_supported_actions() == []

    def test_supported_event_types_default(self):
        p = PluginInterface()
        assert p.get_supported_event_types() == []
