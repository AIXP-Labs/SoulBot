"""Tests for Telegram Bridge connector."""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from soulbot.connect.telegram import (
    TelegramBridge,
    _chunk_markdown,
    _display_width,
    _edit_html,
    _escape_html,
    _extract_tables,
    _pad_to_width,
    _render_table_cards,
    _reply_html,
    _strip_md,
    md_to_html,
)


# ---------------------------------------------------------------------------
# md_to_html tests
# ---------------------------------------------------------------------------


class TestEscapeHtml:
    def test_escape_ampersand(self):
        assert _escape_html("A & B") == "A &amp; B"

    def test_escape_lt_gt(self):
        assert _escape_html("<div>") == "&lt;div&gt;"

    def test_no_escape_needed(self):
        assert _escape_html("hello") == "hello"


class TestMdToHtml:
    def test_bold(self):
        assert "<b>bold</b>" in md_to_html("**bold**")

    def test_italic(self):
        assert "<i>italic</i>" in md_to_html("*italic*")

    def test_strikethrough(self):
        assert "<s>strike</s>" in md_to_html("~~strike~~")

    def test_link(self):
        result = md_to_html("[click](https://example.com)")
        assert '<a href="https://example.com">click</a>' in result

    def test_heading(self):
        result = md_to_html("# Title")
        assert "<b>Title</b>" in result

    def test_hr(self):
        result = md_to_html("---")
        assert "───" in result

    def test_inline_code(self):
        result = md_to_html("Use `print()` here")
        assert "<code>print()</code>" in result

    def test_code_block(self):
        result = md_to_html("```python\nprint('hi')\n```")
        assert "<pre><code>" in result
        assert "print(&#x27;hi&#x27;)" in result or "print('hi')" in result

    def test_html_escaped_outside_code(self):
        result = md_to_html("a < b & c > d")
        assert "&lt;" in result
        assert "&amp;" in result
        assert "&gt;" in result

    def test_code_block_not_double_escaped(self):
        result = md_to_html("```\na < b\n```")
        assert "&lt;" in result
        assert "&amp;lt;" not in result

    def test_bold_and_italic_combined(self):
        result = md_to_html("**bold** and *italic*")
        assert "<b>bold</b>" in result
        assert "<i>italic</i>" in result

    def test_plain_text(self):
        assert md_to_html("hello world") == "hello world"

    def test_empty_string(self):
        assert md_to_html("") == ""

    def test_multiple_inline_codes(self):
        result = md_to_html("`foo` and `bar`")
        assert "<code>foo</code>" in result
        assert "<code>bar</code>" in result

    def test_table_renders_as_cards(self):
        md = "| H1 | H2 |\n|---|---|\n| A | B |"
        result = md_to_html(md)
        # Card mode: no <pre> for table, uses ◆ and <b>
        assert "◆" in result
        assert "<b>A</b>" in result
        assert "H2: B" in result

    def test_table_multi_row(self):
        md = "| Name | Score |\n|---|---|\n| QQQ | 5.5/10 |\n| SPY | 7.0/10 |"
        result = md_to_html(md)
        assert "◆ <b>QQQ</b>" in result
        assert "◆ <b>SPY</b>" in result
        assert "Score: 5.5/10" in result
        assert "Score: 7.0/10" in result

    def test_table_with_bold_cells(self):
        md = "| **Bold** | Normal |\n|---|---|\n| A | B |"
        result = md_to_html(md)
        # Card mode: first col header "Bold" stripped, data "A" is title
        assert "◆ <b>A</b>" in result
        assert "Normal: B" in result
        assert "**" not in result

    def test_table_not_in_code_block(self):
        md = "```\n| H1 | H2 |\n|---|---|\n| A | B |\n```"
        result = md_to_html(md)
        # Table inside code block should NOT be converted to cards
        assert "◆" not in result
        assert "<pre>" in result  # only the code block's <pre>

    def test_unordered_list(self):
        md = "- Item 1\n- Item 2\n- Item 3"
        result = md_to_html(md)
        assert "• Item 1" in result
        assert "• Item 2" in result
        assert "• Item 3" in result

    def test_nested_list_indentation(self):
        md = "- Parent\n  - Child"
        result = md_to_html(md)
        assert "• Parent" in result
        assert "  • Child" in result

    def test_blockquote(self):
        md = "> This is a quote"
        result = md_to_html(md)
        assert "<blockquote>" in result
        assert "This is a quote" in result
        assert "</blockquote>" in result

    def test_blockquote_multiline_merged(self):
        md = "> Line 1\n> Line 2\n> Line 3"
        result = md_to_html(md)
        # Should be merged into a single blockquote
        assert result.count("<blockquote>") == 1
        assert result.count("</blockquote>") == 1
        assert "Line 1" in result
        assert "Line 3" in result

    def test_mixed_content(self):
        md = (
            "# Title\n\n"
            "**Bold** text\n\n"
            "| A | B |\n|---|---|\n| 1 | 2 |\n\n"
            "- Item 1\n- Item 2\n\n"
            "> Quote here"
        )
        result = md_to_html(md)
        assert "<b>Title</b>" in result
        assert "<b>Bold</b>" in result
        assert "◆" in result  # table rendered as cards
        assert "• Item 1" in result
        assert "<blockquote>" in result


