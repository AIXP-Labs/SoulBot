"""Plugins — lifecycle-managed extensible components."""

from .interface import PluginInterface, PluginStatus
from .decorator import plugin, get_plugin_classes, clear_plugin_classes
from .registry import PluginRegistry
from .loader import PluginLoader

__all__ = [
    "PluginInterface",
    "PluginStatus",
    "plugin",
    "get_plugin_classes",
    "clear_plugin_classes",
    "PluginRegistry",
    "PluginLoader",
]
