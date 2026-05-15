"""Tests for AisopPlugin runtime."""

import json
import pytest

from soulbot.aisop.runtime import AisopPlugin
from soulbot.plugins.registry import PluginRegistry


def _write_aisop(directory, name, data):
    path = directory / f"{name}.aisop.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


class TestAisopPlugin:
    async def test_initialize(self, tmp_path):
        _write_aisop(tmp_path, "main", {"name": "main", "description": "Main"})

        plugin = AisopPlugin()
        await plugin.initialize({"aisop_dir": str(tmp_path)})
        assert plugin._loader is not None
        assert "main" in plugin._prompt_cache

    async def test_get_system_prompt(self, tmp_path):
        _write_aisop(tmp_path, "main", {
            "name": "main",
            "workflow": "graph TD\n  A-->B",
        })

        plugin = AisopPlugin()
        await plugin.initialize({"aisop_dir": str(tmp_path)})
        await plugin.start()

        result = await plugin.execute({"action": "get_system_prompt"})
        assert "system_prompt" in result
        assert "main" in result["system_prompt"]
        assert result["aisop_name"] == "main"

    async def test_get_named_prompt(self, tmp_path):
        _write_aisop(tmp_path, "support", {
            "name": "support",
            "description": "Support flow",
        })

        plugin = AisopPlugin()
        await plugin.initialize({"aisop_dir": str(tmp_path)})
        await plugin.start()

        result = await plugin.execute({"action": "get_system_prompt", "aisop": "support"})
        assert result["aisop_name"] == "support"
        assert "support" in result["system_prompt"].lower()

    async def test_list_action(self, tmp_path):
        _write_aisop(tmp_path, "a", {"name": "a"})
        _write_aisop(tmp_path, "b", {"name": "b"})

        plugin = AisopPlugin()
        await plugin.initialize({"aisop_dir": str(tmp_path)})
        await plugin.start()

        result = await plugin.execute({"action": "list"})
        assert result["count"] == 2
        assert set(result["aisops"]) == {"a", "b"}

    async def test_reload_action(self, tmp_path):
        _write_aisop(tmp_path, "main", {"name": "main", "version": "1.0"})

        plugin = AisopPlugin()
        await plugin.initialize({"aisop_dir": str(tmp_path)})
        await plugin.start()

        # Modify file
        _write_aisop(tmp_path, "main", {"name": "main", "version": "2.0"})

        result = await plugin.execute({"action": "reload"})
        assert result["reloaded"] is True
        assert result["count"] == 1

    async def test_unknown_action(self, tmp_path):
        plugin = AisopPlugin()
        await plugin.initialize({"aisop_dir": str(tmp_path)})
        await plugin.start()

        with pytest.raises(ValueError, match="Unknown AISOP action"):
            await plugin.execute({"action": "unknown"})

    async def test_supported_actions(self):
        plugin = AisopPlugin()
        actions = plugin.get_supported_actions()
        assert "get_system_prompt" in actions
        assert "list" in actions
        assert "reload" in actions

    async def test_plugin_in_registry(self, tmp_path):
        _write_aisop(tmp_path, "main", {"name": "main"})

        registry = PluginRegistry()
        plugin = AisopPlugin()
        registry.add_plugin(plugin)

        await plugin.initialize({"aisop_dir": str(tmp_path)})
        await registry.start_all()

        result = await registry.execute("aisop_engine", {"action": "list"})
        assert result["count"] == 1

    async def test_prompt_cache(self, tmp_path):
        _write_aisop(tmp_path, "main", {"name": "main"})

        plugin = AisopPlugin()
        await plugin.initialize({"aisop_dir": str(tmp_path)})
        await plugin.start()

        # First call caches
        r1 = await plugin.execute({"action": "get_system_prompt"})
        r2 = await plugin.execute({"action": "get_system_prompt"})
        assert r1["system_prompt"] == r2["system_prompt"]

    async def test_empty_dir(self, tmp_path):
        plugin = AisopPlugin()
        await plugin.initialize({"aisop_dir": str(tmp_path)})
        await plugin.start()

        result = await plugin.execute({"action": "list"})
        assert result["count"] == 0