# ---------------------------------------------------------------------------
# Table helper tests
# ---------------------------------------------------------------------------


class TestStripMd:
    def test_strip_bold(self):
        assert _strip_md("**bold**") == "bold"

    def test_strip_italic(self):
        assert _strip_md("*italic*") == "italic"

    def test_strip_strike(self):
        assert _strip_md("~~strike~~") == "strike"

    def test_strip_code(self):
        assert _strip_md("`code`") == "code"

    def test_strip_mixed(self):
        assert _strip_md("**bold** and `code`") == "bold and code"

    def test_no_formatting(self):
        assert _strip_md("plain text") == "plain text"


class TestDisplayWidth:
    def test_ascii(self):
        assert _display_width("hello") == 5

    def test_cjk(self):
        assert _display_width("你好") == 4  # 2 chars × 2 width

    def test_mixed(self):
        assert _display_width("hi你好") == 6  # 2 + 4

    def test_empty(self):
        assert _display_width("") == 0


class TestPadToWidth:
    def test_pad_ascii(self):
        result = _pad_to_width("hi", 5)
        assert result == "hi   "
        assert len(result) == 5

    def test_pad_cjk(self):
        result = _pad_to_width("你好", 6)
        assert result == "你好  "  # 4 display width + 2 spaces

    def test_no_pad_needed(self):
        assert _pad_to_width("hello", 5) == "hello"

    def test_over_width(self):
        assert _pad_to_width("hello", 3) == "hello"  # no truncation


class TestRenderTableCards:
    def test_simple_table(self):
        lines = ["| A | B |", "|---|---|", "| 1 | 2 |"]
        result = _render_table_cards(lines)
        # Card mode: first col as title, rest as key: value
        assert "◆" in result
        assert "<b>1</b>" in result
        assert "B: 2" in result

    def test_multi_row_table(self):
        lines = [
            "| Name | Score | Signal |",
            "|---|---|---|",
            "| Value | 4/10 | High |",
            "| Growth | 7/10 | Good |",
        ]
        result = _render_table_cards(lines)
        assert "◆ <b>Value</b>" in result
        assert "Score: 4/10" in result
        assert "Signal: High" in result
        assert "◆ <b>Growth</b>" in result
        assert "Score: 7/10" in result
        # Cards separated by newline
        assert result.count("◆") == 2

    def test_empty_table(self):
        result = _render_table_cards([])
        assert result == ""

    def test_header_only_table(self):
        lines = ["| A | B | C |", "|---|---|---|"]
        result = _render_table_cards(lines)
        # Header-only → bold joined text
        assert "<b>" in result
        assert "A" in result and "B" in result

    def test_cjk_content(self):
        lines = ["| 因子 | 评分 | 信号 |", "|---|---|---|", "| Value | 4/10 | 偏高 |"]
        result = _render_table_cards(lines)
        assert "◆ <b>Value</b>" in result
        assert "评分: 4/10" in result
        assert "信号: 偏高" in result

    def test_html_escaping(self):
        lines = ["| Name | Desc |", "|---|---|", "| A<B | x&y |"]
        result = _render_table_cards(lines)
        assert "A&lt;B" in result
        assert "x&amp;y" in result


class TestExtractTables:
    def test_extract_single_table(self):
        text = "Before\n| H1 | H2 |\n|---|---|\n| A | B |\nAfter"
        blocks: list[str] = []
        result = _extract_tables(text, blocks)
        assert len(blocks) == 1
        assert "\x00TABLE0\x00" in result
        assert "Before" in result
        assert "After" in result

    def test_no_table(self):
        text = "Just some text\nWith pipes | in it"
        blocks: list[str] = []
        result = _extract_tables(text, blocks)
        assert len(blocks) == 0
        assert result == text

    def test_multiple_tables(self):
        text = "| A | B |\n|---|---|\n| 1 | 2 |\n\n| X | Y |\n|---|---|\n| 3 | 4 |"
        blocks: list[str] = []
        result = _extract_tables(text, blocks)
        assert len(blocks) == 2


