"""Tests for Session persistence, title, auto-resume, and unified user_id (Doc 20).

Verifies:
- Session model title + created_at fields
- DatabaseSessionService migration and new-field handling
- InMemorySessionService title support + sorted list_sessions
- Auto title generation in Runner
- Auto-resume in CLI chat_loop (via list_sessions order)
- Unified DEFAULT_USER_ID across channels
- Telegram session management commands (/sessions, /new, /session)
"""

import time
import pytest

aiosqlite = pytest.importorskip("aiosqlite")

from soulbot.agents import LlmAgent
from soulbot.events.event import Content, Event, Part
from soulbot.events.event_actions import EventActions
from soulbot.models.base_llm import BaseLlm
from soulbot.models.llm_request import LlmRequest, LlmResponse
from soulbot.models.registry import ModelRegistry
from soulbot.runners import Runner
from soulbot.sessions import InMemorySessionService, Session, State
from soulbot.sessions.constants import DEFAULT_USER_ID
from soulbot.sessions.database_session_service import DatabaseSessionService


# ---------------------------------------------------------------------------
# Mock LLM for Runner tests
# ---------------------------------------------------------------------------


class PersistMockLlm(BaseLlm):
    """Mock LLM that returns canned responses."""

    _responses: list[LlmResponse] = []

    @classmethod
    def set_responses(cls, responses: list[LlmResponse]):
        cls._responses = list(responses)

    @classmethod
    def supported_models(cls) -> list[str]:
        return [r"persist-mock-.*"]

    async def generate_content_async(self, llm_request, *, stream=False):
        if self._responses:
            yield self._responses.pop(0)
        else:
            yield LlmResponse(
                content=Content(role="model", parts=[Part(text="default reply")])
            )


@pytest.fixture(autouse=True)
def setup_persist_mock():
    ModelRegistry.reset()
    ModelRegistry.register(r"persist-mock-.*", PersistMockLlm)
    yield
    ModelRegistry.reset()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def db_service(tmp_path):
    db_path = str(tmp_path / "test_persist.db")
    return DatabaseSessionService(db_path=db_path)


@pytest.fixture
def mem_service():
    return InMemorySessionService()


def _make_agent(name="test_agent"):
    return LlmAgent(
        name=name,
        model="persist-mock-model",
        instruction="You are a test agent.",
    )


def _resp(text: str) -> LlmResponse:
    return LlmResponse(content=Content(role="model", parts=[Part(text=text)]))


# ===================================================================
# TestSessionTitleCreatedAt — Session model new fields
# ===================================================================


class TestSessionTitleCreatedAt:
    def test_defaults(self):
        s = Session()
        assert s.title == ""
        assert s.created_at > 0

    def test_title_set(self):
        s = Session(title="Hello World")
        assert s.title == "Hello World"

    def test_created_at_auto(self):
        before = time.time()
        s = Session()
        after = time.time()
        assert before <= s.created_at <= after

    def test_created_at_custom(self):
        s = Session(created_at=1000.0)
        assert s.created_at == 1000.0

    def test_backward_compat_no_title(self):
        """Session without title/created_at still works (defaults)."""
        s = Session(id="s1", app_name="app", user_id="u1")
        assert s.title == ""
        assert s.created_at > 0


# ===================================================================
# TestDatabaseSessionMigration — DB schema migration
# ===================================================================


