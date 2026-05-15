"""Tests for search_history tool (Doc 22 Step 8)."""

import time

import pytest

from soulbot.history import InMemoryChatHistoryService
from soulbot.tools.history_tool import create_history_tool


@pytest.fixture
def history_svc():
    return InMemoryChatHistoryService()


class TestSearchHistoryTool:
    async def test_search_by_keyword(self, history_svc):
        await history_svc.add_message("default", "agent_a", "s1", "user", "I love pizza")
        await history_svc.add_message("default", "agent_a", "s1", "assistant", "Pizza is great!")
        await history_svc.add_message("default", "agent_a", "s1", "user", "What about sushi?")

        fn = create_history_tool(history_svc, default_agent="agent_a")
        result = await fn(keyword="pizza")
        assert "pizza" in result.lower()
        assert "sushi" not in result.lower()

    async def test_recent_no_keyword(self, history_svc):
        await history_svc.add_message("default", "agent_a", "s1", "user", "hello")
        await history_svc.add_message("default", "agent_a", "s1", "assistant", "hi there")

        fn = create_history_tool(history_svc, default_agent="agent_a")
        result = await fn()
        assert "hello" in result
        assert "hi there" in result

    async def test_empty_results(self, history_svc):
        fn = create_history_tool(history_svc, default_agent="agent_a")
        result = await fn(keyword="nonexistent")
        assert result == "No history found."

    async def test_no_agent_specified(self, history_svc):
        fn = create_history_tool(history_svc)
        result = await fn()
        assert result == "No agent specified."

    async def test_format_output(self, history_svc):
        await history_svc.add_message("default", "agent_a", "s1", "user", "test message")
        await history_svc.add_message("default", "agent_a", "s1", "assistant", "test reply")

        fn = create_history_tool(history_svc, default_agent="agent_a")
        result = await fn()
        # Should contain role labels
        assert "User:" in result
        assert "AI:" in result

    async def test_default_agent_override(self, history_svc):
        await history_svc.add_message("default", "agent_b", "s1", "user", "msg for b")

        fn = create_history_tool(history_svc, default_agent="agent_a")
        # Explicitly search agent_b
        result = await fn(agent="agent_b")
        assert "msg for b" in result

    async def test_content_truncated(self, history_svc):
        long_content = "A" * 300
        await history_svc.add_message("default", "agent_a", "s1", "user", long_content)

        fn = create_history_tool(history_svc, default_agent="agent_a")
        result = await fn()
        assert "..." in result
        # Should be truncated to 200 chars + "..."
        assert "A" * 201 not in result

    async def test_limit_respected(self, history_svc):
        for i in range(10):
            await history_svc.add_message("default", "agent_a", "s1", "user", f"msg {i}")

        fn = create_history_tool(history_svc, default_agent="agent_a")
        result = await fn(limit=3)
        lines = [l for l in result.strip().split("\n") if l.strip()]
        assert len(lines) == 3
