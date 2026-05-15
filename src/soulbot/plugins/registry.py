"""PluginRegistry — manages plugin lifecycle with topological ordering."""

from __future__ import annotations

import logging
from collections import deque
from typing import TYPE_CHECKING, Any

from .interface import PluginInterface

if TYPE_CHECKING:
    from ..bus.event_bus import EventBus

logger = logging.getLogger(__name__)


class PluginRegistry:
    """Registry for managing plugins with dependency-ordered startup.

    Features:
    - Kahn topological sort for startup order
    - Dependency injection (EventBus)
    - Startup failure rollback
    - Cross-plugin execution
    """

    def __init__(self, bus: EventBus | None = None) -> None:
        self._plugins: dict[str, PluginInterface] = {}
        self._dependencies: dict[str, list[str]] = {}
        self._bus = bus
        self._call_stack: set[str] = set()  # shared circular-call detection

    @property
    def plugins(self) -> dict[str, PluginInterface]:
        """Return registered plugins."""
        return dict(self._plugins)

    def add_plugin(self, plugin_instance: PluginInterface) -> None:
        """Register a plugin instance. Injects registry and bus references."""
        plugin_instance._registry = self
        plugin_instance._bus = self._bus
        self._plugins[plugin_instance.name] = plugin_instance
        self._dependencies[plugin_instance.name] = list(plugin_instance.dependencies)

        # Auto-subscribe to declared event types
        if self._bus and plugin_instance.get_supported_event_types():
            for event_type in plugin_instance.get_supported_event_types():
                self._bus.subscribe(event_type, plugin_instance.handle_event)

    async def remove_plugin(self, name: str) -> bool:
        """Remove a plugin, stopping it and unsubscribing from EventBus.

        Returns True if found and removed.
        """
        plugin = self._plugins.pop(name, None)
        if plugin is None:
            return False
        self._dependencies.pop(name, None)

        # Stop plugin if still running
        if plugin.is_running:
            try:
                await plugin.stop()
            except Exception as exc:
                logger.warning("Error stopping plugin %s during removal: %s", name, exc)

        # Unsubscribe from EventBus
        if self._bus:
            for event_type in plugin.get_supported_event_types():
                self._bus.unsubscribe(event_type, plugin.handle_event)

        # Final cleanup
        try:
            await plugin.cleanup()
        except Exception as exc:
            logger.warning("Error cleaning up plugin %s: %s", name, exc)

        return True

    def get_plugin(self, name: str) -> PluginInterface | None:
        """Get a plugin by name."""
        return self._plugins.get(name)

    async def start_all(self) -> list[str]:
        """Start all plugins in topological order.

        If a plugin fails to start, all previously started plugins
        are stopped in reverse order (rollback).

        Returns:
            List of successfully started plugin names.

        Raises:
            Exception: Re-raises the original startup exception after rollback.
        """
        order = self._calculate_startup_order()
        started: list[str] = []

        for name in order:
            plugin = self._plugins[name]
            try:
                await plugin.start()
                started.append(name)
                if self._bus:
                    from ..bus.events import BusEvent

                    await self._bus.publish(BusEvent(
                        type="plugin.started",
                        data={"name": name, "version": plugin.version},
                        source="registry",
                    ))
            except Exception as exc:
                logger.error("Plugin %s failed to start: %s", name, exc)
                if self._bus:
                    from ..bus.events import BusEvent

                    await self._bus.publish(BusEvent(
                        type="plugin.error",
                        data={"name": name, "error": str(exc)},
                        source="registry",
                    ))
                # Rollback in reverse
                for rollback_name in reversed(started):
                    try:
                        await self._plugins[rollback_name].stop()
                    except Exception:
                        pass
                raise

        return started

    async def stop_all(self) -> list[str]:
        """Stop all running plugins in reverse topological order.

        Returns:
            List of successfully stopped plugin names.
        """
        order = self._calculate_startup_order()
        stopped: list[str] = []

        for name in reversed(order):
            plugin = self._plugins[name]
            if plugin.is_running:
                try:
                    await plugin.stop()
                    stopped.append(name)
                    if self._bus:
                        from ..bus.events import BusEvent

                        await self._bus.publish(BusEvent(
                            type="plugin.stopped",
                            data={"name": name},
                            source="registry",
                        ))
                except Exception as exc:
                    logger.error("Plugin %s stop error: %s", name, exc)

        return stopped

    async def execute(self, plugin_name: str, params: dict[str, Any]) -> Any:
        """Execute a plugin's ``execute()`` method.

        Args:
            plugin_name: The target plugin name.
            params: Parameters passed to the plugin.

        Raises:
            KeyError: Plugin not found.
            RuntimeError: Plugin not running.
        """
        plugin = self._plugins.get(plugin_name)
        if plugin is None:
            raise KeyError(f"Plugin not found: {plugin_name}")
        if not plugin.is_running:
            raise RuntimeError(f"Plugin {plugin_name} is not running")
        return await plugin.execute(params)

    def _calculate_startup_order(self) -> list[str]:
        """Kahn's algorithm for topological sort.

        Returns:
            Ordered list of plugin names.

        Raises:
            ValueError: Circular or missing dependency.
        """
        names = list(self._plugins.keys())
        in_degree: dict[str, int] = {n: 0 for n in names}
        adj: dict[str, list[str]] = {n: [] for n in names}

        for name, deps in self._dependencies.items():
            for dep in deps:
                if dep not in self._plugins:
                    raise ValueError(
                        f"Plugin '{name}' depends on unknown plugin '{dep}'"
                    )
                adj[dep].append(name)
                in_degree[name] += 1

        queue = deque(n for n in names if in_degree[n] == 0)
        result: list[str] = []

        while queue:
            node = queue.popleft()
            result.append(node)
            for neighbor in adj[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(result) != len(names):
            missing = set(names) - set(result)
            raise ValueError(f"Circular dependency detected: {missing}")

        return result