class TestDatabaseSessionMigration:
    @pytest.mark.asyncio
    async def test_create_with_title(self, db_service):
        s = await db_service.create_session("app", "u1", agent_name="test", session_id="s1", title="My Chat")
        assert s.title == "My Chat"
        assert s.created_at > 0

    @pytest.mark.asyncio
    async def test_get_reads_title(self, db_service):
        await db_service.create_session("app", "u1", agent_name="test", session_id="s1", title="Chat 1")
        loaded = await db_service.get_session("app", "u1", "s1")
        assert loaded.title == "Chat 1"
        assert loaded.created_at > 0

    @pytest.mark.asyncio
    async def test_list_reads_title(self, db_service):
        await db_service.create_session("app", "u1", agent_name="test", session_id="s1", title="Chat A")
        await db_service.create_session("app", "u1", agent_name="test", session_id="s2", title="Chat B")
        sessions = await db_service.list_sessions("app", "u1", agent_name="test")
        titles = {s.title for s in sessions}
        assert titles == {"Chat A", "Chat B"}

    @pytest.mark.asyncio
    async def test_update_session_title(self, db_service):
        await db_service.create_session("app", "u1", agent_name="test", session_id="s1", title="Old")
        await db_service.update_session_title("app", "u1", "s1", "New Title")
        loaded = await db_service.get_session("app", "u1", "s1")
        assert loaded.title == "New Title"

    @pytest.mark.asyncio
    async def test_alter_idempotent(self, db_service):
        """ALTER TABLE is idempotent — calling _create_tables twice doesn't fail."""
        # First call creates tables
        await db_service.create_session("app", "u1", agent_name="test", session_id="s1")
        # Force re-init
        db_service._initialized = False
        # Second call should not fail (ALTER already-exists is caught)
        await db_service.create_session("app", "u1", agent_name="test", session_id="s2")
        sessions = await db_service.list_sessions("app", "u1", agent_name="test")
        assert len(sessions) == 2

    @pytest.mark.asyncio
    async def test_default_title_empty(self, db_service):
        """create_session without title defaults to empty string."""
        s = await db_service.create_session("app", "u1", agent_name="test", session_id="s1")
        assert s.title == ""


# ===================================================================
# TestInMemorySessionTitle — InMemory adapter
# ===================================================================


class TestInMemorySessionTitle:
    @pytest.mark.asyncio
    async def test_create_with_title(self, mem_service):
        s = await mem_service.create_session("app", "u1", agent_name="test", title="My Chat")
        assert s.title == "My Chat"

    @pytest.mark.asyncio
    async def test_update_session_title(self, mem_service):
        s = await mem_service.create_session("app", "u1", agent_name="test", session_id="s1", title="Old")
        await mem_service.update_session_title("app", "u1", "s1", "New")
        loaded = await mem_service.get_session("app", "u1", "s1")
        assert loaded.title == "New"

    @pytest.mark.asyncio
    async def test_list_sorted_by_update_time(self, mem_service):
        s1 = await mem_service.create_session("app", "u1", agent_name="test", session_id="s1", title="Old")
        s1.last_update_time = 100.0
        s2 = await mem_service.create_session("app", "u1", agent_name="test", session_id="s2", title="New")
        s2.last_update_time = 200.0
        sessions = await mem_service.list_sessions("app", "u1", agent_name="test")
        assert sessions[0].id == "s2"  # Most recent first
        assert sessions[1].id == "s1"


# ===================================================================
# TestAutoTitle — Runner auto-generates title
# ===================================================================


