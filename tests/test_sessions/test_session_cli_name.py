"""Tests for Doc 21 — CLI_NAME, data/ directory, last_agent soft classification.

Verifies:
- resolve_cli_name() from env vars
- resolve_db_path() creates data/ directory
- Session model last_agent field
- DatabaseSessionService last_agent CRUD + list_sessions filter
- InMemorySessionService last_agent CRUD + list_sessions filter
- Runner sets/updates last_agent
- Default resume two-layer logic
- Telegram auto-switch agent on session switch
- Web API last_agent in summary/detail
"""

import os
import time

import pytest

aiosqlite = pytest.importorskip("aiosqlite")

from soulbot.agents import LlmAgent
from soulbot.events.event import Content, Event, Part
from soulbot.models.base_llm import BaseLlm
from soulbot.models.llm_request import LlmResponse
from soulbot.models.registry import ModelRegistry
from soulbot.runners import Runner
from soulbot.sessions import InMemorySessionService, Session
from soulbot.sessions.constants import (
    DEFAULT_USER_ID,
    resolve_cli_name,
    resolve_db_path,
)
from soulbot.sessions.database_session_service import DatabaseSessionService


# ---------------------------------------------------------------------------
# Mock LLM
# ---------------------------------------------------------------------------


class Doc21MockLlm(BaseLlm):
    _responses: list[LlmResponse] = []

    @classmethod
    def set_responses(cls, responses):
        cls._responses = list(responses)

    @classmethod
    def supported_models(cls):
        return [r"doc21-mock-.*"]

    async def generate_content_async(self, llm_request, *, stream=False):
        if self._responses:
            yield self._responses.pop(0)
        else:
            yield LlmResponse(
                content=Content(role="model", parts=[Part(text="default")])
            )


@pytest.fixture(autouse=True)
def setup_mock():
    ModelRegistry.reset()
    ModelRegistry.register(r"doc21-mock-.*", Doc21MockLlm)
    yield
    ModelRegistry.reset()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def db_svc(tmp_path):
    return DatabaseSessionService(str(tmp_path / "test21.db"))


@pytest.fixture
def mem_svc():
    return InMemorySessionService()


def _agent(name="hello_agent"):
    return LlmAgent(name=name, model="doc21-mock-model", instruction="test")


def _resp(text="ok"):
    return LlmResponse(content=Content(role="model", parts=[Part(text=text)]))


# ===================================================================
# TestResolveCliName
# ===================================================================


class TestResolveCliName:
    def test_explicit_cli_name(self, monkeypatch):
        monkeypatch.setenv("CLI_NAME", "my_custom_cli")
        assert resolve_cli_name() == "my_custom_cli"

    def test_claude_cli_inferred(self, monkeypatch):
        monkeypatch.delenv("CLI_NAME", raising=False)
        monkeypatch.setenv("CLAUDE_CLI", "true")
        monkeypatch.delenv("OPENCODE_CLI", raising=False)
        monkeypatch.delenv("GEMINI_CLI", raising=False)
        assert resolve_cli_name() == "claude_cli"

    def test_opencode_cli_inferred(self, monkeypatch):
        monkeypatch.delenv("CLI_NAME", raising=False)
        monkeypatch.delenv("CLAUDE_CLI", raising=False)
        monkeypatch.setenv("OPENCODE_CLI", "true")
        monkeypatch.delenv("GEMINI_CLI", raising=False)
        assert resolve_cli_name() == "opencode_cli"

    def test_gemini_cli_inferred(self, monkeypatch):
        monkeypatch.delenv("CLI_NAME", raising=False)
        monkeypatch.delenv("CLAUDE_CLI", raising=False)
        monkeypatch.delenv("OPENCODE_CLI", raising=False)
        monkeypatch.setenv("GEMINI_CLI", "true")
        assert resolve_cli_name() == "gemini_cli"

    def test_default_fallback(self, monkeypatch):
        monkeypatch.delenv("CLI_NAME", raising=False)
        monkeypatch.delenv("CLAUDE_CLI", raising=False)
        monkeypatch.delenv("OPENCODE_CLI", raising=False)
        monkeypatch.delenv("GEMINI_CLI", raising=False)
        monkeypatch.delenv("OPENCLAW_CLI", raising=False)
        assert resolve_cli_name() == "default_cli"


