"""Tests for FileCache — JSON persistence, TTL cleanup."""

import json
import time
from pathlib import Path

import pytest

from soulbot.conversation.cache import FileCache


class TestFileBasicOps:
    async def test_set_and_get(self, tmp_path: Path):
        cache = FileCache(tmp_path / "cache.json")
        await cache.set("k", "v")
        assert await cache.get("k") == "v"

    async def test_get_miss(self, tmp_path: Path):
        cache = FileCache(tmp_path / "cache.json")
        assert await cache.get("missing") is None

    async def test_delete(self, tmp_path: Path):
        cache = FileCache(tmp_path / "cache.json")
        await cache.set("k", "v")
        assert await cache.delete("k") is True
        assert await cache.get("k") is None

    async def test_delete_missing(self, tmp_path: Path):
        cache = FileCache(tmp_path / "cache.json")
        assert await cache.delete("nope") is False

    async def test_exists(self, tmp_path: Path):
        cache = FileCache(tmp_path / "cache.json")
        await cache.set("k", "v")
        assert await cache.exists("k") is True
        assert await cache.exists("nope") is False


class TestFilePersistence:
    async def test_persists_to_disk(self, tmp_path: Path):
        path = tmp_path / "cache.json"
        cache = FileCache(path)
        await cache.set("k", "hello")
        # Verify file exists and contains data
        raw = json.loads(path.read_text(encoding="utf-8"))
        assert "k" in raw
        assert raw["k"]["value"] == "hello"

    async def test_reload_from_disk(self, tmp_path: Path):
        path = tmp_path / "cache.json"
        cache1 = FileCache(path)
        await cache1.set("k", [1, 2, 3])

        # New instance loads from the same file
        cache2 = FileCache(path)
        assert await cache2.get("k") == [1, 2, 3]

    async def test_creates_parent_dirs(self, tmp_path: Path):
        path = tmp_path / "sub" / "dir" / "cache.json"
        cache = FileCache(path)
        await cache.set("k", "v")
        assert path.exists()

    async def test_handles_corrupt_file(self, tmp_path: Path):
        path = tmp_path / "cache.json"
        path.write_text("not json!", encoding="utf-8")
        cache = FileCache(path)
        assert await cache.get("anything") is None


class TestFileTTL:
    async def test_ttl_expiry(self, tmp_path: Path):
        cache = FileCache(tmp_path / "cache.json")
        await cache.set("k", "v", ttl=1)
        assert await cache.get("k") == "v"
        time.sleep(1.1)
        assert await cache.get("k") is None

    async def test_expired_pruned_on_load(self, tmp_path: Path):
        path = tmp_path / "cache.json"
        # Write a manually expired entry
        data = {"old": {"value": "stale", "expire_at": time.time() - 100}}
        path.write_text(json.dumps(data), encoding="utf-8")
        cache = FileCache(path)
        assert await cache.get("old") is None

    async def test_exists_expired(self, tmp_path: Path):
        cache = FileCache(tmp_path / "cache.json")
        await cache.set("k", "v", ttl=1)
        time.sleep(1.1)
        assert await cache.exists("k") is False
