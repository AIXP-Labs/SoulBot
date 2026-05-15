"""Telegram Bridge — route Telegram messages to SoulBot Agent Runner.

Provides a TelegramBridge class that:
- Receives messages via Telegram Long Polling
- Routes them through Runner.run(stream=True)
- Sends back AI responses with typewriter effect (edit_message_text)
- Renders Markdown as Telegram-compatible HTML
- Supports multi-agent routing via /agents command + InlineKeyboard

Usage::

    # Single agent
    bridge = TelegramBridge(runner=runner, bot_token=token, session_service=svc)
    bridge.start_in_thread()

    # Multi-agent routing
    bridge = TelegramBridge(
        runner=runners["default"],
        bot_token=token,
        session_service=svc,
        runners=runners,
        default_agent="default",
    )
    bridge.start_in_thread()
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
import threading
import time
import unicodedata
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from ..runners.runner import Runner
    from ..sessions.base_session_service import BaseSessionService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Markdown → Telegram HTML
# ---------------------------------------------------------------------------


def _escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ---------------------------------------------------------------------------
# Table rendering helpers (inspired by OpenClaw "code" table mode)
# ---------------------------------------------------------------------------


def _strip_md(text: str) -> str:
    """Strip Markdown inline formatting for plain-text display."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"\1", text)
    text = re.sub(r"~~(.+?)~~", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return text


def _display_width(text: str) -> int:
    """Display width — CJK fullwidth chars count as 2."""
    w = 0
    for ch in text:
        if unicodedata.east_asian_width(ch) in ("W", "F"):
            w += 2
        else:
            w += 1
    return w


def _pad_to_width(text: str, target: int) -> str:
    """Right-pad *text* with spaces to reach *target* display columns."""
    return text + " " * max(0, target - _display_width(text))


_TABLE_SEP_RE = re.compile(
    r"^\s*\|?[\s:]*-{2,}[\s:]*(\|[\s:]*-{2,}[\s:]*)*\|?\s*$"
)


def _render_table_cards(table_lines: list[str]) -> str:
    """Render Markdown table as card-list HTML (mobile-friendly, no ``<pre>``)."""
    rows: list[list[str]] = []
    for line in table_lines:
        stripped = line.strip()
        if _TABLE_SEP_RE.match(stripped):
            continue  # skip separator row
        if stripped.startswith("|"):
            stripped = stripped[1:]
        if stripped.endswith("|"):
            stripped = stripped[:-1]
        cells = [_strip_md(c.strip()) for c in stripped.split("|")]
        rows.append(cells)

    if not rows:
        return ""

    headers = rows[0]
    data_rows = rows[1:] if len(rows) > 1 else []

    if not data_rows:
        # Header-only table → just bold the cells
        return "<b>" + _escape_html(" · ".join(headers)) + "</b>"

    out: list[str] = []
    for row in data_rows:
        # First column value as card title
        title = _escape_html(row[0]) if row else ""
        pairs: list[str] = []
        for ci in range(1, len(headers)):
            key = _escape_html(headers[ci]) if ci < len(headers) else ""
            val = _escape_html(row[ci]) if ci < len(row) else ""
            pairs.append(f"{key}: {val}")
        if pairs:
            out.append(f"◆ <b>{title}</b>\n  {' · '.join(pairs)}")
        else:
            out.append(f"◆ <b>{title}</b>")

    return "\n".join(out)


def _extract_tables(text: str, table_blocks: list[str]) -> str:
    """Find Markdown tables, convert to card-list HTML, replace with placeholders."""
    lines = text.split("\n")
    result: list[str] = []
    i = 0
    while i < len(lines):
        if (
            "|" in lines[i]
            and i + 1 < len(lines)
            and _TABLE_SEP_RE.match(lines[i + 1])
        ):
            tbl: list[str] = [lines[i], lines[i + 1]]
            i += 2
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                tbl.append(lines[i])
                i += 1
            idx = len(table_blocks)
            table_blocks.append(_render_table_cards(tbl))
            result.append(f"\x00TABLE{idx}\x00")
        else:
            result.append(lines[i])
            i += 1
    return "\n".join(result)


# ---------------------------------------------------------------------------
# Markdown-aware chunking (Telegram 4096 char limit)
# ---------------------------------------------------------------------------

# Telegram hard limit is 4096 chars for the *rendered* message.
# HTML tags add overhead, so we use a lower raw-text limit.
_CHUNK_LIMIT = 3500


def _chunk_markdown(text: str, limit: int = _CHUNK_LIMIT) -> list[str]:
    """Split Markdown text into chunks at natural boundaries.

    Split priority:
    1. Double newline (paragraph break)
    2. Single newline
    3. Hard break at *limit*

    Each chunk is self-contained Markdown that can be independently
    converted to Telegram HTML.
    """
    if len(text) <= limit:
        return [text]

    # Split text at paragraph boundaries, keeping separators
    sections = re.split(r"(\n\n+)", text)

    chunks: list[str] = []
    current = ""

    for section in sections:
        if not current:
            current = section
        elif len(current) + len(section) <= limit:
            current += section
        else:
            if current.strip():
                chunks.append(current.rstrip())
            current = section.lstrip("\n")

    if current.strip():
        chunks.append(current.rstrip())

    # Handle chunks still too long (e.g. a single massive paragraph)
    final: list[str] = []
    for chunk in chunks:
        if len(chunk) <= limit:
            final.append(chunk)
        else:
            lines = chunk.split("\n")
            sub = ""
            for line in lines:
                # Single line longer than limit → hard-break
                if len(line) > limit:
                    if sub.strip():
                        final.append(sub)
                        sub = ""
                    for j in range(0, len(line), limit):
                        final.append(line[j : j + limit])
                elif not sub:
                    sub = line
                elif len(sub) + 1 + len(line) <= limit:
                    sub += "\n" + line
                else:
                    if sub.strip():
                        final.append(sub)
                    sub = line
            if sub.strip():
                final.append(sub)

    return final if final else [text[:limit]]


# ---------------------------------------------------------------------------
# Markdown → Telegram HTML (enhanced)
# ---------------------------------------------------------------------------


def md_to_html(text: str) -> str:
    """Convert Markdown to Telegram-compatible HTML.

    Telegram supports: <b> <i> <code> <pre> <a> <s> <blockquote>

    Processing order:
    1. Extract and protect code blocks (``````...``````)
    2. Extract and convert Markdown tables → card-list HTML
    3. Extract and protect inline code (`...`)
    4. Escape HTML special characters in remaining text
    5. Apply Markdown → HTML conversions
    6. Convert unordered lists (- item → • item)
    7. Convert blockquotes (> text → <blockquote>)
    8. Restore code blocks, tables, and inline code
    """
    # Step 1: Extract code blocks → <pre><code>
    code_blocks: list[str] = []

    def _save_code_block(m: re.Match) -> str:
        idx = len(code_blocks)
        code_blocks.append(
            f"<pre><code>{_escape_html(m.group(1).strip())}</code></pre>"
        )
        return f"\x00CODEBLOCK{idx}\x00"

    text = re.sub(r"```(?:\w*)\n(.*?)```", _save_code_block, text, flags=re.DOTALL)

    # Step 2: Extract and convert Markdown tables → <pre> aligned blocks
    table_blocks: list[str] = []
    text = _extract_tables(text, table_blocks)

    # Step 3: Extract inline code → <code>
    inline_codes: list[str] = []

    def _save_inline_code(m: re.Match) -> str:
        idx = len(inline_codes)
        inline_codes.append(f"<code>{_escape_html(m.group(1))}</code>")
        return f"\x00INLINE{idx}\x00"

    text = re.sub(r"`([^`]+)`", _save_inline_code, text)

    # Step 4: Escape remaining HTML
    text = _escape_html(text)

    # Step 5: Markdown → HTML conversions
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)                    # **bold**
    text = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<i>\1</i>", text)        # *italic*
    text = re.sub(r"~~(.+?)~~", r"<s>\1</s>", text)                        # ~~strike~~
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text) # [text](url)
    text = re.sub(r"^#{1,6}\s+(.+)$", r"<b>\1</b>", text, flags=re.MULTILINE)  # heading
    text = re.sub(r"^-{3,}$", "───", text, flags=re.MULTILINE)             # --- → line

    # Step 6: Convert unordered lists (- item → • item)
    text = re.sub(r"^(\s*)-\s+", r"\1• ", text, flags=re.MULTILINE)

    # Step 7: Convert blockquotes (&gt; after HTML escaping)
    text = re.sub(
        r"^&gt;\s?(.+)$", r"<blockquote>\1</blockquote>", text, flags=re.MULTILINE
    )
    text = re.sub(r"</blockquote>\n<blockquote>", "\n", text)  # merge consecutive

    # Step 8: Restore protected blocks
    for idx, block in enumerate(code_blocks):
        text = text.replace(f"\x00CODEBLOCK{idx}\x00", block)
    for idx, block in enumerate(table_blocks):
        text = text.replace(f"\x00TABLE{idx}\x00", block)
    for idx, code in enumerate(inline_codes):
        text = text.replace(f"\x00INLINE{idx}\x00", code)

    return text