# ===================================================================
# TestResolveDbPath
# ===================================================================


class TestResolveDbPath:
    def test_with_agents_dir(self, tmp_path):
        path = resolve_db_path(str(tmp_path))
        assert "data" in path
        assert path.endswith("soulbot_sessions.db")
        assert (tmp_path / "data").is_dir()

    def test_without_agents_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        path = resolve_db_path()
        assert path.endswith("soulbot_sessions.db")
        assert (tmp_path / "data").is_dir()

    def test_data_dir_auto_created(self, tmp_path):
        agents = tmp_path / "my_agents"
        agents.mkdir()
        path = resolve_db_path(str(agents))
        assert (agents / "data").is_dir()


# ===================================================================
# TestLastAgent — Session model
# ===================================================================


class TestLastAgent:
    def test_default_empty(self):
        s = Session()
        assert s.last_agent == ""

    def test_set_last_agent(self):
        s = Session(last_agent="hello_agent")
        assert s.last_agent == "hello_agent"

    @pytest.mark.asyncio
    async def test_db_create_with_last_agent(self, db_svc):
        s = await db_svc.create_session(
            "cli", "u1", session_id="s1", agent_name="hello"
        )
        assert s.last_agent == "hello"

    @pytest.mark.asyncio
    async def test_db_get_reads_last_agent(self, db_svc):
        await db_svc.create_session(
            "cli", "u1", session_id="s1", agent_name="hello"
        )
        loaded = await db_svc.get_session("cli", "u1", "s1")
        assert loaded.last_agent == "hello"

    @pytest.mark.asyncio
    async def test_db_update_last_agent(self, db_svc):
        await db_svc.create_session(
            "cli", "u1", session_id="s1", agent_name="hello"
        )
        await db_svc.update_last_agent("cli", "u1", "s1", "weather")
        loaded = await db_svc.get_session("cli", "u1", "s1")
        assert loaded.last_agent == "weather"

    @pytest.mark.asyncio
    async def test_inmemory_create_with_last_agent(self, mem_svc):
        s = await mem_svc.create_session(
            "cli", "u1", session_id="s1", agent_name="hello"
        )
        assert s.last_agent == "hello"

    @pytest.mark.asyncio
    async def test_inmemory_update_last_agent(self, mem_svc):
        await mem_svc.create_session(
            "cli", "u1", session_id="s1", agent_name="hello"
        )
        await mem_svc.update_last_agent("cli", "u1", "s1", "weather")
        loaded = await mem_svc.get_session("cli", "u1", "s1")
        assert loaded.last_agent == "weather"


# ===================================================================
# TestListSessionsFilter — agent_name filter
# ===================================================================


class TestListSessionsFilter:
    @pytest.mark.asyncio
    async def test_no_filter_returns_all(self, mem_svc):
        await mem_svc.create_session("cli", "u1", session_id="s1", agent_name="hello")
        await mem_svc.create_session("cli", "u1", session_id="s2", agent_name="weather")
        sessions = await mem_svc.list_all_sessions("cli", "u1")
        assert len(sessions) == 2

    @pytest.mark.asyncio
    async def test_filter_by_agent(self, mem_svc):
        await mem_svc.create_session("cli", "u1", session_id="s1", agent_name="hello")
        await mem_svc.create_session("cli", "u1", session_id="s2", agent_name="weather")
        sessions = await mem_svc.list_sessions("cli", "u1", agent_name="hello")
        assert len(sessions) == 1
        assert sessions[0].last_agent == "hello"

    @pytest.mark.asyncio
    async def test_filter_empty_result(self, mem_svc):
        await mem_svc.create_session("cli", "u1", session_id="s1", agent_name="hello")
        sessions = await mem_svc.list_sessions("cli", "u1", agent_name="nonexistent")
        assert len(sessions) == 0

    @pytest.mark.asyncio
    async def test_db_filter_by_agent(self, db_svc):
        await db_svc.create_session("cli", "u1", session_id="s1", agent_name="hello")
        await db_svc.create_session("cli", "u1", session_id="s2", agent_name="weather")
        sessions = await db_svc.list_sessions("cli", "u1", agent_name="hello")
        assert len(sessions) == 1
        assert sessions[0].last_agent == "hello"

    @pytest.mark.asyncio
    async def test_db_no_filter_returns_all(self, db_svc):
        await db_svc.create_session("cli", "u1", session_id="s1", agent_name="hello")
        await db_svc.create_session("cli", "u1", session_id="s2", agent_name="weather")
        sessions = await db_svc.list_all_sessions("cli", "u1")
        assert len(sessions) == 2