class TestChunkMarkdown:
    def test_short_text_single_chunk(self):
        text = "Hello world"
        assert _chunk_markdown(text) == [text]

    def test_split_at_paragraph_boundary(self):
        para1 = "A" * 2000
        para2 = "B" * 2000
        text = para1 + "\n\n" + para2
        chunks = _chunk_markdown(text, limit=2500)
        assert len(chunks) == 2
        assert chunks[0].strip() == para1
        assert chunks[1].strip() == para2

    def test_split_at_newline_when_no_paragraph_break(self):
        line1 = "A" * 2000
        line2 = "B" * 2000
        text = line1 + "\n" + line2
        chunks = _chunk_markdown(text, limit=2500)
        assert len(chunks) == 2

    def test_preserves_all_content(self):
        sections = [f"Section {i}: " + "x" * 500 for i in range(10)]
        text = "\n\n".join(sections)
        chunks = _chunk_markdown(text, limit=1500)
        reassembled = "\n\n".join(c.strip() for c in chunks)
        # All sections should be present
        for s in sections:
            assert s in reassembled

    def test_very_long_single_paragraph(self):
        text = "A" * 8000
        chunks = _chunk_markdown(text, limit=3500)
        # Should still produce chunks (hard-break fallback)
        assert len(chunks) >= 2
        assert all(len(c) <= 3500 for c in chunks)

    def test_table_not_split(self):
        table = "| H1 | H2 |\n|---|---|\n| A | B |\n| C | D |"
        before = "Intro paragraph."
        after = "Conclusion paragraph."
        text = before + "\n\n" + table + "\n\n" + after
        chunks = _chunk_markdown(text, limit=3500)
        # Table should be in a single chunk (it's short)
        found = False
        for chunk in chunks:
            if "| H1 |" in chunk and "| C | D |" in chunk:
                found = True
        assert found, "Table should not be split across chunks"

    def test_returns_at_least_one_chunk(self):
        assert len(_chunk_markdown("")) == 0 or len(_chunk_markdown("x")) == 1


# ---------------------------------------------------------------------------
# _edit_html / _reply_html tests
# ---------------------------------------------------------------------------


class TestEditHtml:
    @pytest.mark.asyncio
    async def test_edit_html_success(self):
        bot = AsyncMock()
        bot.edit_message_text = AsyncMock()
        result = await _edit_html(bot, 123, 456, "**hello**")
        assert result is True
        bot.edit_message_text.assert_called_once()
        call_kwargs = bot.edit_message_text.call_args[1]
        assert call_kwargs["chat_id"] == 123
        assert call_kwargs["message_id"] == 456
        assert "<b>hello</b>" in call_kwargs["text"]

    @pytest.mark.asyncio
    async def test_edit_html_not_modified(self):
        bot = AsyncMock()
        bot.edit_message_text = AsyncMock(
            side_effect=Exception("Bad Request: message is not modified")
        )
        result = await _edit_html(bot, 123, 456, "same text")
        assert result is True

    @pytest.mark.asyncio
    async def test_edit_html_fallback_to_plain(self):
        bot = AsyncMock()
        call_count = 0

        async def _side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("HTML parse error")

        bot.edit_message_text = AsyncMock(side_effect=_side_effect)
        result = await _edit_html(bot, 123, 456, "text")
        assert result is True
        assert bot.edit_message_text.call_count == 2
        second_call = bot.edit_message_text.call_args_list[1][1]
        assert "parse_mode" not in second_call

    @pytest.mark.asyncio
    async def test_edit_html_both_fail(self):
        bot = AsyncMock()
        bot.edit_message_text = AsyncMock(side_effect=Exception("network error"))
        result = await _edit_html(bot, 123, 456, "text")
        assert result is False


class TestReplyHtml:
    @pytest.mark.asyncio
    async def test_reply_html_success(self):
        message = AsyncMock()
        message.reply_text = AsyncMock(return_value="sent")
        result = await _reply_html(message, "**bold**")
        assert result == "sent"
        call_args = message.reply_text.call_args[0]
        assert "<b>bold</b>" in call_args[0]

    @pytest.mark.asyncio
    async def test_reply_html_fallback(self):
        message = AsyncMock()
        call_count = 0

        async def _side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("HTML error")
            return "sent_plain"

        message.reply_text = AsyncMock(side_effect=_side_effect)
        result = await _reply_html(message, "text")
        assert result == "sent_plain"
        assert message.reply_text.call_count == 2


# ---------------------------------------------------------------------------
# Helper: make mock runners
# ---------------------------------------------------------------------------


