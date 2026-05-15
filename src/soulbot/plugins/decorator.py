"""@plugin decorator for convenient plugin class registration."""

from __future__ import annotations

from typing import Any

from .interface import PluginInterface

# Global registry of decorated plugin classes
_plugin_classes: dict[str, type[PluginInterface]] = {}


def plugin(
    name: str,
    version: str = "0.0.0",
    dependencies: list[str] | None = None,
    **meta: Any,
):
    """Class decorator: register a plugin class.

    Usage::

        @plugin("my_plugin", version="1.0.0", dependencies=["core"])
        class MyPlugin(PluginInterface):
            async def execute(self, params):
                return {"status": "ok"}

    Args:
        name: Unique plugin name.
        version: Semantic version string.
        dependencies: List of plugin names this plugin depends on.
        **meta: Additional metadata stored as ``_plugin_{key}`` attributes.
    """

    def decorator(cls: type) -> type:
        if not issubclass(cls, PluginInterface):
            raise TypeError(
                f"{cls.__name__} must inherit from PluginInterface"
            )
        cls.name = name
        cls.version = version
        cls.dependencies = dependencies or []
        for key, value in meta.items():
            setattr(cls, f"_plugin_{key}", value)
        _plugin_classes[name] = cls
        return cls

    return decorator


def get_plugin_classes() -> dict[str, type[PluginInterface]]:
    """Return all registered plugin classes."""
    return dict(_plugin_classes)


def clear_plugin_classes() -> None:
    """Clear the plugin class registry (for testing)."""
    _plugin_classes.clear()