# ===================================================================
# TestSessionCrossAgent — sessions shared across agents
# ===================================================================


class TestSessionCrossAgent:
    @pytest.mark.asyncio
    async def test_same_cli_different_agents_share_pool(self, mem_svc):
        """Sessions under same CLI are shared regardless of last_agent."""
        await mem_svc.create_session("claude_cli", "u1", session_id="s1", agent_name="hello")
        await mem_svc.create_session("claude_cli", "u1", session_id="s2", agent_name="weather")
        all_sessions = await mem_svc.list_all_sessions("claude_cli", "u1")
        assert len(all_sessions) == 2

    @pytest.mark.asyncio
    async def test_runner_updates_last_agent(self):
        svc = InMemorySessionService()
        agent_a = _agent("agent_a")
        agent_b = _agent("agent_b")
        # Create session with agent_a
        runner_a = Runner(agent=agent_a, app_name="cli", session_service=svc)
        Doc21MockLlm.set_responses([_resp("Hi from A")])
        async for _ in runner_a.run(user_id="u1", session_id="s1", message="Hello"):
            pass
        s = await svc.get_session("cli", "u1", "s1")
        assert s.last_agent == "agent_a"

        # Reuse same session with agent_b → last_agent updated
        runner_b = Runner(agent=agent_b, app_name="cli", session_service=svc)
        Doc21MockLlm.set_responses([_resp("Hi from B")])
        async for _ in runner_b.run(user_id="u1", session_id="s1", message="Hello"):
            pass
        s = await svc.get_session("cli", "u1", "s1")
        assert s.last_agent == "agent_b"

    @pytest.mark.asyncio
    async def test_select_pins_to_top(self, mem_svc):
        """Selecting and using a historical session updates last_update_time."""
        s1 = await mem_svc.create_session("cli", "u1", session_id="s1", agent_name="hello")
        s1.last_update_time = 100.0
        s2 = await mem_svc.create_session("cli", "u1", session_id="s2", agent_name="hello")
        s2.last_update_time = 200.0
        # s2 is on top
        sessions = await mem_svc.list_all_sessions("cli", "u1")
        assert sessions[0].id == "s2"
        # Append event to s1 → its time becomes latest
        e = Event(author="user", content=Content(role="user", parts=[Part(text="hi")]))
        await mem_svc.append_event(s1, e)
        sessions = await mem_svc.list_all_sessions("cli", "u1")
        assert sessions[0].id == "s1"  # s1 is now on top

    @pytest.mark.asyncio
    async def test_cross_agent_resume(self, mem_svc):
        """When current agent has no session, resume from another agent."""
        s1 = await mem_svc.create_session("cli", "u1", session_id="s1", agent_name="weather")
        s1.last_update_time = 100.0
        # hello_agent has no sessions
        hello_sessions = await mem_svc.list_sessions("cli", "u1", agent_name="hello")
        assert len(hello_sessions) == 0
        # Global fallback finds weather's session
        all_sessions = await mem_svc.list_all_sessions("cli", "u1")
        assert len(all_sessions) == 1
        assert all_sessions[0].last_agent == "weather"


# ===================================================================
# TestDefaultResume — two-layer resume logic
# ===================================================================