def _make_runner(name: str, model: str = "claude-acp/sonnet", desc: str = ""):
    runner = MagicMock()
    runner.agent = MagicMock()
    runner.agent.name = name
    runner.agent.model = model
    runner.agent.description = desc
    runner.app_name = name
    return runner


# ---------------------------------------------------------------------------
# TelegramBridge — single agent tests
# ---------------------------------------------------------------------------


class TestTelegramBridge:
    def _make_bridge(self):
        runner = _make_runner("test_agent", desc="Test agent")
        session_service = AsyncMock()
        return TelegramBridge(
            runner=runner,
            bot_token="fake-token-123",
            session_service=session_service,
        )

    def test_init_single_agent(self):
        bridge = self._make_bridge()
        assert bridge.bot_token == "fake-token-123"
        assert bridge.multi_agent is False
        assert bridge.default_agent == "test_agent"
        assert len(bridge.runners) == 1
        assert "test_agent" in bridge.runners

    def test_build_application(self):
        bridge = self._make_bridge()

        mock_app = MagicMock()
        mock_builder_cls = MagicMock()
        mock_builder_cls.return_value.token.return_value.post_init.return_value.build.return_value = mock_app

        mock_telegram_ext = MagicMock()
        mock_telegram_ext.ApplicationBuilder = mock_builder_cls
        mock_telegram_ext.CommandHandler = MagicMock()
        mock_telegram_ext.CallbackQueryHandler = MagicMock()
        mock_telegram_ext.MessageHandler = MagicMock()
        mock_telegram_ext.filters = MagicMock()

        with patch.dict("sys.modules", {"telegram.ext": mock_telegram_ext}):
            result = bridge.build_application()

        assert result is mock_app
        assert bridge.app is mock_app
        mock_builder_cls.return_value.token.assert_called_once_with("fake-token-123")
        # 11 handlers: start, clear, history, sessions, new, load_history, session, agents, agent, callback, message
        assert mock_app.add_handler.call_count == 11

    @pytest.mark.asyncio
    async def test_handle_start_single(self):
        bridge = self._make_bridge()
        update = MagicMock()
        update.message = AsyncMock()
        update.message.reply_text = AsyncMock()
        context = MagicMock()

        mock_constants = MagicMock()
        with patch.dict("sys.modules", {"telegram.constants": mock_constants}):
            await bridge._handle_start(update, context)

        update.message.reply_text.assert_called_once()
        text = update.message.reply_text.call_args[0][0]
        assert "test_agent" in text

    @pytest.mark.asyncio
    async def test_handle_clear(self):
        bridge = self._make_bridge()
        update = MagicMock()
        update.effective_user = MagicMock()
        update.effective_user.id = 12345
        update.message = AsyncMock()
        update.message.reply_text = AsyncMock()
        context = MagicMock()

        await bridge._handle_clear(update, context)

        update.message.reply_text.assert_called_once()
        reply = update.message.reply_text.call_args[0][0].lower()
        assert "new session" in reply or "started" in reply

    @pytest.mark.asyncio
    async def test_handle_clear_session_not_found(self):
        bridge = self._make_bridge()
        bridge.session_service.delete_session = AsyncMock(
            side_effect=Exception("not found")
        )
        update = MagicMock()
        update.effective_user = MagicMock()
        update.effective_user.id = 12345
        update.message = AsyncMock()
        update.message.reply_text = AsyncMock()
        context = MagicMock()

        await bridge._handle_clear(update, context)
        update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_history_no_session(self):
        bridge = self._make_bridge()
        bridge.session_service.get_session = AsyncMock(return_value=None)

        update = MagicMock()
        update.effective_user = MagicMock()
        update.effective_user.id = 12345
        update.message = AsyncMock()
        update.message.reply_text = AsyncMock()
        context = MagicMock()

        await bridge._handle_history(update, context)

        update.message.reply_text.assert_called_once()
        assert "no" in update.message.reply_text.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_handle_history_with_events(self):
        bridge = self._make_bridge()

        mock_part = MagicMock()
        mock_part.text = "Hello, how are you?"
        mock_content = MagicMock()
        mock_content.parts = [mock_part]
        mock_event = MagicMock()
        mock_event.partial = False
        mock_event.content = mock_content
        mock_event.author = "user"

        mock_session = MagicMock()
        mock_session.events = [mock_event]
        bridge.session_service.get_session = AsyncMock(return_value=mock_session)

        update = MagicMock()
        update.effective_user = MagicMock()
        update.effective_user.id = 12345
        update.message = AsyncMock()
        update.message.reply_text = AsyncMock()
        context = MagicMock()

        mock_constants = MagicMock()
        with patch.dict("sys.modules", {"telegram.constants": mock_constants}):
            await bridge._handle_history(update, context)

        update.message.reply_text.assert_called_once()
        text = update.message.reply_text.call_args[0][0]
        assert "You" in text
        assert "Hello" in text

    def test_stop_not_running(self):
        bridge = self._make_bridge()
        bridge.stop()


