"""Tests for plugin startup failure rollback."""

import pytest

from soulbot.plugins.interface import PluginInterface, PluginStatus
from soulbot.plugins.registry import PluginRegistry


class TestStartupRollback:
    async def test_third_plugin_fails_rolls_back_first_two(self):
        stop_order = []

        class GoodPlugin(PluginInterface):
            async def on_stop(self):
                stop_order.append(self.name)

        class BadPlugin(PluginInterface):
            async def on_start(self):
                raise RuntimeError("startup failed")

        p1 = GoodPlugin()
        p1.name = "p1"
        p1.dependencies = []

        p2 = GoodPlugin()
        p2.name = "p2"
        p2.dependencies = ["p1"]

        p3 = BadPlugin()
        p3.name = "p3"
        p3.dependencies = ["p2"]

        registry = PluginRegistry()
        registry.add_plugin(p1)
        registry.add_plugin(p2)
        registry.add_plugin(p3)

        with pytest.raises(RuntimeError, match="startup failed"):
            await registry.start_all()

        # p1 and p2 should have been stopped (reversed order)
        assert stop_order == ["p2", "p1"]
        assert p1.status == PluginStatus.STOPPED
        assert p2.status == PluginStatus.STOPPED
        assert p3.status == PluginStatus.ERROR

    async def test_first_plugin_fails_no_rollback_needed(self):
        class BadPlugin(PluginInterface):
            name = "bad"
            async def on_start(self):
                raise RuntimeError("fail")

        registry = PluginRegistry()
        registry.add_plugin(BadPlugin())

        with pytest.raises(RuntimeError):
            await registry.start_all()

    async def test_rollback_handles_stop_errors(self):
        """Even if stop() fails during rollback, all plugins are attempted."""
        stop_attempts = []

        class HardStopPlugin(PluginInterface):
            async def on_stop(self):
                stop_attempts.append(self.name)
                raise RuntimeError("stop failed too")

        class BadPlugin(PluginInterface):
            async def on_start(self):
                raise RuntimeError("start failed")

        p1 = HardStopPlugin()
        p1.name = "p1"
        p1.dependencies = []

        p2 = HardStopPlugin()
        p2.name = "p2"
        p2.dependencies = ["p1"]

        p3 = BadPlugin()
        p3.name = "p3"
        p3.dependencies = ["p2"]

        registry = PluginRegistry()
        registry.add_plugin(p1)
        registry.add_plugin(p2)
        registry.add_plugin(p3)

        with pytest.raises(RuntimeError, match="start failed"):
            await registry.start_all()

        # Both should have been attempted despite errors
        assert set(stop_attempts) == {"p1", "p2"}
