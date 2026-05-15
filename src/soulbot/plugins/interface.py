"""PluginInterface — base class for all plugins."""

from __future__ import annotations

import asyncio
import logging
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..bus.event_bus import EventBus
    from ..bus.events import BusEvent

logger = logging.getLogger(__name__)


class PluginStatus(Enum):
    """Plugin lifecycle status."""

    CREATED = "created"
    INITIALIZED = "initialized"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class PluginInterface:
    """Base class for all plugins.

    Plugins provide modular, lifecycle-managed components that can:
    - Subscribe to EventBus events
    - Communicate with other plugins via ``call()``
    - Publish events via ``emit()``
    - Run named background tasks
    """

    name: str = "base_plugin"
    version: str = "0.0.0"
    dependencies: list[str] = []

    def __init__(self) -> None:
        self._status: PluginStatus = PluginStatus.CREATED
        self._registry: Any = None  # PluginRegistry (avoid circular import)
        self._bus: EventBus | None = None
        self._background_tasks: dict[str, asyncio.Task] = {}
        self._call_stack: set[str] = set()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def status(self) -> PluginStatus:
        return self._status

    @property
    def is_running(self) -> bool:
        return self._status == PluginStatus.RUNNING

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self, config: dict[str, Any] | None = None) -> None:
        """Initialize with configuration. Called before ``start()``."""
        self._status = PluginStatus.INITIALIZED

    async def start(self) -> bool:
        """Start the plugin. Calls ``on_start()`` for subclass logic."""
        if self._status == PluginStatus.CREATED:
            await self.initialize()
        try:
            await self.on_start()
            self._status = PluginStatus.RUNNING
            return True
        except Exception:
            self._status = PluginStatus.ERROR
            raise

    async def on_start(self) -> None:
        """Override in subclass: custom start logic."""
        pass

    async def stop(self) -> None:
        """Stop the plugin. Cancels background tasks, calls ``on_stop()``."""
        for task in self._background_tasks.values():
            task.cancel()
        self._background_tasks.clear()
        await self.on_stop()
        self._status = PluginStatus.STOPPED

    async def on_stop(self) -> None:
        """Override in subclass: custom stop/cleanup logic."""
        pass

    async def execute(self, params: dict[str, Any]) -> Any:
        """Execute a plugin action. Must be overridden by subclass."""
        raise NotImplementedError(f"{self.name} does not implement execute()")

    async def cleanup(self) -> None:
        """Final cleanup when plugin is unloaded."""
        pass

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------

    def get_supported_actions(self) -> list[str]:
        """Return list of action names this plugin supports."""
        return []

    def get_supported_event_types(self) -> list[str]:
        """Return list of event types this plugin subscribes to."""
        return []

    async def handle_event(self, event: BusEvent) -> None:
        """Handle an EventBus event. Override in subclass."""
        pass

    # ------------------------------------------------------------------
    # Cross-plugin communication
    # ------------------------------------------------------------------

    async def call(self, plugin_name: str, params: dict[str, Any]) -> Any:
        """Call another plugin's ``execute()`` via the registry.

        Uses a registry-level call stack to detect circular calls.
        """
        if self._registry is None:
            raise RuntimeError("Plugin not registered")
        call_stack: set[str] = self._registry._call_stack
        if plugin_name in call_stack:
            raise RuntimeError(
                f"Circular plugin call: {self.name} -> {plugin_name}"
            )
        call_stack.add(plugin_name)
        try:
            return await self._registry.execute(plugin_name, params)
        finally:
            call_stack.discard(plugin_name)

    async def emit(self, event_type: str, data: dict[str, Any] | None = None) -> int:
        """Publish an event via the EventBus."""
        if self._bus is None:
            return 0
        from ..bus.events import BusEvent

        return await self._bus.publish(
            BusEvent(type=event_type, data=data or {}, source=self.name)
        )

    # ------------------------------------------------------------------
    # Background tasks
    # ------------------------------------------------------------------

    def start_background_task(self, name: str, coro) -> None:
        """Start a named background task. Replaces existing task with same name."""
        if name in self._background_tasks:
            self._background_tasks[name].cancel()
        self._background_tasks[name] = asyncio.create_task(coro)

    def stop_background_task(self, name: str) -> bool:
        """Stop a named background task. Returns True if found."""
        task = self._background_tasks.pop(name, None)
        if task is not None:
            task.cancel()
            return True
        return False