# ---------------------------------------------------------------------------
# TelegramBridge — multi-agent tests
# ---------------------------------------------------------------------------


class TestMultiAgentBridge:
    def _make_multi_bridge(self):
        runner_a = _make_runner("agent_a", desc="Agent A")
        runner_b = _make_runner("agent_b", desc="Agent B")
        runner_c = _make_runner("agent_c", desc="Agent C")
        session_service = AsyncMock()
        runners = {
            "agent_a": runner_a,
            "agent_b": runner_b,
            "agent_c": runner_c,
        }
        return TelegramBridge(
            runner=runner_a,
            bot_token="fake-token",
            session_service=session_service,
            runners=runners,
            default_agent="agent_a",
        )

    def test_init_multi_agent(self):
        bridge = self._make_multi_bridge()
        assert bridge.multi_agent is True
        assert bridge.default_agent == "agent_a"
        assert len(bridge.runners) == 3

    def test_get_runner_for_user_default(self):
        bridge = self._make_multi_bridge()
        runner = bridge._get_runner_for_user("user1")
        assert runner.agent.name == "agent_a"

    def test_get_runner_for_user_after_switch(self):
        bridge = self._make_multi_bridge()
        bridge._user_agent["user1"] = "agent_b"
        runner = bridge._get_runner_for_user("user1")
        assert runner.agent.name == "agent_b"

    def test_get_agent_name_for_user(self):
        bridge = self._make_multi_bridge()
        assert bridge._get_agent_name_for_user("user1") == "agent_a"
        bridge._user_agent["user1"] = "agent_c"
        assert bridge._get_agent_name_for_user("user1") == "agent_c"

    @pytest.mark.asyncio
    async def test_handle_start_multi(self):
        bridge = self._make_multi_bridge()
        update = MagicMock()
        update.effective_user = MagicMock()
        update.effective_user.id = 12345
        update.message = AsyncMock()
        update.message.reply_text = AsyncMock()
        context = MagicMock()

        mock_constants = MagicMock()
        mock_telegram = MagicMock()
        with patch.dict("sys.modules", {
            "telegram.constants": mock_constants,
            "telegram": mock_telegram,
        }):
            await bridge._handle_start(update, context)

        update.message.reply_text.assert_called_once()
        text = update.message.reply_text.call_args[0][0]
        assert "agent_a" in text
        assert "agent_b" in text
        assert "agent_c" in text
        # Shows current default agent
        assert "Current" in text or "current" in text
        # Should have reply_markup (InlineKeyboard)
        assert "reply_markup" in update.message.reply_text.call_args[1]

    @pytest.mark.asyncio
    async def test_handle_agents(self):
        bridge = self._make_multi_bridge()
        bridge._user_agent["12345"] = "agent_b"

        update = MagicMock()
        update.effective_user = MagicMock()
        update.effective_user.id = 12345
        update.message = AsyncMock()
        update.message.reply_text = AsyncMock()
        context = MagicMock()

        mock_constants = MagicMock()
        mock_telegram = MagicMock()
        with patch.dict("sys.modules", {
            "telegram.constants": mock_constants,
            "telegram": mock_telegram,
        }):
            await bridge._handle_agents(update, context)

        text = update.message.reply_text.call_args[0][0]
        assert "agent_b" in text
        assert "(current)" in text

    @pytest.mark.asyncio
    async def test_handle_agents_single_agent(self):
        runner = _make_runner("solo_agent")
        bridge = TelegramBridge(
            runner=runner, bot_token="tok", session_service=AsyncMock(),
        )

        update = MagicMock()
        update.message = AsyncMock()
        update.message.reply_text = AsyncMock()
        context = MagicMock()

        mock_constants = MagicMock()
        with patch.dict("sys.modules", {"telegram.constants": mock_constants}):
            await bridge._handle_agents(update, context)

        text = update.message.reply_text.call_args[0][0]
        assert "solo_agent" in text

    @pytest.mark.asyncio
    async def test_handle_agent_switch_command(self):
        from soulbot.sessions.constants import DEFAULT_USER_ID

        bridge = self._make_multi_bridge()
        update = MagicMock()
        update.effective_user = MagicMock()
        update.effective_user.id = 12345
        update.message = AsyncMock()
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        context.args = ["agent_c"]

        mock_constants = MagicMock()
        with patch.dict("sys.modules", {"telegram.constants": mock_constants}):
            await bridge._handle_agent_switch(update, context)

        assert bridge._user_agent[DEFAULT_USER_ID] == "agent_c"
        text = update.message.reply_text.call_args[0][0]
        assert "agent_c" in text

    @pytest.mark.asyncio
    async def test_handle_agent_switch_unknown(self):
        bridge = self._make_multi_bridge()
        update = MagicMock()
        update.effective_user = MagicMock()
        update.effective_user.id = 12345
        update.message = AsyncMock()
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        context.args = ["nonexistent"]

        await bridge._handle_agent_switch(update, context)

        text = update.message.reply_text.call_args[0][0]
        assert "Unknown" in text or "nonexistent" in text

    @pytest.mark.asyncio
    async def test_handle_agent_switch_no_args(self):
        """No args → should show agent list (delegate to _handle_agents)."""
        bridge = self._make_multi_bridge()
        update = MagicMock()
        update.effective_user = MagicMock()
        update.effective_user.id = 12345
        update.message = AsyncMock()
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        context.args = []

        mock_constants = MagicMock()
        mock_telegram = MagicMock()
        with patch.dict("sys.modules", {
            "telegram.constants": mock_constants,
            "telegram": mock_telegram,
        }):
            await bridge._handle_agent_switch(update, context)

        # Should list agents
        text = update.message.reply_text.call_args[0][0]
        assert "agent_a" in text

    @pytest.mark.asyncio
    async def test_handle_callback_agent_select(self):
        from soulbot.sessions.constants import DEFAULT_USER_ID

        bridge = self._make_multi_bridge()
        query = AsyncMock()
        query.data = "agent:agent_b"
        query.from_user = MagicMock()
        query.from_user.id = 99999
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()

        update = MagicMock()
        update.callback_query = query
        context = MagicMock()

        mock_constants = MagicMock()
        with patch.dict("sys.modules", {"telegram.constants": mock_constants}):
            await bridge._handle_callback(update, context)

        query.answer.assert_called_once()
        assert bridge._user_agent[DEFAULT_USER_ID] == "agent_b"
        query.edit_message_text.assert_called_once()
        text = query.edit_message_text.call_args[0][0]
        assert "agent_b" in text

    @pytest.mark.asyncio
    async def test_handle_callback_unknown_agent(self):
        bridge = self._make_multi_bridge()
        query = AsyncMock()
        query.data = "agent:nonexistent"
        query.from_user = MagicMock()
        query.from_user.id = 99999
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()

        update = MagicMock()
        update.callback_query = query
        context = MagicMock()

        await bridge._handle_callback(update, context)

        query.answer.assert_called_once()
        assert "99999" not in bridge._user_agent

    @pytest.mark.asyncio
    async def test_handle_callback_non_agent(self):
        bridge = self._make_multi_bridge()
        query = AsyncMock()
        query.data = "other:data"
        query.answer = AsyncMock()

        update = MagicMock()
        update.callback_query = query
        context = MagicMock()

        await bridge._handle_callback(update, context)
        query.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_switch_agent_keeps_session(self):
        bridge = self._make_multi_bridge()
        bridge._user_session["user1"] = "existing-session"
        await bridge._switch_agent("user1", "agent_b")

        assert bridge._user_agent["user1"] == "agent_b"
        # Doc 21: session is NOT replaced — session belongs to CLI, not agent
        assert bridge._user_session["user1"] == "existing-session"

    @pytest.mark.asyncio
    async def test_message_uses_default_agent(self):
        """In multi-agent mode, unselected user auto-routes to default agent."""
        bridge = self._make_multi_bridge()
        # User 55555 has NOT selected an agent
        runner = bridge._get_runner_for_user("55555")
        # Should fall back to default_agent ("agent_a")
        assert runner.agent.name == "agent_a"

    def test_build_agent_keyboard(self):
        bridge = self._make_multi_bridge()

        mock_button = MagicMock()
        mock_markup = MagicMock()
        mock_telegram = MagicMock()
        mock_telegram.InlineKeyboardButton = mock_button
        mock_telegram.InlineKeyboardMarkup = mock_markup

        with patch.dict("sys.modules", {"telegram": mock_telegram}):
            bridge._build_agent_keyboard("user1")

        # Should create buttons for each agent
        assert mock_button.call_count == 3
        mock_markup.assert_called_once()


