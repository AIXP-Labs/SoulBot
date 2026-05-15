"""PluginLoader — discover and load plugin classes from the filesystem."""

from __future__ import annotations

import importlib.util
import inspect
import logging
from pathlib import Path

from .interface import PluginInterface

logger = logging.getLogger(__name__)


class PluginLoader:
    """Load PluginInterface subclasses from Python files.

    Usage::

        loader = PluginLoader([Path("./plugins")])
        classes = loader.scan()
        for name, cls in classes.items():
            registry.add_plugin(cls())
    """

    def __init__(self, plugin_dirs: list[Path] | None = None) -> None:
        self._dirs = plugin_dirs or []

    def scan(self) -> dict[str, type[PluginInterface]]:
        """Scan all directories for plugin classes.

        Returns:
            Mapping of plugin name → plugin class.
        """
        found: dict[str, type[PluginInterface]] = {}
        for directory in self._dirs:
            if not directory.is_dir():
                logger.warning("Plugin directory not found: %s", directory)
                continue
            for py_file in sorted(directory.glob("*.py")):
                if py_file.name.startswith("_"):
                    continue
                try:
                    cls = self.load_from_file(py_file)
                    found[cls.name] = cls
                except (ImportError, AttributeError) as exc:
                    logger.warning("Skipping %s: %s", py_file, exc)
        return found

    def load_from_file(self, path: Path) -> type[PluginInterface]:
        """Load a single plugin class from a Python file.

        Args:
            path: Path to the ``.py`` file.

        Returns:
            The PluginInterface subclass found in the module.

        Raises:
            ImportError: No PluginInterface subclass found.
        """
        module = self._import_module(path)
        return self._find_plugin_class(module)

    @staticmethod
    def _import_module(path: Path):
        """Import a Python file as a module."""
        module_name = f"_plugin_{path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load module from {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    @staticmethod
    def _find_plugin_class(module) -> type[PluginInterface]:
        """Find the first PluginInterface subclass in a module."""
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, PluginInterface) and obj is not PluginInterface:
                return obj
        raise ImportError(
            f"No PluginInterface subclass found in {module.__name__}"
        )
