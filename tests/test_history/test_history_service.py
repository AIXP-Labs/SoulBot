"""Tests for ChatHistoryService — InMemory + SQLite implementations (Doc 22).

Covers:
- ChatMessage model
- InMemoryChatHistoryService full CRUD
- SqliteChatHistoryService full CRUD
- Cross-agent isolation
- Keyword search
- Session-scoped queries
"""

import time

import pytest

from soulbot.history import ChatMessage, InMemoryChatHistoryService

aiosqlite = pytest.importorskip("aiosqlite")

from soulbot.history import SqliteChatHistoryService


# ---------------------------------------------------------------------------
# TestChatMessage
# ---------------------------------------------------------------------------


class TestChatMessage:
    def test_defaults(self):
        m = ChatMessage()
        assert m.id == 0
        assert m.user_id == "default"
        assert m.agent == ""
        assert m.role == ""
        assert m.content == ""
        assert m.created_at == 0

    def test_fields(self):
        m = ChatMessage(
            id=1, user_id="u1", agent="hello", session_id="s1",
            role="user", content="hi", created_at=1000,
        )
        assert m.agent == "hello"
        assert m.created_at == 1000

    def test_timestamp_type(self):
        m = ChatMessage(created_at=int(time.time()))
        assert isinstance(m.created_at, int)


# ---------------------------------------------------------------------------
# TestInMemoryChatHistoryService
# ---------------------------------------------------------------------------


class TestInMemoryHistoryService:
    async def test_add_and_count(self):
        svc = InMemoryChatHistoryService()
        await svc.add_message("u1", "agent_a", "s1", "user", "hello")
        assert await svc.count("u1") == 1

    async def test_get_session_history(self):
        svc = InMemoryChatHistoryService()
        await svc.add_message("u1", "agent_a", "s1", "user", "hello")
        await svc.add_message("u1", "agent_a", "s1", "assistant", "hi!")
        msgs = await svc.get_session_history("s1")
        assert len(msgs) == 2
        assert msgs[0].role == "user"
        assert msgs[1].role == "assistant"

    async def test_get_agent_history_newest_first(self):
        svc = InMemoryChatHistoryService()
        await svc.add_message("u1", "agent_a", "s1", "user", "first")
        await svc.add_message("u1", "agent_a", "s1", "user", "second")
        msgs = await svc.get_agent_history("u1", "agent_a")
        assert msgs[0].content == "second"  # newest first
        assert msgs[1].content == "first"

    async def test_agent_isolation(self):
        svc = InMemoryChatHistoryService()
        await svc.add_message("u1", "agent_a", "s1", "user", "from a")
        await svc.add_message("u1", "agent_b", "s2", "user", "from b")
        assert await svc.count("u1", "agent_a") == 1
        assert await svc.count("u1", "agent_b") == 1
        assert await svc.count("u1") == 2

    async def test_search_by_keyword(self):
        svc = InMemoryChatHistoryService()
        await svc.add_message("u1", "agent_a", "s1", "user", "I love pizza")
        await svc.add_message("u1", "agent_a", "s1", "assistant", "Pizza is great!")
        await svc.add_message("u1", "agent_a", "s1", "user", "What about sushi?")
        results = await svc.search("u1", "agent_a", "pizza")
        assert len(results) == 2
        assert all("pizza" in r.content.lower() for r in results)

    async def test_search_case_insensitive(self):
        svc = InMemoryChatHistoryService()
        await svc.add_message("u1", "agent_a", "s1", "user", "HELLO World")
        results = await svc.search("u1", "agent_a", "hello")
        assert len(results) == 1

    async def test_search_no_results(self):
        svc = InMemoryChatHistoryService()
        await svc.add_message("u1", "agent_a", "s1", "user", "hello")
        results = await svc.search("u1", "agent_a", "nonexistent")
        assert results == []

    async def test_delete_agent_history(self):
        svc = InMemoryChatHistoryService()
        await svc.add_message("u1", "agent_a", "s1", "user", "msg1")
        await svc.add_message("u1", "agent_a", "s1", "assistant", "reply1")
        await svc.add_message("u1", "agent_b", "s2", "user", "msg2")
        deleted = await svc.delete_agent_history("u1", "agent_a")
        assert deleted == 2
        assert await svc.count("u1", "agent_a") == 0
        assert await svc.count("u1", "agent_b") == 1

    async def test_delete_session_history(self):
        svc = InMemoryChatHistoryService()
        await svc.add_message("u1", "agent_a", "s1", "user", "msg1")
        await svc.add_message("u1", "agent_a", "s2", "user", "msg2")
        deleted = await svc.delete_session_history("s1")
        assert deleted == 1
        assert await svc.count("u1") == 1

    async def test_limit(self):
        svc = InMemoryChatHistoryService()
        for i in range(10):
            await svc.add_message("u1", "agent_a", "s1", "user", f"msg {i}")
        msgs = await svc.get_agent_history("u1", "agent_a", limit=3)
        assert len(msgs) == 3

    async def test_session_history_chronological(self):
        svc = InMemoryChatHistoryService()
        await svc.add_message("u1", "agent_a", "s1", "user", "first")
        await svc.add_message("u1", "agent_a", "s1", "assistant", "second")
        msgs = await svc.get_session_history("s1")
        assert msgs[0].content == "first"
        assert msgs[1].content == "second"

    async def test_count_with_agent_filter(self):
        svc = InMemoryChatHistoryService()
        await svc.add_message("u1", "a", "s1", "user", "1")
        await svc.add_message("u1", "b", "s2", "user", "2")
        await svc.add_message("u1", "a", "s1", "user", "3")
        assert await svc.count("u1", "a") == 2
        assert await svc.count("u1", "b") == 1
        assert await svc.count("u1") == 3