# ---------------------------------------------------------------------------
# Token scanning tests
# ---------------------------------------------------------------------------


class TestScanTelegramTokens:
    """Tests for _scan_telegram_tokens (reads from AgentLoader env cache)."""

    def test_scan_single_agent_with_token(self, tmp_path):
        from soulbot.cli import _scan_telegram_tokens
        from soulbot.server.agent_loader import AgentLoader

        agent_dir = tmp_path / "my_agent"
        agent_dir.mkdir()
        (agent_dir / "agent.py").write_text("x = 1\n")
        (agent_dir / ".env").write_text("TELEGRAM_BOT_TOKEN=tok123\n")

        loader = AgentLoader(tmp_path)
        result = _scan_telegram_tokens(loader)
        assert "tok123" in result
        assert result["tok123"] == ["my_agent"]

    def test_scan_no_token_agents_with_root(self, tmp_path):
        from soulbot.cli import _scan_telegram_tokens
        from soulbot.server.agent_loader import AgentLoader

        (tmp_path / ".env").write_text("TELEGRAM_BOT_TOKEN=root_tok\n")
        agent_dir = tmp_path / "bare_agent"
        agent_dir.mkdir()
        (agent_dir / "agent.py").write_text("x = 1\n")
        (agent_dir / ".env").write_text("CLAUDE_CLI=true\n")  # no token

        loader = AgentLoader(tmp_path)
        result = _scan_telegram_tokens(loader, root_token="root_tok")
        assert "root_tok" in result
        assert result["root_tok"] == ["bare_agent"]

    def test_scan_no_token_no_root(self, tmp_path):
        from soulbot.cli import _scan_telegram_tokens
        from soulbot.server.agent_loader import AgentLoader

        agent_dir = tmp_path / "bare_agent"
        agent_dir.mkdir()
        (agent_dir / "agent.py").write_text("x = 1\n")
        (agent_dir / ".env").write_text("CLAUDE_CLI=true\n")

        loader = AgentLoader(tmp_path)
        result = _scan_telegram_tokens(loader)
        assert len(result) == 0

    def test_scan_agent_inherits_root_token(self, tmp_path):
        """Agent without own token inherits root token → goes to shared group."""
        from soulbot.cli import _scan_telegram_tokens
        from soulbot.server.agent_loader import AgentLoader

        (tmp_path / ".env").write_text("TELEGRAM_BOT_TOKEN=root_tok\n")
        agent_dir = tmp_path / "my_agent"
        agent_dir.mkdir()
        (agent_dir / "agent.py").write_text("x = 1\n")
        # No agent .env at all → inherits root

        loader = AgentLoader(tmp_path)
        result = _scan_telegram_tokens(loader, root_token="root_tok")
        assert "root_tok" in result
        assert "my_agent" in result["root_tok"]

    def test_scan_groups_same_token(self, tmp_path):
        from soulbot.cli import _scan_telegram_tokens
        from soulbot.server.agent_loader import AgentLoader

        for name in ["agent_x", "agent_y"]:
            d = tmp_path / name
            d.mkdir()
            (d / "agent.py").write_text("x = 1\n")
            (d / ".env").write_text("TELEGRAM_BOT_TOKEN=shared_tok\n")

        loader = AgentLoader(tmp_path)
        result = _scan_telegram_tokens(loader)
        assert "shared_tok" in result
        assert len(result["shared_tok"]) == 2

    def test_scan_mixed_tokens(self, tmp_path):
        """Independent + shared tokens coexist."""
        from soulbot.cli import _scan_telegram_tokens
        from soulbot.server.agent_loader import AgentLoader

        (tmp_path / ".env").write_text("TELEGRAM_BOT_TOKEN=root_tok\n")

        # Agent with own token
        a = tmp_path / "vip_agent"
        a.mkdir()
        (a / "agent.py").write_text("x = 1\n")
        (a / ".env").write_text("TELEGRAM_BOT_TOKEN=vip_tok\n")

        # Agent without token (inherits root)
        b = tmp_path / "basic_agent"
        b.mkdir()
        (b / "agent.py").write_text("x = 1\n")

        loader = AgentLoader(tmp_path)
        result = _scan_telegram_tokens(loader, root_token="root_tok")
        assert result["vip_tok"] == ["vip_agent"]
        assert result["root_tok"] == ["basic_agent"]