class TestAutoTitle:
    @pytest.mark.asyncio
    async def test_auto_title_from_message(self):
        svc = InMemorySessionService()
        agent = _make_agent()
        runner = Runner(agent=agent, app_name=agent.name, session_service=svc)
        PersistMockLlm.set_responses([_resp("Hi!")])
        async for _ in runner.run(user_id="u1", session_id="s1", message="Hello world"):
            pass
        s = await svc.get_session(agent.name, "u1", "s1")
        assert s.title == "Hello world"

    @pytest.mark.asyncio
    async def test_auto_title_truncated(self):
        svc = InMemorySessionService()
        agent = _make_agent()
        runner = Runner(agent=agent, app_name=agent.name, session_service=svc)
        long_msg = "A" * 50
        PersistMockLlm.set_responses([_resp("Reply")])
        async for _ in runner.run(user_id="u1", session_id="s1", message=long_msg):
            pass
        s = await svc.get_session(agent.name, "u1", "s1")
        assert s.title == "A" * 30 + "..."
        assert len(s.title) == 33

    @pytest.mark.asyncio
    async def test_existing_session_title_not_overwritten(self):
        svc = InMemorySessionService()
        agent = _make_agent()
        runner = Runner(agent=agent, app_name=agent.name, session_service=svc)
        # First message creates session with title
        PersistMockLlm.set_responses([_resp("R1"), _resp("R2")])
        async for _ in runner.run(user_id="u1", session_id="s1", message="First topic"):
            pass
        # Second message reuses existing session
        async for _ in runner.run(user_id="u1", session_id="s1", message="Second topic"):
            pass
        s = await svc.get_session(agent.name, "u1", "s1")
        assert s.title == "First topic"

    @pytest.mark.asyncio
    async def test_auto_title_short_message(self):
        svc = InMemorySessionService()
        agent = _make_agent()
        runner = Runner(agent=agent, app_name=agent.name, session_service=svc)
        PersistMockLlm.set_responses([_resp("OK")])
        async for _ in runner.run(user_id="u1", session_id="s1", message="Hi"):
            pass
        s = await svc.get_session(agent.name, "u1", "s1")
        assert s.title == "Hi"


# ===================================================================
# TestAutoResume — list_sessions ordering for resume
# ===================================================================


class TestAutoResume:
    @pytest.mark.asyncio
    async def test_list_sessions_order_db(self, db_service):
        """Most recently updated session comes first."""
        s1 = await db_service.create_session("app", "u1", agent_name="test", session_id="s1", title="Old")
        # Add event to s1 to update its timestamp
        e = Event(author="user", content=Content(role="user", parts=[Part(text="hi")]))
        await db_service.append_event(s1, e)
        # Create s2 after s1
        import asyncio
        await asyncio.sleep(0.01)
        s2 = await db_service.create_session("app", "u1", agent_name="test", session_id="s2", title="New")
        sessions = await db_service.list_sessions("app", "u1", agent_name="test")
        # s2 or s1 could be first depending on timing; just check ordering
        assert len(sessions) == 2
        assert sessions[0].last_update_time >= sessions[1].last_update_time

    @pytest.mark.asyncio
    async def test_empty_list_no_resume(self, db_service):
        """No sessions → empty list."""
        sessions = await db_service.list_sessions("app", "u1", agent_name="test")
        assert sessions == []

    @pytest.mark.asyncio
    async def test_list_sessions_order_inmemory(self, mem_service):
        s1 = await mem_service.create_session("app", "u1", agent_name="test", session_id="s1")
        s1.last_update_time = 100.0
        s2 = await mem_service.create_session("app", "u1", agent_name="test", session_id="s2")
        s2.last_update_time = 200.0
        sessions = await mem_service.list_sessions("app", "u1", agent_name="test")
        assert sessions[0].id == "s2"

    @pytest.mark.asyncio
    async def test_resume_gets_correct_session(self, mem_service):
        """Simulates CLI auto-resume: pick sessions[0]."""
        s1 = await mem_service.create_session("app", "u1", agent_name="test", session_id="s1", title="Old")
        s1.last_update_time = 100.0
        s2 = await mem_service.create_session("app", "u1", agent_name="test", session_id="s2", title="Recent")
        s2.last_update_time = 200.0
        sessions = await mem_service.list_sessions("app", "u1", agent_name="test")
        resumed = sessions[0]
        assert resumed.id == "s2"
        assert resumed.title == "Recent"


# ===================================================================
# TestUnifiedUserId — DEFAULT_USER_ID consistency
# ===================================================================


class TestUnifiedUserId:
    def test_default_user_id_value(self):
        assert DEFAULT_USER_ID == "default"

    def test_importable_from_sessions(self):
        from soulbot.sessions import DEFAULT_USER_ID as uid
        assert uid == "default"

    def test_resolve_functions_importable(self):
        from soulbot.sessions import resolve_cli_name, resolve_db_path
        assert callable(resolve_cli_name)
        assert callable(resolve_db_path)


