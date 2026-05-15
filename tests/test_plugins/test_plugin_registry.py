"""Tests for PluginRegistry add/start/stop/execute."""

import pytest

from soulbot.plugins.interface import PluginInterface, PluginStatus
from soulbot.plugins.registry import PluginRegistry


class EchoPlugin(PluginInterface):
    name = "echo"
    version = "1.0.0"

    async def execute(self, params):
        return {"echo": params}


class UpperPlugin(PluginInterface):
    name = "upper"
    version = "1.0.0"

    async def execute(self, params):
        return {"result": params.get("text", "").upper()}


class TestPluginRegistry:
    async def test_add_plugin(self):
        registry = PluginRegistry()
        p = EchoPlugin()
        registry.add_plugin(p)
        assert "echo" in registry.plugins
        assert p._registry is registry

    async def test_get_plugin(self):
        registry = PluginRegistry()
        p = EchoPlugin()
        registry.add_plugin(p)
        assert registry.get_plugin("echo") is p
        assert registry.get_plugin("nonexistent") is None

    async def test_remove_plugin(self):
        registry = PluginRegistry()
        registry.add_plugin(EchoPlugin())
        assert await registry.remove_plugin("echo") is True
        assert await registry.remove_plugin("echo") is False
        assert "echo" not in registry.plugins

    async def test_start_all(self):
        registry = PluginRegistry()
        registry.add_plugin(EchoPlugin())
        registry.add_plugin(UpperPlugin())

        started = await registry.start_all()
        assert set(started) == {"echo", "upper"}

        for name in started:
            assert registry.get_plugin(name).is_running

    async def test_stop_all(self):
        registry = PluginRegistry()
        registry.add_plugin(EchoPlugin())
        registry.add_plugin(UpperPlugin())
        await registry.start_all()

        stopped = await registry.stop_all()
        assert set(stopped) == {"echo", "upper"}

        for name in stopped:
            assert registry.get_plugin(name).status == PluginStatus.STOPPED

    async def test_execute(self):
        registry = PluginRegistry()
        registry.add_plugin(EchoPlugin())
        await registry.start_all()

        result = await registry.execute("echo", {"msg": "hi"})
        assert result == {"echo": {"msg": "hi"}}

    async def test_execute_not_found(self):
        registry = PluginRegistry()
        with pytest.raises(KeyError, match="Plugin not found"):
            await registry.execute("missing", {})

    async def test_execute_not_running(self):
        registry = PluginRegistry()
        registry.add_plugin(EchoPlugin())
        # Not started
        with pytest.raises(RuntimeError, match="not running"):
            await registry.execute("echo", {})