# ---------------------------------------------------------------------------
# TestSqliteChatHistoryService
# ---------------------------------------------------------------------------


class TestSqliteHistoryService:
    async def test_add_and_count(self, tmp_path):
        db = str(tmp_path / "history.db")
        svc = SqliteChatHistoryService(db)
        await svc.add_message("u1", "agent_a", "s1", "user", "hello")
        assert await svc.count("u1") == 1

    async def test_get_session_history(self, tmp_path):
        db = str(tmp_path / "history.db")
        svc = SqliteChatHistoryService(db)
        await svc.add_message("u1", "agent_a", "s1", "user", "hello")
        await svc.add_message("u1", "agent_a", "s1", "assistant", "hi!")
        msgs = await svc.get_session_history("s1")
        assert len(msgs) == 2
        assert msgs[0].role == "user"
        assert msgs[1].role == "assistant"
        assert msgs[0].id > 0  # autoincrement ID

    async def test_get_agent_history_newest_first(self, tmp_path):
        db = str(tmp_path / "history.db")
        svc = SqliteChatHistoryService(db)
        await svc.add_message("u1", "agent_a", "s1", "user", "first")
        await svc.add_message("u1", "agent_a", "s1", "user", "second")
        msgs = await svc.get_agent_history("u1", "agent_a")
        assert msgs[0].content == "second"
        assert msgs[1].content == "first"

    async def test_agent_isolation(self, tmp_path):
        db = str(tmp_path / "history.db")
        svc = SqliteChatHistoryService(db)
        await svc.add_message("u1", "agent_a", "s1", "user", "from a")
        await svc.add_message("u1", "agent_b", "s2", "user", "from b")
        assert await svc.count("u1", "agent_a") == 1
        assert await svc.count("u1", "agent_b") == 1

    async def test_search(self, tmp_path):
        db = str(tmp_path / "history.db")
        svc = SqliteChatHistoryService(db)
        await svc.add_message("u1", "agent_a", "s1", "user", "I love pizza")
        await svc.add_message("u1", "agent_a", "s1", "assistant", "Pizza is great!")
        await svc.add_message("u1", "agent_a", "s1", "user", "What about sushi?")
        results = await svc.search("u1", "agent_a", "pizza")
        assert len(results) == 2

    async def test_search_no_results(self, tmp_path):
        db = str(tmp_path / "history.db")
        svc = SqliteChatHistoryService(db)
        await svc.add_message("u1", "agent_a", "s1", "user", "hello")
        results = await svc.search("u1", "agent_a", "nonexistent")
        assert results == []

    async def test_delete_agent_history(self, tmp_path):
        db = str(tmp_path / "history.db")
        svc = SqliteChatHistoryService(db)
        await svc.add_message("u1", "agent_a", "s1", "user", "msg1")
        await svc.add_message("u1", "agent_a", "s1", "assistant", "reply1")
        await svc.add_message("u1", "agent_b", "s2", "user", "msg2")
        deleted = await svc.delete_agent_history("u1", "agent_a")
        assert deleted == 2
        assert await svc.count("u1", "agent_a") == 0
        assert await svc.count("u1", "agent_b") == 1

    async def test_delete_session_history(self, tmp_path):
        db = str(tmp_path / "history.db")
        svc = SqliteChatHistoryService(db)
        await svc.add_message("u1", "agent_a", "s1", "user", "msg1")
        await svc.add_message("u1", "agent_a", "s2", "user", "msg2")
        deleted = await svc.delete_session_history("s1")
        assert deleted == 1
        assert await svc.count("u1") == 1

    async def test_limit(self, tmp_path):
        db = str(tmp_path / "history.db")
        svc = SqliteChatHistoryService(db)
        for i in range(10):
            await svc.add_message("u1", "agent_a", "s1", "user", f"msg {i}")
        msgs = await svc.get_agent_history("u1", "agent_a", limit=3)
        assert len(msgs) == 3

    async def test_created_at_populated(self, tmp_path):
        db = str(tmp_path / "history.db")
        svc = SqliteChatHistoryService(db)
        before = int(time.time())
        await svc.add_message("u1", "agent_a", "s1", "user", "hello")
        after = int(time.time())
        msgs = await svc.get_session_history("s1")
        assert before <= msgs[0].created_at <= after

    async def test_lazy_init_creates_table(self, tmp_path):
        db = str(tmp_path / "history.db")
        svc = SqliteChatHistoryService(db)
        # First call should create the table
        assert await svc.count("u1") == 0
        # Second call should reuse
        assert await svc.count("u1") == 0

    async def test_count_with_agent_filter(self, tmp_path):
        db = str(tmp_path / "history.db")
        svc = SqliteChatHistoryService(db)
        await svc.add_message("u1", "a", "s1", "user", "1")
        await svc.add_message("u1", "b", "s2", "user", "2")
        await svc.add_message("u1", "a", "s1", "user", "3")
        assert await svc.count("u1", "a") == 2
        assert await svc.count("u1", "b") == 1
        assert await svc.count("u1") == 3