# ===================================================================
# TestTelegramSessionCommands — mock-based Telegram command tests
# ===================================================================


class _FakeMessage:
    """Minimal mock for Telegram Message."""

    def __init__(self):
        self.replies = []

    async def reply_text(self, text, **kwargs):
        self.replies.append(text)
        return self


class _FakeUpdate:
    """Minimal mock for Telegram Update."""

    def __init__(self, msg=None):
        self.message = msg or _FakeMessage()
        self.effective_user = type("User", (), {"id": 12345})()
        self.effective_chat = type("Chat", (), {"id": 67890})()


class _FakeContext:
    """Minimal mock for Telegram CallbackContext."""

    def __init__(self, args=None):
        self.args = args or []
        self.bot = _FakeBot()


class _FakeBot:
    """Minimal mock for Telegram Bot."""

    async def send_chat_action(self, **kwargs):
        pass

    async def edit_message_text(self, **kwargs):
        pass

    async def send_message(self, **kwargs):
        pass


class TestTelegramSessionCommands:
    def _make_bridge(self, svc=None, runners=None):
        from unittest.mock import MagicMock

        svc = svc or InMemorySessionService()
        agent = _make_agent()
        runner = MagicMock()
        runner.agent = agent
        runner.app_name = agent.name

        from soulbot.connect.telegram import TelegramBridge

        bridge = TelegramBridge(
            runner=runner,
            bot_token="fake-token",
            session_service=svc,
            runners=runners,
        )
        return bridge, svc

    @pytest.mark.asyncio
    async def test_sessions_empty(self):
        bridge, svc = self._make_bridge()
        update = _FakeUpdate()
        ctx = _FakeContext()
        await bridge._handle_sessions(update, ctx)
        assert "No sessions found" in update.message.replies[0]

    @pytest.mark.asyncio
    async def test_sessions_lists(self):
        svc = InMemorySessionService()
        await svc.create_session("test_agent", DEFAULT_USER_ID, agent_name="test_agent", session_id="s1", title="Chat A")
        await svc.create_session("test_agent", DEFAULT_USER_ID, agent_name="test_agent", session_id="s2", title="Chat B")
        bridge, _ = self._make_bridge(svc=svc)
        update = _FakeUpdate()
        ctx = _FakeContext()
        await bridge._handle_sessions(update, ctx)
        reply = update.message.replies[0]
        assert "Chat A" in reply or "Chat B" in reply

    @pytest.mark.asyncio
    async def test_new_session(self):
        bridge, svc = self._make_bridge()
        update = _FakeUpdate()
        ctx = _FakeContext()
        await bridge._handle_new_session(update, ctx)
        assert "New session created" in update.message.replies[0]
        # User should have a new session_id
        assert DEFAULT_USER_ID in bridge._user_session

    @pytest.mark.asyncio
    async def test_session_switch(self):
        svc = InMemorySessionService()
        await svc.create_session("test_agent", DEFAULT_USER_ID, agent_name="test_agent", session_id="s1", title="Session 1")
        await svc.create_session("test_agent", DEFAULT_USER_ID, agent_name="test_agent", session_id="s2", title="Session 2")
        bridge, _ = self._make_bridge(svc=svc)
        update = _FakeUpdate()
        ctx = _FakeContext(args=["1"])
        await bridge._handle_session_switch(update, ctx)
        reply = update.message.replies[0]
        assert "Switched to session" in reply

    @pytest.mark.asyncio
    async def test_session_switch_invalid(self):
        svc = InMemorySessionService()
        bridge, _ = self._make_bridge(svc=svc)
        update = _FakeUpdate()
        ctx = _FakeContext(args=["99"])
        await bridge._handle_session_switch(update, ctx)
        reply = update.message.replies[0]
        assert "Invalid session number" in reply