class TestDefaultResume:
    @pytest.mark.asyncio
    async def test_prefer_current_agent_session(self, mem_svc):
        """Layer 1: prefer current agent's session."""
        s1 = await mem_svc.create_session("cli", "u1", session_id="s1", agent_name="hello")
        s1.last_update_time = 100.0
        s2 = await mem_svc.create_session("cli", "u1", session_id="s2", agent_name="weather")
        s2.last_update_time = 200.0
        # hello_agent's session
        hello_sessions = await mem_svc.list_sessions("cli", "u1", agent_name="hello")
        assert len(hello_sessions) == 1
        assert hello_sessions[0].id == "s1"

    @pytest.mark.asyncio
    async def test_fallback_to_global(self, mem_svc):
        """Layer 2: no current agent sessions → fallback to global."""
        s1 = await mem_svc.create_session("cli", "u1", session_id="s1", agent_name="weather")
        s1.last_update_time = 200.0
        # No hello_agent sessions
        hello_sessions = await mem_svc.list_sessions("cli", "u1", agent_name="hello")
        assert len(hello_sessions) == 0
        # Global has weather's session
        all_sessions = await mem_svc.list_all_sessions("cli", "u1")
        assert len(all_sessions) == 1
        assert all_sessions[0].last_agent == "weather"

    @pytest.mark.asyncio
    async def test_empty_list_new_session(self, mem_svc):
        """No sessions at all → start fresh."""
        sessions = await mem_svc.list_sessions("cli", "u1", agent_name="hello")
        assert len(sessions) == 0
        sessions = await mem_svc.list_all_sessions("cli", "u1")
        assert len(sessions) == 0

    @pytest.mark.asyncio
    async def test_selected_becomes_last(self, mem_svc):
        """After selecting and using a session, it becomes the most recent."""
        s1 = await mem_svc.create_session("cli", "u1", session_id="s1", agent_name="hello")
        s1.last_update_time = 100.0
        s2 = await mem_svc.create_session("cli", "u1", session_id="s2", agent_name="hello")
        s2.last_update_time = 200.0
        # s2 is most recent
        sessions = await mem_svc.list_sessions("cli", "u1", agent_name="hello")
        assert sessions[0].id == "s2"
        # Use s1 (simulate with append_event)
        e = Event(author="user", content=Content(role="user", parts=[Part(text="msg")]))
        await mem_svc.append_event(s1, e)
        # Now s1 is most recent
        sessions = await mem_svc.list_sessions("cli", "u1", agent_name="hello")
        assert sessions[0].id == "s1"


# ===================================================================
# TestCliNameInRunner
# ===================================================================


class TestCliNameInRunner:
    @pytest.mark.asyncio
    async def test_runner_app_name_is_cli_name(self):
        agent = _agent("hello")
        svc = InMemorySessionService()
        runner = Runner(agent=agent, app_name="claude_cli", session_service=svc)
        assert runner.app_name == "claude_cli"
        assert runner.agent_name == "hello"

    @pytest.mark.asyncio
    async def test_create_session_uses_cli_name(self):
        agent = _agent("hello")
        svc = InMemorySessionService()
        runner = Runner(agent=agent, app_name="claude_cli", session_service=svc)
        Doc21MockLlm.set_responses([_resp("ok")])
        async for _ in runner.run(user_id="u1", session_id="s1", message="Hi"):
            pass
        # Session should be under claude_cli, not hello
        s = await svc.get_session("claude_cli", "u1", "s1")
        assert s is not None
        assert s.app_name == "claude_cli"
        assert s.last_agent == "hello"

    @pytest.mark.asyncio
    async def test_get_session_uses_cli_name(self):
        agent = _agent("hello")
        svc = InMemorySessionService()
        runner = Runner(agent=agent, app_name="claude_cli", session_service=svc)
        Doc21MockLlm.set_responses([_resp("ok"), _resp("ok2")])
        async for _ in runner.run(user_id="u1", session_id="s1", message="Hello"):
            pass
        # Second run on same session should work
        async for _ in runner.run(user_id="u1", session_id="s1", message="Again"):
            pass
        s = await svc.get_session("claude_cli", "u1", "s1")
        assert len(s.events) == 4  # 2 user + 2 agent


# ===================================================================
# TestTelegramAutoSwitch — session switch auto-switches agent
# ===================================================================


class _FakeMessage:
    def __init__(self):
        self.replies = []

    async def reply_text(self, text, **kwargs):
        self.replies.append(text)
        return self


class _FakeUpdate:
    def __init__(self, msg=None):
        self.message = msg or _FakeMessage()
        self.effective_user = type("User", (), {"id": 12345})()
        self.effective_chat = type("Chat", (), {"id": 67890})()


