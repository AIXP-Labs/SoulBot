"""Tests for AisopLoader."""

import json
import pytest

from soulbot.aisop.loader import AisopLoader


def _write_aisop(directory, name, data):
    """Helper to write a .aisop.json file."""
    path = directory / f"{name}.aisop.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


class TestAisopLoader:
    def test_load_all(self, tmp_path):
        _write_aisop(tmp_path, "main", {"name": "main", "description": "Main"})
        _write_aisop(tmp_path, "support", {"name": "support", "description": "Support"})

        loader = AisopLoader(tmp_path)
        blueprints = loader.load_all()
        assert len(blueprints) == 2
        assert "main" in blueprints
        assert "support" in blueprints

    def test_load_single(self, tmp_path):
        _write_aisop(tmp_path, "hello", {"name": "hello", "workflow": "graph TD\n  A-->B"})

        loader = AisopLoader(tmp_path)
        bp = loader.load("hello")
        assert bp.name == "hello"
        assert "A-->B" in bp.workflow

    def test_load_caches(self, tmp_path):
        _write_aisop(tmp_path, "cached", {"name": "cached"})

        loader = AisopLoader(tmp_path)
        bp1 = loader.load("cached")
        bp2 = loader.load("cached")
        assert bp1 is bp2  # same object from cache

    def test_load_not_found(self, tmp_path):
        loader = AisopLoader(tmp_path)
        with pytest.raises(FileNotFoundError, match="not found"):
            loader.load("nonexistent")

    def test_load_all_empty_dir(self, tmp_path):
        loader = AisopLoader(tmp_path)
        result = loader.load_all()
        assert result == {}

    def test_load_all_nonexistent_dir(self, tmp_path):
        loader = AisopLoader(tmp_path / "no_such_dir")
        result = loader.load_all()
        assert result == {}

    def test_reload_all(self, tmp_path):
        _write_aisop(tmp_path, "main", {"name": "main", "version": "1.0"})

        loader = AisopLoader(tmp_path)
        loader.load_all()
        assert loader.blueprints["main"].version == "1.0"

        # Modify file
        _write_aisop(tmp_path, "main", {"name": "main", "version": "2.0"})

        count = loader.reload_all()
        assert count == 1
        assert loader.blueprints["main"].version == "2.0"

    def test_bom_file(self, tmp_path):
        """UTF-8 BOM should be handled gracefully."""
        path = tmp_path / "bom.aisop.json"
        content = json.dumps({"name": "bom_test"})
        path.write_bytes(b"\xef\xbb\xbf" + content.encode("utf-8"))

        loader = AisopLoader(tmp_path)
        blueprints = loader.load_all()
        assert "bom_test" in blueprints

    def test_blueprints_property(self, tmp_path):
        _write_aisop(tmp_path, "test", {"name": "test"})
        loader = AisopLoader(tmp_path)
        loader.load_all()

        # Returns a copy
        bp = loader.blueprints
        assert "test" in bp
        bp.clear()
        assert "test" in loader.blueprints  # original unaffected

    def test_invalid_json_skipped(self, tmp_path):
        (tmp_path / "bad.aisop.json").write_text("not json", encoding="utf-8")
        _write_aisop(tmp_path, "good", {"name": "good"})

        loader = AisopLoader(tmp_path)
        blueprints = loader.load_all()
        assert len(blueprints) == 1
        assert "good" in blueprints
