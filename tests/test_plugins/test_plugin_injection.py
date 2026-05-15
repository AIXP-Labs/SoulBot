"""Tests for dependency injection (bus/registry) and emit/call."""

import pytest

from soulbot.bus.events import BusEvent
from soulbot.bus.event_bus import EventBus
from soulbot.plugins.interface import PluginInterface
from soulbot.plugins.registry import PluginRegistry


class EmitterPlugin(PluginInterface):
    name = "emitter"
    version = "1.0.0"

    async def execute(self, params):
        count = await self.emit("custom.event", {"msg": params.get("msg", "")})
        return {"emitted": count}


class CallerPlugin(PluginInterface):
    name = "caller"
    version = "1.0.0"

    async def execute(self, params):
        result = await self.call("target", {"x": 42})
        return {"called_result": result}


class TargetPlugin(PluginInterface):
    name = "target"
    version = "1.0.0"

    async def execute(self, params):
        return {"received": params}


class TestBusInjection:
    async def test_bus_injected(self):
        bus = EventBus()
        registry = PluginRegistry(bus=bus)
        p = EmitterPlugin()
        registry.add_plugin(p)
        assert p._bus is bus

    async def test_emit_publishes_to_bus(self):
        bus = EventBus()
        received = []

        async def handler(event: BusEvent):
            received.append(event)

        bus.subscribe("custom.event", handler)

        registry = PluginRegistry(bus=bus)
        p = EmitterPlugin()
        registry.add_plugin(p)
        await registry.start_all()

        result = await registry.execute("emitter", {"msg": "hello"})
        assert result["emitted"] == 1
        assert received[0].data["msg"] == "hello"
        assert received[0].source == "emitter"

    async def test_emit_without_bus(self):
        registry = PluginRegistry(bus=None)
        p = EmitterPlugin()
        registry.add_plugin(p)
        await registry.start_all()

        result = await registry.execute("emitter", {"msg": "test"})
        assert result["emitted"] == 0


class TestRegistryInjection:
    async def test_registry_injected(self):
        registry = PluginRegistry()
        p = CallerPlugin()
        registry.add_plugin(p)
        assert p._registry is registry

    async def test_call_other_plugin(self):
        registry = PluginRegistry()
        registry.add_plugin(CallerPlugin())
        registry.add_plugin(TargetPlugin())
        await registry.start_all()

        result = await registry.execute("caller", {})
        assert result == {"called_result": {"received": {"x": 42}}}

    async def test_call_without_registry(self):
        p = CallerPlugin()
        with pytest.raises(RuntimeError, match="not registered"):
            await p.call("target", {})


class TestEventSubscription:
    async def test_auto_subscribe_event_types(self):
        bus = EventBus()
        received = []

        class ListenerPlugin(PluginInterface):
            name = "listener"

            def get_supported_event_types(self):
                return ["custom.event"]

            async def handle_event(self, event):
                received.append(event)

        registry = PluginRegistry(bus=bus)
        registry.add_plugin(ListenerPlugin())

        await bus.publish(BusEvent(type="custom.event", data={"x": 1}))
        assert len(received) == 1

    async def test_start_all_publishes_plugin_started(self):
        bus = EventBus()
        events = []

        async def handler(event: BusEvent):
            events.append(event)

        bus.subscribe("plugin.started", handler)

        registry = PluginRegistry(bus=bus)
        p = PluginInterface()
        p.name = "test_plugin"
        registry.add_plugin(p)
        await registry.start_all()

        assert len(events) == 1
        assert events[0].data["name"] == "test_plugin"