class _FakeContext:
    def __init__(self, args=None):
        self.args = args or []
        self.bot = _FakeBot()


class _FakeBot:
    async def send_chat_action(self, **kwargs):
        pass

    async def edit_message_text(self, **kwargs):
        pass

    async def send_message(self, **kwargs):
        pass


class TestTelegramAutoSwitch:
    def _make_bridge(self, svc=None, multi=False):
        from unittest.mock import MagicMock
        from soulbot.connect.telegram import TelegramBridge

        svc = svc or InMemorySessionService()
        agent_a = _agent("hello_agent")
        agent_b = _agent("weather_agent")
        runner_a = MagicMock()
        runner_a.agent = agent_a
        runner_a.app_name = "claude_cli"
        runner_b = MagicMock()
        runner_b.agent = agent_b
        runner_b.app_name = "claude_cli"

        runners = {"hello_agent": runner_a, "weather_agent": runner_b} if multi else None
        bridge = TelegramBridge(
            runner=runner_a, bot_token="fake", session_service=svc,
            runners=runners,
        )
        return bridge, svc

    @pytest.mark.asyncio
    async def test_session_switch_auto_switches_agent(self):
        svc = InMemorySessionService()
        s1 = await svc.create_session(
            "claude_cli", DEFAULT_USER_ID, session_id="s1",
            agent_name="hello_agent", title="Chat 1",
        )
        s1.last_update_time = 200.0
        s2 = await svc.create_session(
            "claude_cli", DEFAULT_USER_ID, session_id="s2",
            agent_name="weather_agent", title="Weather",
        )
        s2.last_update_time = 100.0
        bridge, _ = self._make_bridge(svc=svc, multi=True)
        # Switch to session 2 (weather_agent)
        update = _FakeUpdate()
        ctx = _FakeContext(args=["2"])
        await bridge._handle_session_switch(update, ctx)
        assert bridge._user_agent.get(DEFAULT_USER_ID) == "weather_agent"
        assert bridge._user_session.get(DEFAULT_USER_ID) == "s2"

    @pytest.mark.asyncio
    async def test_resume_auto_switches_agent(self):
        svc = InMemorySessionService()
        s1 = await svc.create_session(
            "claude_cli", DEFAULT_USER_ID, session_id="s1",
            agent_name="hello_agent", title="Weather",
        )
        s1.last_update_time = 200.0
        bridge, _ = self._make_bridge(svc=svc, multi=True)
        # hello_agent has a session → bridge resumes it
        sid = await bridge._get_session_id_for_user(DEFAULT_USER_ID)
        assert sid == "s1"

    @pytest.mark.asyncio
    async def test_switch_agent_no_new_session(self):
        svc = InMemorySessionService()
        await svc.create_session(
            "claude_cli", DEFAULT_USER_ID, session_id="s1",
            agent_name="hello_agent",
        )
        bridge, _ = self._make_bridge(svc=svc, multi=True)
        bridge._user_session[DEFAULT_USER_ID] = "s1"
        await bridge._switch_agent(DEFAULT_USER_ID, "weather_agent")
        # Session should NOT change
        assert bridge._user_session[DEFAULT_USER_ID] == "s1"
        assert bridge._user_agent[DEFAULT_USER_ID] == "weather_agent"

    @pytest.mark.asyncio
    async def test_sessions_shows_all_agents(self):
        svc = InMemorySessionService()
        await svc.create_session(
            "claude_cli", DEFAULT_USER_ID, session_id="s1",
            agent_name="hello_agent", title="Hello Chat",
        )
        await svc.create_session(
            "claude_cli", DEFAULT_USER_ID, session_id="s2",
            agent_name="weather_agent", title="Weather Chat",
        )
        bridge, _ = self._make_bridge(svc=svc, multi=True)
        update = _FakeUpdate()
        ctx = _FakeContext()
        await bridge._handle_sessions(update, ctx)
        reply = update.message.replies[0]
        assert "hello_agent" in reply
        assert "weather_agent" in reply
        assert "Hello Chat" in reply
        assert "Weather Chat" in reply


# ===================================================================
# TestWebApiLastAgent — API server last_agent support
# ===================================================================


