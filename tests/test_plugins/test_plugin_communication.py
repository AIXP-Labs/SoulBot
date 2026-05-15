"""Tests for cross-plugin communication and circular call detection."""

import pytest

from soulbot.plugins.interface import PluginInterface
from soulbot.plugins.registry import PluginRegistry


class PluginA(PluginInterface):
    name = "plugin_a"

    async def execute(self, params):
        if params.get("call_b"):
            return await self.call("plugin_b", {"from": "a"})
        return {"from": "a", "params": params}


class PluginB(PluginInterface):
    name = "plugin_b"

    async def execute(self, params):
        if params.get("call_a"):
            return await self.call("plugin_a", {"from": "b"})
        return {"from": "b", "params": params}


class TestCrossPluginCall:
    async def test_a_calls_b(self):
        registry = PluginRegistry()
        registry.add_plugin(PluginA())
        registry.add_plugin(PluginB())
        await registry.start_all()

        result = await registry.execute("plugin_a", {"call_b": True})
        assert result == {"from": "b", "params": {"from": "a"}}

    async def test_b_calls_a(self):
        registry = PluginRegistry()
        registry.add_plugin(PluginA())
        registry.add_plugin(PluginB())
        await registry.start_all()

        result = await registry.execute("plugin_b", {"call_a": True})
        assert result == {"from": "a", "params": {"from": "b"}}


class TestCircularCallDetection:
    async def test_circular_call_detected(self):
        """A calls B which calls A → circular detection."""

        class CircularA(PluginInterface):
            name = "circ_a"

            async def execute(self, params):
                return await self.call("circ_b", {"depth": 1})

        class CircularB(PluginInterface):
            name = "circ_b"

            async def execute(self, params):
                return await self.call("circ_a", {"depth": 2})

        registry = PluginRegistry()
        registry.add_plugin(CircularA())
        registry.add_plugin(CircularB())
        await registry.start_all()

        with pytest.raises(RuntimeError, match="Circular plugin call"):
            await registry.execute("circ_a", {})

    async def test_non_circular_same_plugin_called_separately(self):
        """Two separate calls to the same plugin are fine."""
        call_count = 0

        class CountPlugin(PluginInterface):
            name = "counter"

            async def execute(self, params):
                nonlocal call_count
                call_count += 1
                return {"count": call_count}

        registry = PluginRegistry()
        registry.add_plugin(CountPlugin())
        await registry.start_all()

        r1 = await registry.execute("counter", {})
        r2 = await registry.execute("counter", {})
        assert r1["count"] == 1
        assert r2["count"] == 2
