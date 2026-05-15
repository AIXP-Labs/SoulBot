"""Tests for @plugin decorator."""

import pytest

from soulbot.plugins.interface import PluginInterface
from soulbot.plugins.decorator import (
    plugin,
    get_plugin_classes,
    clear_plugin_classes,
)


@pytest.fixture(autouse=True)
def reset_registry():
    clear_plugin_classes()
    yield
    clear_plugin_classes()


class TestPluginDecorator:
    def test_basic_decoration(self):
        @plugin("my_plugin", version="2.0.0")
        class MyPlugin(PluginInterface):
            pass

        assert MyPlugin.name == "my_plugin"
        assert MyPlugin.version == "2.0.0"
        assert MyPlugin.dependencies == []

    def test_with_dependencies(self):
        @plugin("dep_plugin", dependencies=["core", "auth"])
        class DepPlugin(PluginInterface):
            pass

        assert DepPlugin.dependencies == ["core", "auth"]

    def test_with_metadata(self):
        @plugin("meta_plugin", author="test", priority=10)
        class MetaPlugin(PluginInterface):
            pass

        assert MetaPlugin._plugin_author == "test"
        assert MetaPlugin._plugin_priority == 10

    def test_registered_in_global_dict(self):
        @plugin("global_plugin")
        class GlobalPlugin(PluginInterface):
            pass

        classes = get_plugin_classes()
        assert "global_plugin" in classes
        assert classes["global_plugin"] is GlobalPlugin

    def test_non_plugin_class_raises(self):
        with pytest.raises(TypeError, match="must inherit"):
            @plugin("bad")
            class NotAPlugin:
                pass

    def test_multiple_plugins(self):
        @plugin("p1")
        class P1(PluginInterface):
            pass

        @plugin("p2")
        class P2(PluginInterface):
            pass

        classes = get_plugin_classes()
        assert len(classes) == 2
        assert "p1" in classes
        assert "p2" in classes

    def test_clear_plugin_classes(self):
        @plugin("temp")
        class TempPlugin(PluginInterface):
            pass

        assert len(get_plugin_classes()) == 1
        clear_plugin_classes()
        assert len(get_plugin_classes()) == 0

    def test_instance_has_correct_name(self):
        @plugin("named")
        class NamedPlugin(PluginInterface):
            pass

        instance = NamedPlugin()
        assert instance.name == "named"