class TestWebApiLastAgent:
    @pytest.fixture
    def service(self):
        return InMemorySessionService()

    @pytest.fixture
    def app(self, service):
        from soulbot.agents import BaseAgent
        from soulbot.events.event import Content, Event, Part
        from soulbot.server.api_server import create_app

        class StubAgent(BaseAgent):
            async def _run_async_impl(self, ctx):
                yield Event(
                    author=self.name,
                    invocation_id=ctx.invocation_id,
                    content=Content(role="model", parts=[Part(text=f"Hello from {self.name}")]),
                )

        agents = {
            "hello": StubAgent(name="hello", description="Hello agent"),
            "weather": StubAgent(name="weather", description="Weather agent"),
        }
        return create_app(
            agents=agents, session_service=service,
            cli_name="test_cli", dev_ui=False,
        )

    @pytest.fixture
    async def client(self, app):
        from httpx import ASGITransport, AsyncClient
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c

    @pytest.mark.asyncio
    async def test_session_summary_has_last_agent(self, client):
        resp = await client.post(
            "/apps/hello/users/u1/sessions",
            json={"session_id": "s1", "title": "Test"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "last_agent" in data

    @pytest.mark.asyncio
    async def test_session_detail_has_last_agent(self, client):
        await client.post(
            "/apps/hello/users/u1/sessions",
            json={"session_id": "s1"},
        )
        resp = await client.get("/apps/hello/users/u1/sessions/s1")
        assert resp.status_code == 200
        data = resp.json()
        assert "last_agent" in data

    @pytest.mark.asyncio
    async def test_run_sets_last_agent(self, client):
        resp = await client.post("/run", json={
            "app_name": "hello",
            "user_id": "u1",
            "session_id": "auto-agent",
            "new_message": {"role": "user", "parts": [{"text": "Hi"}]},
        })
        assert resp.status_code == 200
        resp = await client.get("/apps/hello/users/u1/sessions/auto-agent")
        data = resp.json()
        assert data["last_agent"] == "hello"

    @pytest.mark.asyncio
    async def test_cli_info_endpoint(self, client):
        resp = await client.get("/cli-info")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cli_name"] == "test_cli"

    @pytest.mark.asyncio
    async def test_list_sessions_agent_filter(self, client, service):
        # Create sessions with different last_agents directly
        await service.create_session(
            "test_cli", "u1", session_id="s1", agent_name="hello",
        )
        await service.create_session(
            "test_cli", "u1", session_id="s2", agent_name="weather",
        )
        # Filter by agent
        resp = await client.get("/apps/hello/users/u1/sessions?agent=hello")
        sessions = resp.json()
        assert len(sessions) == 1
        assert sessions[0]["last_agent"] == "hello"

        # Each agent endpoint returns only that agent's sessions
        resp = await client.get("/apps/hello/users/u1/sessions")
        sessions = resp.json()
        assert len(sessions) == 1
        assert sessions[0]["last_agent"] == "hello"

        resp = await client.get("/apps/weather/users/u1/sessions")
        sessions = resp.json()
        assert len(sessions) == 1
        assert sessions[0]["last_agent"] == "weather"


# ===================================================================
# TestDbMigration — old DB migration
# ===================================================================


class TestDbMigration:
    @pytest.mark.asyncio
    async def test_alter_last_agent_idempotent(self, db_svc):
        """ALTER TABLE for last_agent is idempotent."""
        await db_svc.create_session("cli", "u1", agent_name="", session_id="s1")
        db_svc._initialized = False
        await db_svc.create_session("cli", "u1", agent_name="", session_id="s2")
        sessions = await db_svc.list_all_sessions("cli", "u1")
        assert len(sessions) == 2

    @pytest.mark.asyncio
    async def test_last_agent_default_empty(self, db_svc):
        """Sessions created without last_agent get empty string."""
        s = await db_svc.create_session("cli", "u1", agent_name="", session_id="s1")
        assert s.last_agent == ""

    @pytest.mark.asyncio
    async def test_list_sessions_returns_last_agent(self, db_svc):
        await db_svc.create_session("cli", "u1", session_id="s1", agent_name="hello")
        sessions = await db_svc.list_all_sessions("cli", "u1")
        assert sessions[0].last_agent == "hello"
