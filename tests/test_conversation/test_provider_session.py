"""Tests for ProviderSessionStore — session_id mapping, clear, hash privacy."""

import pytest

from soulbot.conversation.store import ProviderSessionStore


class TestProviderSession:
    async def test_set_and_get(self):
        store = ProviderSessionStore()
        await store.set_session_id("user1", "claude", "sess-abc")
        result = await store.get_session_id("user1", "claude")
        assert result == "sess-abc"

    async def test_get_miss(self):
        store = ProviderSessionStore()
        assert await store.get_session_id("user1", "claude") is None

    async def test_different_providers(self):
        store = ProviderSessionStore()
        await store.set_session_id("user1", "claude", "c-1")
        await store.set_session_id("user1", "gemini", "g-1")
        assert await store.get_session_id("user1", "claude") == "c-1"
        assert await store.get_session_id("user1", "gemini") == "g-1"

    async def test_different_users(self):
        store = ProviderSessionStore()
        await store.set_session_id("alice", "claude", "alice-sess")
        await store.set_session_id("bob", "claude", "bob-sess")
        assert await store.get_session_id("alice", "claude") == "alice-sess"
        assert await store.get_session_id("bob", "claude") == "bob-sess"

    async def test_overwrite(self):
        store = ProviderSessionStore()
        await store.set_session_id("user1", "claude", "old")
        await store.set_session_id("user1", "claude", "new")
        assert await store.get_session_id("user1", "claude") == "new"


class TestProviderClear:
    async def test_clear_single_provider(self):
        store = ProviderSessionStore()
        await store.set_session_id("user1", "claude", "c-1")
        await store.set_session_id("user1", "gemini", "g-1")
        await store.clear("user1", provider="claude")
        assert await store.get_session_id("user1", "claude") is None
        assert await store.get_session_id("user1", "gemini") == "g-1"

    async def test_clear_all_providers(self):
        store = ProviderSessionStore()
        await store.set_session_id("user1", "claude", "c-1")
        await store.set_session_id("user1", "gemini", "g-1")
        await store.set_session_id("user1", "opencode", "o-1")
        await store.clear("user1")
        for p in ProviderSessionStore.PROVIDERS:
            assert await store.get_session_id("user1", p) is None


class TestProviderPrivacy:
    async def test_numeric_id_hashed(self):
        store = ProviderSessionStore()
        key = store._key("claude", "123456")
        assert "123456" not in key
        assert "provider_session:claude:" in key

    async def test_string_id_not_hashed(self):
        store = ProviderSessionStore()
        key = store._key("claude", "alice")
        assert key == "provider_session:claude:alice"