# ---------------------------------------------------------------------------
# Telegram HTML helpers
# ---------------------------------------------------------------------------


async def _notify_flood_control(bot: Any, chat_id: int, retry_after: int) -> None:
    """Notify user about Telegram flood control wait time."""
    if retry_after < 60:
        wait_text = f"{retry_after} seconds"
    elif retry_after < 3600:
        minutes = retry_after // 60
        wait_text = f"{minutes} min"
    else:
        hours = retry_after // 3600
        minutes = (retry_after % 3600) // 60
        wait_text = f"{hours}h {minutes}m" if minutes else f"{hours}h"
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=f"\u26a0\ufe0f Telegram rate limit reached. Will resume in ~{wait_text}.",
        )
    except Exception:
        pass


async def _edit_html(bot: Any, chat_id: int, message_id: int, text: str) -> bool:
    """Edit a message with HTML rendering, falling back to plain text."""
    from telegram.constants import ParseMode
    from telegram.error import RetryAfter

    html = md_to_html(text)
    try:
        await bot.edit_message_text(
            chat_id=chat_id, message_id=message_id,
            text=html, parse_mode=ParseMode.HTML,
        )
        return True
    except RetryAfter as e:
        logger.warning("Telegram flood control: retry after %ss", e.retry_after)
        await _notify_flood_control(bot, chat_id, e.retry_after)
        await asyncio.sleep(min(e.retry_after, 30))
        return False
    except Exception as e:
        if "not modified" in str(e).lower():
            return True
        # HTML parse failure → fallback to plain text
        try:
            await bot.edit_message_text(
                chat_id=chat_id, message_id=message_id, text=text,
            )
            return True
        except RetryAfter as e2:
            logger.warning("Telegram flood control: retry after %ss", e2.retry_after)
            await _notify_flood_control(bot, chat_id, e2.retry_after)
            await asyncio.sleep(min(e2.retry_after, 30))
            return False
        except Exception:
            return False


async def _reply_html(message: Any, text: str) -> Any:
    """Reply with HTML rendering, falling back to plain text."""
    from telegram.constants import ParseMode
    from telegram.error import RetryAfter

    html = md_to_html(text)
    try:
        return await message.reply_text(html, parse_mode=ParseMode.HTML)
    except RetryAfter as e:
        logger.warning("Telegram flood control on reply: retry after %ss", e.retry_after)
        await _notify_flood_control(message.get_bot(), message.chat_id, e.retry_after)
        await asyncio.sleep(min(e.retry_after, 30))
        return await message.reply_text(html, parse_mode=ParseMode.HTML)
    except Exception:
        return await message.reply_text(text)