# ---------------------------------------------------------------------------
# CLI command tests
# ---------------------------------------------------------------------------


class TestTelegramCLI:
    def test_telegram_help(self):
        from click.testing import CliRunner
        from soulbot.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["telegram", "--help"])
        assert result.exit_code == 0
        assert "Telegram" in result.output or "telegram" in result.output

    def test_telegram_no_token(self, tmp_path, monkeypatch):
        from unittest.mock import patch
        from click.testing import CliRunner
        from soulbot.cli import main

        # Ensure no real token leaks from cwd/.env or system env
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

        agent_dir = tmp_path / "test_agent"
        agent_dir.mkdir()
        (agent_dir / "agent.py").write_text(
            "from soulbot.agents import LlmAgent\n"
            "root_agent = LlmAgent(name='test', model='claude-acp/sonnet')\n",
            encoding="utf-8",
        )
        (agent_dir / ".env").write_text("CLAUDE_CLI=true\n", encoding="utf-8")

        # Prevent load_dotenv from loading the real cwd/.env
        with patch("soulbot.cli.load_dotenv"):
            runner = CliRunner()
            result = runner.invoke(main, ["telegram", str(agent_dir)])
        assert result.exit_code != 0
        assert "TELEGRAM_BOT_TOKEN" in result.output

    def test_web_telegram_option_help(self):
        from click.testing import CliRunner
        from soulbot.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["web", "--help"])
        assert result.exit_code == 0
        assert "--telegram" in result.output


