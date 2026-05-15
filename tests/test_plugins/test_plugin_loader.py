"""Tests for PluginLoader filesystem loading."""

import pytest
from pathlib import Path

from soulbot.plugins.interface import PluginInterface
from soulbot.plugins.loader import PluginLoader


class TestPluginLoader:
    def test_scan_empty_dir(self, tmp_path):
        loader = PluginLoader([tmp_path])
        found = loader.scan()
        assert found == {}

    def test_scan_finds_plugin(self, tmp_path):
        plugin_file = tmp_path / "my_plugin.py"
        plugin_file.write_text(
            "from soulbot.plugins.interface import PluginInterface\n"
            "\n"
            "class MyPlugin(PluginInterface):\n"
            "    name = 'my_plugin'\n"
            "    version = '1.0.0'\n"
        )

        loader = PluginLoader([tmp_path])
        found = loader.scan()
        assert "my_plugin" in found
        assert issubclass(found["my_plugin"], PluginInterface)

    def test_scan_skips_underscored_files(self, tmp_path):
        (tmp_path / "__init__.py").write_text("")
        (tmp_path / "_private.py").write_text(
            "from soulbot.plugins.interface import PluginInterface\n"
            "class P(PluginInterface): name='private'\n"
        )

        loader = PluginLoader([tmp_path])
        found = loader.scan()
        assert len(found) == 0

    def test_load_from_file(self, tmp_path):
        plugin_file = tmp_path / "hello_plugin.py"
        plugin_file.write_text(
            "from soulbot.plugins.interface import PluginInterface\n"
            "\n"
            "class HelloPlugin(PluginInterface):\n"
            "    name = 'hello'\n"
        )

        loader = PluginLoader()
        cls = loader.load_from_file(plugin_file)
        assert cls.name == "hello"
        assert issubclass(cls, PluginInterface)

    def test_load_no_plugin_class(self, tmp_path):
        no_plugin_file = tmp_path / "empty.py"
        no_plugin_file.write_text("x = 42\n")

        loader = PluginLoader()
        with pytest.raises(ImportError, match="No PluginInterface subclass"):
            loader.load_from_file(no_plugin_file)

    def test_scan_nonexistent_dir(self, tmp_path):
        loader = PluginLoader([tmp_path / "nonexistent"])
        found = loader.scan()
        assert found == {}

    def test_scan_multiple_dirs(self, tmp_path):
        dir_a = tmp_path / "a"
        dir_a.mkdir()
        (dir_a / "pa.py").write_text(
            "from soulbot.plugins.interface import PluginInterface\n"
            "class PA(PluginInterface): name='pa'\n"
        )

        dir_b = tmp_path / "b"
        dir_b.mkdir()
        (dir_b / "pb.py").write_text(
            "from soulbot.plugins.interface import PluginInterface\n"
            "class PB(PluginInterface): name='pb'\n"
        )

        loader = PluginLoader([dir_a, dir_b])
        found = loader.scan()
        assert "pa" in found
        assert "pb" in found