# ---------------------------------------------------------------------------
# TelegramBridge
# ---------------------------------------------------------------------------


class TelegramBridge:
    """Bridge Telegram messages to SoulBot Agent Runner(s).

    Supports two modes:
    - **Single agent**: one Runner, messages go directly to it.
    - **Multi-agent routing**: multiple Runners, user selects via
      ``/agents`` command or InlineKeyboard buttons.

    Args:
        runner: The default Runner instance.
        bot_token: Telegram Bot API token (from @BotFather).
        session_service: Shared session service.
        runners: Optional dict ``{agent_name: Runner}`` for multi-agent mode.
        default_agent: Name of the default agent (used when user hasn't chosen).
    """

    def __init__(
        self,
        runner: "Runner",
        bot_token: str,
        session_service: "BaseSessionService",
        runners: dict[str, "Runner"] | None = None,
        default_agent: str | None = None,
        bus: Optional[Any] = None,
        on_startup: list | None = None,
        history_service: Optional[Any] = None,
    ) -> None:
        self.runner = runner
        self.bot_token = bot_token
        self.session_service = session_service

        # Multi-agent support
        self.runners: dict[str, "Runner"] = runners or {runner.agent.name: runner}
        self.default_agent = default_agent or runner.agent.name
        self.multi_agent = len(self.runners) > 1

        # User → current agent name mapping
        self._user_agent: dict[str, str] = {}

        # User → current session_id mapping (Doc 20)
        self._user_session: dict[str, str] = {}

        # User → chat_id cache (for scheduled task delivery)
        self._user_chat_cache: dict[str, int] = {}

        # EventBus (optional, for schedule.executed subscription)
        self._bus = bus
        if bus:
            bus.subscribe("schedule.executed", self._on_schedule_executed)

        # Startup coroutines (e.g. cron.start) — run in _post_init
        self._on_startup = on_startup or []

        # Chat history service (Doc 22)
        self._history_service = history_service

        self.app: Any = None  # telegram.ext.Application
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Multi-agent helpers
    # ------------------------------------------------------------------

    def _get_runner_for_user(self, user_id: str) -> "Runner":
        """Get the Runner bound to a user (or default)."""
        agent_name = self._user_agent.get(user_id, self.default_agent)
        return self.runners.get(agent_name, self.runner)

    def _get_agent_name_for_user(self, user_id: str) -> str:
        """Get the agent name bound to a user (or default)."""
        return self._user_agent.get(user_id, self.default_agent)

    async def _ensure_user_agent_loaded(self, user_id: str) -> None:
        """Restore the user's last active agent (+ session) from DB when
        the in-memory cache is cold (e.g. first message after restart).

        Cross-restart continuity hook. Idempotent: warm-cache calls no-op.
        MUST run before any handler reads `_user_agent` (directly or via
        `_get_agent_name_for_user` / `_get_runner_for_user`); otherwise
        `/start`, `/agents`, and first-message routing fall back to
        `default_agent` regardless of the user's last session.

        `list_all_sessions(app_name, user_id)` queries across every agent
        (multi-agent runners share app_name) ordered by last_update_time
        DESC. Top row's `last_agent` (or fallback `agent_name` for legacy
        rows) is the user's most recent active agent.
        """
        if not self.multi_agent or user_id in self._user_agent:
            return
        try:
            any_runner = next(iter(self.runners.values()))
            all_sessions = await self.session_service.list_all_sessions(
                any_runner.app_name, user_id
            )
            if not all_sessions:
                return
            latest = all_sessions[0]
            restored_agent = latest.last_agent or latest.agent_name
            if restored_agent and restored_agent in self.runners:
                self._user_agent[user_id] = restored_agent
                # Warm session cache so subsequent _get_session_id_for_user
                # skips its own DB roundtrip.
                if user_id not in self._user_session:
                    self._user_session[user_id] = latest.id
                logger.info(
                    "Telegram last-agent restore: user=%s → agent=%s "
                    "session=%s (from DB)",
                    user_id, restored_agent, latest.id,
                )
        except Exception as e:
            logger.warning("last_agent restore failed: %s", e)

    async def _get_session_id_for_user(self, user_id: str) -> str:
        """Get or auto-resume the session_id for a user (Doc 11).

        Cold-cache path (after restart or first message): restore last
        active agent via `_ensure_user_agent_loaded`, then look up the
        session for that agent. Warm-cache path: return cached session
        id immediately.
        """
        if user_id in self._user_session:
            return self._user_session[user_id]

        # Cold-cache: restore last active agent + session from DB.
        await self._ensure_user_agent_loaded(user_id)
        if user_id in self._user_session:
            return self._user_session[user_id]

        runner = self._get_runner_for_user(user_id)
        agent_name = self._get_agent_name_for_user(user_id)

        try:
            sessions = await self.session_service.list_sessions(
                runner.app_name, user_id, agent_name=agent_name
            )
            if sessions:
                sid = sessions[0].id
                self._user_session[user_id] = sid
                return sid
        except Exception:
            pass

        # No existing session — use a default ID; Runner will create it
        import uuid
        sid = str(uuid.uuid4())
        self._user_session[user_id] = sid
        return sid

    # ------------------------------------------------------------------
    # Application builder
    # ------------------------------------------------------------------

    def build_application(self) -> Any:
        """Build the Telegram Application and register handlers."""
        try:
            from telegram.ext import (
                ApplicationBuilder,
                CallbackQueryHandler,
                CommandHandler,
                MessageHandler,
                filters,
            )
        except ImportError:
            raise ImportError(
                "python-telegram-bot is required for Telegram support. "
                "Install with: pip install 'python-telegram-bot>=20.0'"
            )

        builder = ApplicationBuilder().token(self.bot_token).post_init(self._post_init)

        # Proxy support — reads from TELEGRAM_PROXY or HTTPS_PROXY env var.
        # Examples:  http://127.0.0.1:7890  socks5://127.0.0.1:1080
        proxy_url = os.environ.get("TELEGRAM_PROXY") or os.environ.get("HTTPS_PROXY")
        if proxy_url:
            from telegram.request import HTTPXRequest
            request = HTTPXRequest(proxy=proxy_url, connect_timeout=30, read_timeout=30)
            builder = builder.request(request).get_updates_request(HTTPXRequest(proxy=proxy_url, connect_timeout=30, read_timeout=30))
            logger.info("Telegram using proxy: %s", proxy_url)

        self.app = builder.build()
        self.app.add_handler(CommandHandler("start", self._handle_start))
        self.app.add_handler(CommandHandler("clear", self._handle_clear))
        self.app.add_handler(CommandHandler("history", self._handle_history))
        self.app.add_handler(CommandHandler("sessions", self._handle_sessions))
        self.app.add_handler(CommandHandler("new", self._handle_new_session))
        self.app.add_handler(CommandHandler("load_history", self._handle_import))
        self.app.add_handler(CommandHandler("session", self._handle_session_switch))
        self.app.add_handler(CommandHandler("agents", self._handle_agents))
        self.app.add_handler(CommandHandler("agent", self._handle_agent_switch))
        self.app.add_handler(CallbackQueryHandler(self._handle_callback))
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
        )
        return self.app

    async def _post_init(self, application: Any) -> None:
        """Register bot commands with Telegram and run startup coroutines."""
        from telegram import BotCommand

        commands = [
            BotCommand("start", "Start / show agent info"),
            BotCommand("clear", "Clear and start new session"),
            BotCommand("history", "Show recent history"),
            BotCommand("sessions", "List all sessions"),
            BotCommand("new", "Create a new session"),
            BotCommand("session", "Switch to session by number"),
        ]
        if self.multi_agent:
            commands.append(BotCommand("agents", "Switch agent"))
        await application.bot.set_my_commands(commands)

        # Run startup coroutines (e.g. CronScheduler.start)
        for coro_fn in self._on_startup:
            try:
                await coro_fn()
            except Exception as exc:
                logger.error("Startup callback failed: %s", exc)

    # ------------------------------------------------------------------
    # InlineKeyboard builder
    # ------------------------------------------------------------------

    def _build_agent_keyboard(self, user_id: str) -> Any:
        """Build InlineKeyboard with agent selection buttons."""
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        current = self._get_agent_name_for_user(user_id)
        buttons = []
        row: list[Any] = []
        for name, r in self.runners.items():
            label = r.agent.name
            if name == current:
                label = f"🤖 {label}"
            row.append(InlineKeyboardButton(label, callback_data=f"agent:{name}"))
            if len(row) >= 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        return InlineKeyboardMarkup(buttons)

    # ------------------------------------------------------------------
    # Command handlers
    # ------------------------------------------------------------------

    async def _handle_start(self, update: Any, context: Any) -> None:
        """/start — show agent info or agent selection menu."""
        from telegram.constants import ParseMode
        from ..sessions.constants import DEFAULT_USER_ID

        user_id = DEFAULT_USER_ID

        if self.multi_agent:
            # Restore last-active agent from DB if cache is cold (post-restart).
            await self._ensure_user_agent_loaded(user_id)
            # Multi-agent: show current agent + selection menu
            current = self._get_agent_name_for_user(user_id)
            lines = [
                "<b>SoulBot</b>",
                "",
                f"Current: <b>{_escape_html(current)}</b>",
                "",
                "Available Agents:",
            ]
            for name, r in self.runners.items():
                desc = r.agent.description or ""
                marker = " (current)" if name == current else ""
                lines.append(f"  • <b>{_escape_html(name)}</b>{marker}: {_escape_html(desc)}")
            lines.append("")
            lines.append("Use /agents to switch. Commands: /clear /history")

            await update.message.reply_text(
                "\n".join(lines),
                parse_mode=ParseMode.HTML,
                reply_markup=self._build_agent_keyboard(user_id),
            )
        else:
            # Single agent: show info
            agent = self.runner.agent
            lines = [
                f"<b>{_escape_html(agent.name)}</b>",
                "",
                f"Model: <code>{_escape_html(agent.model or 'default')}</code>",
            ]
            if agent.description:
                lines.append(f"Description: {_escape_html(agent.description)}")
            lines.append("")
            lines.append("Send a message to start chatting.")
            lines.append("Commands: /clear /history")

            await update.message.reply_text(
                "\n".join(lines), parse_mode=ParseMode.HTML,
            )

    async def _handle_agents(self, update: Any, context: Any) -> None:
        """/agents — list available agents with selection buttons."""
        from telegram.constants import ParseMode
        from ..sessions.constants import DEFAULT_USER_ID

        if not self.multi_agent:
            agent = self.runner.agent
            await update.message.reply_text(
                f"Current agent: <b>{_escape_html(agent.name)}</b>",
                parse_mode=ParseMode.HTML,
            )
            return

        user_id = DEFAULT_USER_ID
        await self._ensure_user_agent_loaded(user_id)
        current = self._get_agent_name_for_user(user_id)

        lines = ["<b>Available Agents:</b>", ""]
        for name, r in self.runners.items():
            marker = " (current)" if name == current else ""
            desc = r.agent.description or ""
            lines.append(
                f"  • <b>{_escape_html(name)}</b>{marker}\n"
                f"    {_escape_html(desc)}"
            )

        await update.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.HTML,
            reply_markup=self._build_agent_keyboard(user_id),
        )

    async def _handle_agent_switch(self, update: Any, context: Any) -> None:
        """/agent <name> — switch to a specific agent."""
        from telegram.constants import ParseMode
        from ..sessions.constants import DEFAULT_USER_ID

        if not self.multi_agent:
            await update.message.reply_text("Only one agent available.")
            return

        args = context.args
        if not args:
            await self._handle_agents(update, context)
            return

        target = args[0]
        if target not in self.runners:
            names = ", ".join(self.runners.keys())
            await update.message.reply_text(f"Unknown agent: {target}\nAvailable: {names}")
            return

        user_id = DEFAULT_USER_ID
        await self._switch_agent(user_id, target)

        agent = self.runners[target].agent
        await update.message.reply_text(
            f"Switched to <b>{_escape_html(agent.name)}</b>\n"
            f"{_escape_html(agent.description or '')}",
            parse_mode=ParseMode.HTML,
        )

    async def _handle_callback(self, update: Any, context: Any) -> None:
        """Handle InlineKeyboard button clicks."""
        from telegram.constants import ParseMode

        query = update.callback_query
        await query.answer()

        if not query.data or not query.data.startswith("agent:"):
            return

        agent_name = query.data.split(":", 1)[1]
        if agent_name not in self.runners:
            await query.edit_message_text("Agent not found.")
            return

        from ..sessions.constants import DEFAULT_USER_ID

        user_id = DEFAULT_USER_ID
        await self._switch_agent(user_id, agent_name)

        agent = self.runners[agent_name].agent
        await query.edit_message_text(
            f"Connected to <b>{_escape_html(agent.name)}</b>\n"
            f"Model: <code>{_escape_html(agent.model or 'default')}</code>\n"
            f"{_escape_html(agent.description or '')}\n\n"
            f"Send a message to start chatting.",
            parse_mode=ParseMode.HTML,
        )

    async def _switch_agent(self, user_id: str, agent_name: str) -> None:
        """Switch a user to a different agent (Doc 21: keep current session)."""
        self._user_agent[user_id] = agent_name
        # Doc 21: do NOT create new session — session belongs to CLI, not agent.
        # last_agent will be updated on next Runner.run() call.
        logger.info("User %s switched to agent: %s", user_id, agent_name)

    async def _handle_clear(self, update: Any, context: Any) -> None:
        """/clear — start a new session (old session kept in history)."""
        import uuid as _uuid
        from ..sessions.constants import DEFAULT_USER_ID

        user_id = DEFAULT_USER_ID
        # Restore last-active agent first so the next message routes there,
        # not to default_agent. Without this, setting _user_session below
        # makes _get_session_id_for_user short-circuit past the restore.
        await self._ensure_user_agent_loaded(user_id)
        # Switch to a new session (old session preserved for /sessions)
        new_sid = str(_uuid.uuid4())
        self._user_session[user_id] = new_sid
        await update.message.reply_text("New session started. Send a message to begin.")

    async def _handle_history(self, update: Any, context: Any) -> None:
        """/history — show recent conversation history (Doc 22: from SQLite)."""
        from ..sessions.constants import DEFAULT_USER_ID

        user_id = DEFAULT_USER_ID
        await self._ensure_user_agent_loaded(user_id)
        agent_name = self._get_agent_name_for_user(user_id)

        # Prefer history service (Doc 22)
        if self._history_service:
            try:
                messages = await self._history_service.get_agent_history(
                    user_id, agent_name, limit=20
                )
            except Exception:
                messages = []

            if not messages:
                await update.message.reply_text("No conversation history.")
                return

            from datetime import datetime
            from telegram.constants import ParseMode

            lines: list[str] = []
            for m in reversed(messages):  # chronological order
                dt = datetime.fromtimestamp(m.created_at).strftime("%H:%M")
                role = "You" if m.role == "user" else "Bot"
                snippet = m.content[:100]
                if len(m.content) > 100:
                    snippet += "..."
                lines.append(
                    f"[{_escape_html(dt)}] "
                    f"<b>{_escape_html(role)}</b>: {_escape_html(snippet)}"
                )

            await update.message.reply_text(
                "\n".join(lines), parse_mode=ParseMode.HTML,
            )
            return

        # Fallback: read from session events
        session_id = await self._get_session_id_for_user(user_id)
        runner = self._get_runner_for_user(user_id)
        session = await self.session_service.get_session(
            runner.app_name, user_id, session_id,
        )
        if session is None or not session.events:
            await update.message.reply_text("No conversation history.")
            return

        lines = []
        count = 0
        for ev in reversed(session.events):
            if ev.partial or not ev.content or not ev.content.parts:
                continue
            for part in ev.content.parts:
                if part.text:
                    role = "You" if ev.author == "user" else ev.author
                    snippet = part.text[:100]
                    if len(part.text) > 100:
                        snippet += "..."
                    lines.append(f"<b>{_escape_html(role)}</b>: {_escape_html(snippet)}")
                    count += 1
                    break
            if count >= 10:
                break

        lines.reverse()
        if not lines:
            await update.message.reply_text("No conversation history.")
            return

        from telegram.constants import ParseMode

        await update.message.reply_text(
            "\n".join(lines), parse_mode=ParseMode.HTML,
        )

    # ------------------------------------------------------------------
    # Session management commands (Doc 20)
    # ------------------------------------------------------------------

    async def _handle_sessions(self, update: Any, context: Any) -> None:
        """/sessions — list all sessions under this CLI (Doc 11)."""
        from datetime import datetime
        from telegram.constants import ParseMode
        from ..sessions.constants import DEFAULT_USER_ID

        user_id = DEFAULT_USER_ID
        await self._ensure_user_agent_loaded(user_id)
        runner = self._get_runner_for_user(user_id)
        try:
            # Show ALL sessions under this CLI (not filtered by agent)
            sessions = await self.session_service.list_all_sessions(
                runner.app_name, user_id
            )
        except Exception:
            sessions = []

        if not sessions:
            await update.message.reply_text("No sessions found. Send a message to start.")
            return

        current_sid = self._user_session.get(user_id)
        lines = ["<b>Sessions:</b>", ""]
        for idx, s in enumerate(sessions[:20], 1):
            dt = datetime.fromtimestamp(s.last_update_time).strftime("%m-%d %H:%M")
            title = s.title or s.id[:8]
            marker = " (current)" if s.id == current_sid else ""
            agent_tag = f" ({_escape_html(s.last_agent)})" if s.last_agent else ""
            lines.append(
                f"  {idx}. [{_escape_html(dt)}] "
                f"<b>{_escape_html(title)}</b>{agent_tag}{marker}"
            )
        lines.append("")
        lines.append("/session &lt;number&gt; to switch | /new to create")

        await update.message.reply_text(
            "\n".join(lines), parse_mode=ParseMode.HTML,
        )

    async def _handle_new_session(self, update: Any, context: Any) -> None:
        """/new — create a new session."""
        import uuid as _uuid
        from ..sessions.constants import DEFAULT_USER_ID

        user_id = DEFAULT_USER_ID
        await self._ensure_user_agent_loaded(user_id)
        new_sid = str(_uuid.uuid4())
        self._user_session[user_id] = new_sid
        await update.message.reply_text(
            "New session created. Send a message to begin.\n"
            "Use /load_history to import previous chat history."
        )

    async def _handle_import(self, update: Any, context: Any) -> None:
        """/load_history — import recent history into current session (Doc 22)."""
        from ..sessions.constants import DEFAULT_USER_ID

        user_id = DEFAULT_USER_ID

        if not self._history_service:
            await update.message.reply_text("History service not available.")
            return

        await self._ensure_user_agent_loaded(user_id)
        agent_name = self._get_agent_name_for_user(user_id)
        session_id = await self._get_session_id_for_user(user_id)
        runner = self._get_runner_for_user(user_id)

        # Get or create the session
        session = await self.session_service.get_session(
            runner.app_name, user_id, session_id,
        )
        if session is None:
            session = await self.session_service.create_session(
                runner.app_name, user_id, agent_name=agent_name,
                session_id=session_id,
            )

        from ..history import import_history_to_session

        try:
            imported = await import_history_to_session(
                self._history_service, self.session_service, session,
                user_id, agent_name,
            )
        except Exception as exc:
            logger.warning("History import failed: %s", exc)
            await update.message.reply_text("Failed to import history.")
            return

        if imported == 0:
            await update.message.reply_text(
                f"No previous history found for {agent_name}."
            )
        else:
            await update.message.reply_text(
                f"Imported {imported} messages into current session."
            )

    async def _handle_session_switch(self, update: Any, context: Any) -> None:
        """/session <number> — switch to a session by its list number (Doc 21)."""
        from ..sessions.constants import DEFAULT_USER_ID

        user_id = DEFAULT_USER_ID
        args = context.args
        if not args:
            await self._handle_sessions(update, context)
            return

        try:
            idx = int(args[0])
        except (ValueError, IndexError):
            await update.message.reply_text("Usage: /session <number>")
            return

        await self._ensure_user_agent_loaded(user_id)
        runner = self._get_runner_for_user(user_id)
        try:
            sessions = await self.session_service.list_all_sessions(
                runner.app_name, user_id
            )
        except Exception:
            sessions = []

        if idx < 1 or idx > len(sessions):
            await update.message.reply_text(
                f"Invalid session number. Use /sessions to see available (1-{len(sessions)})."
            )
            return

        target = sessions[idx - 1]
        self._user_session[user_id] = target.id

        # Auto-switch to session's agent (Doc 21)
        if target.last_agent and target.last_agent in self.runners:
            self._user_agent[user_id] = target.last_agent

        title = target.title or target.id[:8]
        agent_info = f" -> agent: {target.last_agent}" if target.last_agent else ""
        await update.message.reply_text(f"Switched to session: {title}{agent_info}")

    # ------------------------------------------------------------------
    # Message handler (core: producer-consumer streaming)
    # ------------------------------------------------------------------

    async def _on_schedule_executed(self, event: Any) -> None:
        """Handle schedule.executed events — deliver results to Telegram users."""
        data = event.data
        origin_channel = data.get("origin_channel", "")

        # Only handle telegram and heartbeat origins
        if origin_channel not in ("telegram", "heartbeat"):
            return

        result = data.get("result", "")
        if not result:
            return

        if origin_channel == "heartbeat":
            await self._broadcast_heartbeat(data)
            return

        # Telegram origin — deliver to the originating user
        origin_user = data.get("origin_user", "")
        chat_id = self._user_chat_cache.get(origin_user)
        if not chat_id:
            logger.warning(
                "Schedule result for user %s but no cached chat_id", origin_user
            )
            return

        entry_id = data.get("entry_id", "")
        from_agent = data.get("from_agent", "")
        to_agent = data.get("to_agent", "")
        header = f"[Schedule: {entry_id}]" if entry_id else "[Schedule]"
        if from_agent and to_agent and from_agent != to_agent:
            header = f"**{to_agent}** (from {from_agent}) {header}"
        elif to_agent:
            header = f"**{to_agent}** {header}"
        text = f"{header}\n{result[:4000]}"

        if self.app and self.app.bot:
            from telegram.constants import ParseMode

            html = md_to_html(text)
            try:
                await self.app.bot.send_message(
                    chat_id=chat_id, text=html, parse_mode=ParseMode.HTML,
                )
            except Exception:
                try:
                    await self.app.bot.send_message(chat_id=chat_id, text=text)
                except Exception as exc:
                    logger.error(
                        "Failed to send schedule result to %s: %s", chat_id, exc
                    )

    async def _broadcast_heartbeat(self, data: dict) -> None:
        """Broadcast heartbeat result to all known Telegram chats."""
        result = data.get("result", "")[:4000]
        to_agent = data.get("to_agent", "")
        header = f"**{to_agent}** [Heartbeat]" if to_agent else "[Heartbeat]"
        text = f"{header}\n{result}"

        if not self.app or not self.app.bot:
            return

        from telegram.constants import ParseMode

        html = md_to_html(text)
        for chat_id in set(self._user_chat_cache.values()):
            try:
                await self.app.bot.send_message(
                    chat_id=chat_id, text=html, parse_mode=ParseMode.HTML,
                )
            except Exception:
                try:
                    await self.app.bot.send_message(chat_id=chat_id, text=text)
                except Exception as exc:
                    logger.warning(
                        "Failed to broadcast heartbeat to %s: %s", chat_id, exc
                    )

    async def _handle_message(self, update: Any, context: Any) -> None:
        """Handle text messages — route to Runner with streaming typewriter effect."""
        from telegram.constants import ChatAction
        from ..agents.invocation_context import RunConfig

        from ..sessions.constants import DEFAULT_USER_ID

        user_message = update.message.text
        user_id = DEFAULT_USER_ID
        session_id = await self._get_session_id_for_user(user_id)

        # Cache user_id → chat_id for scheduled task delivery
        self._user_chat_cache[user_id] = update.effective_chat.id

        runner = self._get_runner_for_user(user_id)
        logger.info(
            "Telegram message from %s [%s]: %s",
            user_id, runner.agent.name, user_message[:50],
        )

        # Send typing indicator
        try:
            await context.bot.send_chat_action(
                chat_id=update.effective_chat.id, action=ChatAction.TYPING,
            )
        except Exception:
            pass

        # Multi-agent: prefix with agent name for clarity
        prefix = f"**{runner.agent.name}**:\n" if self.multi_agent else ""

        # Send placeholder message
        placeholder = await update.message.reply_text(
            md_to_html(f"{prefix}...") if prefix else "...",
            parse_mode="HTML" if prefix else None,
        )

        try:
            # Shared buffer between producer and consumer.
            # _turn_offset tracks where the current LLM turn starts in
            # the buffer so that multi-turn tool-use responses accumulate
            # instead of overwriting each other.
            buffer: dict[str, Any] = {
                "text": "",
                "done": False,
                "error": None,
                "_turn_offset": 0,
            }

            # Producer: collect LLM streaming chunks into buffer
            async def producer() -> None:
                try:
                    async for event in runner.run(
                        user_id=user_id,
                        session_id=session_id,
                        message=user_message,
                        run_config=RunConfig(
                            streaming=True,
                            max_message_length=3000,
                            context={
                                "channel": "telegram",
                                "user_id": user_id,
                            },
                        ),
                    ):
                        if event.partial and event.content and event.content.parts:
                            for part in event.content.parts:
                                if part.text:
                                    buffer["text"] += part.text
                        elif event.error_code:
                            buffer["error"] = (
                                f"{event.error_code}: {event.error_message or ''}"
                            )
                        elif (
                            not event.partial
                            and event.content
                            and event.content.parts
                        ):
                            # Show tool name + compact response summary.
                            # The Agent's final text reply still provides the
                            # human-friendly summary; the tool echo here gives
                            # observability into what actually ran (required
                            # by TestProducerToolVisibility invariant).
                            tool_lines: list[str] = []
                            for part in event.content.parts:
                                if part.function_call:
                                    fc = part.function_call
                                    tool_lines.append(f"\U0001f527 `{fc.name}`")
                                elif part.function_response:
                                    fr = part.function_response
                                    resp = fr.response
                                    if isinstance(resp, dict):
                                        resp_text = " ".join(
                                            f"{k}={v}" for k, v in resp.items()
                                        )
                                    else:
                                        resp_text = str(resp) if resp is not None else ""
                                    if resp_text:
                                        tool_lines.append(
                                            f"\u2705 `{fr.name}` \u2192 {resp_text}"
                                        )
                                    else:
                                        tool_lines.append(f"\u2705 `{fr.name}`")
                            if tool_lines:
                                buffer["text"] += "\n".join(tool_lines) + "\n\n"
                                buffer["_turn_offset"] = len(buffer["text"])

                            # Final (complete) text response for this turn.
                            # Replace only the current turn's portion
                            # (from _turn_offset onward) to preserve
                            # text from previous turns in multi-turn
                            # tool-use conversations.
                            final_text = ""
                            for part in event.content.parts:
                                if part.text:
                                    final_text += part.text
                            if final_text:
                                # Strip L2 audit block at producer stage
                                # so consumer never displays it
                                try:
                                    from ..l2_splitter import split_l2
                                    final_text = split_l2(final_text).l1
                                except Exception:
                                    pass
                                kept = buffer["text"][: buffer["_turn_offset"]]
                                buffer["text"] = kept + final_text + "\n\n"
                                buffer["_turn_offset"] = len(buffer["text"])
                except Exception as e:
                    logger.error("Telegram producer error: %s", e)
                    buffer["error"] = str(e)
                finally:
                    buffer["done"] = True

            # Consumer: periodically update Telegram message (typewriter effect)
            # Supports multi-message: when content exceeds _CHUNK_LIMIT,
            # the current message is finalized and a new one is created.
            async def consumer() -> None:
                from telegram.constants import ParseMode

                last_displayed = ""
                last_len = 0
                current_msg = placeholder
                msg_offset = 0          # char offset where current msg starts
                overflow_msgs: list[Any] = []  # extra messages for long responses

                while not buffer["done"] or len(buffer["text"]) > last_len:
                    current = buffer["text"]
                    # Strip L2 audit block in real-time so it never flickers
                    try:
                        from ..l2_splitter import split_l2
                        current = split_l2(current).l1
                    except Exception:
                        pass

                    if current and current != last_displayed:
                        # Progressive display: advance to next natural break
                        target_len = min(
                            last_len + max(len(current) // 4, 20),
                            len(current),
                        )
                        display_end = target_len
                        for i in range(
                            target_len, min(target_len + 30, len(current))
                        ):
                            if current[i] in "\n.。!！?？,，:：;；":
                                display_end = i + 1
                                break

                        display_text = current[:display_end]
                        if display_text != last_displayed:
                            # Text for the current message (from msg_offset)
                            chunk_text = display_text[msg_offset:]
                            show = (
                                (prefix + chunk_text)
                                if msg_offset == 0
                                else chunk_text
                            )

                            # If exceeding limit, finalize and start new msg
                            if len(show) > _CHUNK_LIMIT:
                                # Find a clean break point
                                bp = show[:_CHUNK_LIMIT].rfind("\n\n")
                                if bp < _CHUNK_LIMIT * 0.3:
                                    bp = show[:_CHUNK_LIMIT].rfind("\n")
                                if bp < _CHUNK_LIMIT * 0.3:
                                    bp = _CHUNK_LIMIT
                                # Finalize current message
                                await _edit_html(
                                    context.bot,
                                    current_msg.chat_id,
                                    current_msg.message_id,
                                    show[:bp],
                                )
                                # Start new message
                                msg_offset += bp - (
                                    len(prefix) if msg_offset == 0 else 0
                                )
                                try:
                                    current_msg = await update.message.reply_text(
                                        "..."
                                    )
                                    overflow_msgs.append(current_msg)
                                except Exception:
                                    pass
                                # Re-derive chunk for new message
                                chunk_text = display_text[msg_offset:]
                                show = chunk_text

                            html = md_to_html(show)
                            try:
                                await context.bot.edit_message_text(
                                    chat_id=current_msg.chat_id,
                                    message_id=current_msg.message_id,
                                    text=html,
                                    parse_mode=ParseMode.HTML,
                                )
                            except Exception as _edit_err:
                                from telegram.error import RetryAfter as _RA
                                if isinstance(_edit_err, _RA):
                                    logger.warning("Flood control in consumer: %ss", _edit_err.retry_after)
                                    await _notify_flood_control(context.bot, current_msg.chat_id, _edit_err.retry_after)
                                    await asyncio.sleep(min(_edit_err.retry_after, 30))
                                else:
                                    try:
                                        await context.bot.edit_message_text(
                                            chat_id=current_msg.chat_id,
                                            message_id=current_msg.message_id,
                                            text=show,
                                        )
                                    except Exception:
                                        pass
                            last_displayed = display_text
                            last_len = len(display_text)

                    await asyncio.sleep(5.0)

                # Store overflow msg list for final render to re-use
                buffer["_overflow_msgs"] = overflow_msgs
                buffer["_msg_offset"] = msg_offset
                buffer["_current_msg"] = current_msg

            # Run producer and consumer in parallel
            await asyncio.gather(producer(), consumer())

            # Final result — strip any remaining L2 audit block
            final_response = buffer["text"] or ""
            if buffer["error"]:
                final_response = final_response + f"\n\n\u26a0\ufe0f Error: {buffer['error']}" if final_response else f"\u26a0\ufe0f Error: {buffer['error']}"
            if not final_response:
                final_response = "(empty response)"
            try:
                from ..l2_splitter import split_l2
                final_response = split_l2(final_response).l1
            except Exception:
                pass
            final_response = prefix + final_response

            # Final HTML rendering — markdown-aware chunking
            chunks = _chunk_markdown(final_response)
            # Update first message (the placeholder)
            await _edit_html(
                context.bot, placeholder.chat_id, placeholder.message_id,
                chunks[0],
            )
            # Send remaining chunks as new messages
            # Re-use overflow messages created during streaming where possible
            overflow = buffer.get("_overflow_msgs", [])
            for ci, chunk in enumerate(chunks[1:]):
                if ci < len(overflow):
                    # Re-use existing overflow message
                    await _edit_html(
                        context.bot,
                        overflow[ci].chat_id,
                        overflow[ci].message_id,
                        chunk,
                    )
                else:
                    await _reply_html(update.message, chunk)

        except Exception as e:
            logger.error("Telegram handler error: %s", e)
            try:
                await context.bot.edit_message_text(
                    chat_id=placeholder.chat_id,
                    message_id=placeholder.message_id,
                    text=f"Error: {e}",
                )
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start_in_thread(self) -> None:
        """Start Telegram Long Polling in a background thread.

        Creates an independent event loop so it doesn't block
        the main asyncio loop (e.g. uvicorn).
        """

        def _run() -> None:
            if sys.platform == "win32":
                asyncio.set_event_loop_policy(
                    asyncio.WindowsProactorEventLoopPolicy()
                )
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self.build_application()
            self._running = True
            logger.info("Telegram Bot polling started")
            from telegram import Update

            self.app.run_polling(allowed_updates=Update.ALL_TYPES)

        self._thread = threading.Thread(
            target=_run, daemon=True, name="telegram-bot",
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop Telegram Bot polling."""
        self._running = False
        if self.app and self._loop:
            try:
                asyncio.run_coroutine_threadsafe(
                    self.app.stop(), self._loop,
                ).result(timeout=5)
            except Exception:
                pass
        logger.info("Telegram Bot stopped")