# ---------------------------------------------------------------------------
# Producer: function_call / function_response visibility
# ---------------------------------------------------------------------------


class TestProducerToolVisibility:
    """Verify that function_call and function_response events are captured
    in the Telegram streaming buffer (not silently hidden)."""

    def _make_bridge(self):
        runner = _make_runner("test_agent")
        session_service = AsyncMock()
        session_service.get_session = AsyncMock(return_value=MagicMock())
        session_service.create_session = AsyncMock(return_value=MagicMock())
        bridge = TelegramBridge(
            runner=runner,
            bot_token="fake-token-123",
            session_service=session_service,
        )
        return bridge

    def _make_event(self, parts, partial=False, error_code=None):
        from soulbot.events import Event, Content, Part

        return Event(
            author="test_agent",
            content=Content(parts=parts),
            partial=partial,
            error_code=error_code,
        )

    @pytest.mark.asyncio
    async def test_function_call_visible_in_buffer(self):
        """function_call event should append tool name to buffer."""
        from soulbot.events import Part, FunctionCall

        bridge = self._make_bridge()

        # Build events: first a function_call, then a final text response
        fc_event = self._make_event([
            Part(function_call=FunctionCall(name="schedule.add", args={"time": 10})),
        ])
        text_event = self._make_event([Part(text="Done!")])

        async def fake_run(**kwargs):
            yield fc_event
            yield text_event

        bridge.runners["test_agent"].run = fake_run

        update = MagicMock()
        update.effective_user = MagicMock()
        update.effective_user.id = 12345
        update.message = AsyncMock()
        update.message.reply_text = AsyncMock(return_value=MagicMock(
            chat_id=123, message_id=456,
        ))
        context = MagicMock()
        context.bot = AsyncMock()
        context.bot.edit_message_text = AsyncMock()

        with patch.dict("sys.modules", {"telegram.constants": MagicMock()}):
            await bridge._handle_message(update, context)

        # Check that at least one edit_message_text call contains the tool name
        calls = context.bot.edit_message_text.call_args_list
        all_text = " ".join(
            str(c) for c in calls
        )
        assert "schedule.add" in all_text

    @pytest.mark.asyncio
    async def test_function_response_visible_in_buffer(self):
        """function_response event should append tool result to buffer."""
        from soulbot.events import Part, FunctionCall, FunctionResponse

        bridge = self._make_bridge()

        fc_event = self._make_event([
            Part(function_call=FunctionCall(name="schedule.add", args={})),
        ])
        fr_event = self._make_event([
            Part(function_response=FunctionResponse(
                name="schedule.add",
                response={"entry_id": "remind_water", "status": "active"},
            )),
        ])
        text_event = self._make_event([Part(text="Reminder set!")])

        async def fake_run(**kwargs):
            yield fc_event
            yield fr_event
            yield text_event

        bridge.runners["test_agent"].run = fake_run

        update = MagicMock()
        update.effective_user = MagicMock()
        update.effective_user.id = 12345
        update.message = AsyncMock()
        update.message.reply_text = AsyncMock(return_value=MagicMock(
            chat_id=123, message_id=456,
        ))
        context = MagicMock()
        context.bot = AsyncMock()
        context.bot.edit_message_text = AsyncMock()

        with patch.dict("sys.modules", {"telegram.constants": MagicMock()}):
            await bridge._handle_message(update, context)

        calls = context.bot.edit_message_text.call_args_list
        all_text = " ".join(str(c) for c in calls)
        assert "remind_water" in all_text
        assert "active" in all_text
