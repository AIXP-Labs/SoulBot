"""Tests for MemoryCache — get/set/delete, TTL, LRU eviction."""

import time

import pytest

from soulbot.conversation.cache import MemoryCache


class TestBasicOps:
    async def test_set_and_get(self):
        cache = MemoryCache()
        await cache.set("k", "v")
        assert await cache.get("k") == "v"

    async def test_get_miss(self):
        cache = MemoryCache()
        assert await cache.get("missing") is None

    async def test_overwrite(self):
        cache = MemoryCache()
        await cache.set("k", "old")
        await cache.set("k", "new")
        assert await cache.get("k") == "new"

    async def test_delete_existing(self):
        cache = MemoryCache()
        await cache.set("k", "v")
        assert await cache.delete("k") is True
        assert await cache.get("k") is None

    async def test_delete_missing(self):
        cache = MemoryCache()
        assert await cache.delete("nope") is False

    async def test_exists_true(self):
        cache = MemoryCache()
        await cache.set("k", "v")
        assert await cache.exists("k") is True

    async def test_exists_false(self):
        cache = MemoryCache()
        assert await cache.exists("nope") is False

    async def test_complex_values(self):
        cache = MemoryCache()
        data = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
        await cache.set("conv", data)
        assert await cache.get("conv") == data


class TestTTL:
    async def test_ttl_expiry(self):
        cache = MemoryCache()
        await cache.set("k", "v", ttl=1)
        assert await cache.get("k") == "v"
        time.sleep(1.1)
        assert await cache.get("k") is None

    async def test_no_ttl_persists(self):
        cache = MemoryCache()
        await cache.set("k", "v", ttl=0)
        assert await cache.get("k") == "v"

    async def test_exists_expired(self):
        cache = MemoryCache()
        await cache.set("k", "v", ttl=1)
        time.sleep(1.1)
        assert await cache.exists("k") is False


class TestLRU:
    async def test_eviction_on_max_size(self):
        cache = MemoryCache(max_size=3)
        await cache.set("a", 1)
        await cache.set("b", 2)
        await cache.set("c", 3)
        await cache.set("d", 4)  # should evict "a"
        assert await cache.get("a") is None
        assert await cache.get("b") == 2

    async def test_access_refreshes_lru(self):
        cache = MemoryCache(max_size=3)
        await cache.set("a", 1)
        await cache.set("b", 2)
        await cache.set("c", 3)
        await cache.get("a")    # refresh "a"
        await cache.set("d", 4)  # should evict "b" (oldest untouched)
        assert await cache.get("a") == 1
        assert await cache.get("b") is None
