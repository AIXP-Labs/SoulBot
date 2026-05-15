"""Tests for FastAPI API Server."""

import json

import pytest
from httpx import ASGITransport, AsyncClient

from soulbot.agents import BaseAgent
from soulbot.events.event import Content, Event, Part
from soulbot.models.base_llm import BaseLlm
from soulbot.models.llm_request import LlmResponse
from soulbot.models.registry import ModelRegistry
from soulbot.server.api_server import create_app
from soulbot.sessions import InMemorySessionService


# ---------------------------------------------------------------------------
# Stub agent & mock LLM
# ---------------------------------------------------------------------------


class StubAgent(BaseAgent):
    async def _run_async_impl(self, ctx):
        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            content=Content(role="model", parts=[Part(text=f"Hello from {self.name}")]),
        )


class MockLlm(BaseLlm):
    _responses: list[LlmResponse] = []

    @classmethod
    def set_responses(cls, responses):
        cls._responses = list(responses)

    @classmethod
    def supported_models(cls):
        return [r"mock-.*"]

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
    ModelRegistry.register(r"mock-.*", MockLlm)
    yield
    ModelRegistry.reset()


@pytest.fixture
def service():
    return InMemorySessionService()


@pytest.fixture
def app(service):
    agents = {
        "greeter": StubAgent(name="greeter", description="A greeter agent"),
        "echo": StubAgent(name="echo", description="An echo agent"),
    }
    return create_app(agents=agents, session_service=service, dev_ui=False)


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# System endpoints
# ---------------------------------------------------------------------------


class TestSystemEndpoints:
    @pytest.mark.asyncio
    async def test_health(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_version(self, client):
        resp = await client.get("/version")
        assert resp.status_code == 200
        assert "version" in resp.json()

    @pytest.mark.asyncio
    async def test_list_apps(self, client):
        resp = await client.get("/list-apps")
        assert resp.status_code == 200
        apps = resp.json()
        assert "greeter" in apps
        assert "echo" in apps


# ---------------------------------------------------------------------------
# Agent info
# ---------------------------------------------------------------------------


class TestAgentInfo:
    @pytest.mark.asyncio
    async def test_get_app_info(self, client):
        resp = await client.get("/apps/greeter")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "greeter"
        assert data["description"] == "A greeter agent"

    @pytest.mark.asyncio
    async def test_get_nonexistent_app(self, client):
        resp = await client.get("/apps/unknown")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Session CRUD
# ---------------------------------------------------------------------------


class TestSessionCRUD:
    @pytest.mark.asyncio
    async def test_create_session(self, client):
        resp = await client.post(
            "/apps/greeter/users/u1/sessions",
            json={},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert data["app_name"] == "greeter"
        assert data["user_id"] == "u1"

    @pytest.mark.asyncio
    async def test_create_session_with_id(self, client):
        resp = await client.post(
            "/apps/greeter/users/u1/sessions",
            json={"session_id": "my-session"},
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == "my-session"

    @pytest.mark.asyncio
    async def test_list_sessions(self, client):
        # Create two sessions
        await client.post("/apps/greeter/users/u1/sessions", json={"session_id": "s1"})
        await client.post("/apps/greeter/users/u1/sessions", json={"session_id": "s2"})

        resp = await client.get("/apps/greeter/users/u1/sessions")
        assert resp.status_code == 200
        sessions = resp.json()
        ids = [s["id"] for s in sessions]
        assert "s1" in ids
        assert "s2" in ids

    @pytest.mark.asyncio
    async def test_get_session(self, client):
        await client.post("/apps/greeter/users/u1/sessions", json={"session_id": "s1"})
        resp = await client.get("/apps/greeter/users/u1/sessions/s1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "s1"
        assert "state" in data
        assert "events" in data

    @pytest.mark.asyncio
    async def test_get_nonexistent_session(self, client):
        resp = await client.get("/apps/greeter/users/u1/sessions/nope")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_session(self, client):
        await client.post("/apps/greeter/users/u1/sessions", json={"session_id": "s1"})
        resp = await client.delete("/apps/greeter/users/u1/sessions/s1")
        assert resp.status_code == 200

        resp = await client.get("/apps/greeter/users/u1/sessions/s1")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_create_session_with_title(self, client):
        """Session creation with title (Doc 20)."""
        resp = await client.post(
            "/apps/greeter/users/u1/sessions",
            json={"session_id": "titled", "title": "My Chat"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "My Chat"
        assert data["created_at"] > 0

    @pytest.mark.asyncio
    async def test_session_summary_has_title_and_created_at(self, client):
        """List sessions returns title + created_at (Doc 20)."""
        await client.post(
            "/apps/greeter/users/u1/sessions",
            json={"session_id": "s1", "title": "First"},
        )
        resp = await client.get("/apps/greeter/users/u1/sessions")
        sessions = resp.json()
        assert len(sessions) >= 1
        s = sessions[0]
        assert "title" in s
        assert "created_at" in s

    @pytest.mark.asyncio
    async def test_session_detail_has_title_and_created_at(self, client):
        """Get session detail returns title + created_at (Doc 20)."""
        await client.post(
            "/apps/greeter/users/u1/sessions",
            json={"session_id": "s1", "title": "Detail Test"},
        )
        resp = await client.get("/apps/greeter/users/u1/sessions/s1")
        data = resp.json()
        assert data["title"] == "Detail Test"
        assert data["created_at"] > 0

    @pytest.mark.asyncio
    async def test_run_auto_creates_titled_session(self, client):
        """Running against new session auto-generates title (Doc 20)."""
        resp = await client.post("/run", json={
            "app_name": "greeter",
            "user_id": "u1",
            "session_id": "auto-title",
            "new_message": {"role": "user", "parts": [{"text": "Hello world"}]},
        })
        assert resp.status_code == 200

        resp = await client.get("/apps/greeter/users/u1/sessions/auto-title")
        data = resp.json()
        assert data["title"] == "Hello world"


# ---------------------------------------------------------------------------
# Run endpoints
# ---------------------------------------------------------------------------


class TestRunEndpoints:
    @pytest.mark.asyncio
    async def test_run_sync(self, client):
        resp = await client.post("/run", json={
            "app_name": "greeter",
            "user_id": "u1",
            "session_id": "s1",
            "new_message": {"role": "user", "parts": [{"text": "Hi"}]},
        })
        assert resp.status_code == 200
        events = resp.json()
        assert len(events) >= 1
        # Should contain greeter's response
        texts = []
        for e in events:
            for p in (e.get("content", {}) or {}).get("parts", []):
                if p.get("text"):
                    texts.append(p["text"])
        assert any("greeter" in t for t in texts)

    @pytest.mark.asyncio
    async def test_run_sync_nonexistent_app(self, client):
        resp = await client.post("/run", json={
            "app_name": "unknown",
            "user_id": "u1",
            "session_id": "s1",
            "new_message": {"role": "user", "parts": [{"text": "Hi"}]},
        })
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_run_sse(self, client):
        resp = await client.post("/run_sse", json={
            "app_name": "greeter",
            "user_id": "u1",
            "session_id": "s1",
            "new_message": {"role": "user", "parts": [{"text": "Hi"}]},
            "streaming": True,
        })
        assert resp.status_code == 200
        # SSE response should contain event data
        text = resp.text
        assert "data:" in text or "greeter" in text

    @pytest.mark.asyncio
    async def test_run_creates_session(self, client):
        """Running against a new session_id should auto-create it."""
        resp = await client.post("/run", json={
            "app_name": "greeter",
            "user_id": "u1",
            "session_id": "auto-created",
            "new_message": {"role": "user", "parts": [{"text": "Hi"}]},
        })
        assert resp.status_code == 200

        # Session should now exist
        resp = await client.get("/apps/greeter/users/u1/sessions/auto-created")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_run_empty_message(self, client):
        resp = await client.post("/run", json={
            "app_name": "greeter",
            "user_id": "u1",
            "session_id": "s1",
        })
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_session_has_events_after_run(self, client):
        """After running, the session should contain the events."""
        await client.post("/run", json={
            "app_name": "greeter",
            "user_id": "u1",
            "session_id": "s1",
            "new_message": {"role": "user", "parts": [{"text": "Hi"}]},
        })

        resp = await client.get("/apps/greeter/users/u1/sessions/s1")
        data = resp.json()
        assert len(data["events"]) >= 2  # user + agent


# ---------------------------------------------------------------------------
# Dev UI
# ---------------------------------------------------------------------------


class TestDevUI:
    @pytest.mark.asyncio
    async def test_dev_ui_redirect(self, service):
        """When dev_ui=True, / should redirect to /dev-ui/."""
        agents = {"greeter": StubAgent(name="greeter")}
        app = create_app(agents=agents, session_service=service, dev_ui=True)
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test", follow_redirects=False
        ) as c:
            resp = await c.get("/")
            assert resp.status_code in (301, 302, 307, 308)
            assert "/dev-ui" in resp.headers.get("location", "")

    @pytest.mark.asyncio
    async def test_dev_ui_serves_html(self, service):
        """Dev UI should serve the index.html file."""
        agents = {"greeter": StubAgent(name="greeter")}
        app = create_app(agents=agents, session_service=service, dev_ui=True)
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test", follow_redirects=True
        ) as c:
            resp = await c.get("/dev-ui/")
            assert resp.status_code == 200
            assert "SoulBot" in resp.text


# ---------------------------------------------------------------------------
# Schedule endpoints (Doc 17.5)
# ---------------------------------------------------------------------------


class _FakeScheduleService:
    """Minimal schedule service for API tests."""

    def __init__(self):
        self._entries = {
            "s1": {
                "id": "s1", "trigger_config": {"type": "interval", "minutes": 10},
                "task": {"message": "hello"}, "status": "active",
            },
            "s2": {
                "id": "s2", "trigger_config": {"type": "once", "delay": 60},
                "task": {"message": "world"}, "status": "completed",
            },
        }

    def list(self, status=None, **kwargs):
        entries = list(self._entries.values())
        if status:
            entries = [e for e in entries if e["status"] == status]
        return {"entries": entries, "count": len(entries)}

    def get(self, id, **kwargs):
        if id not in self._entries:
            raise ValueError(f"Schedule '{id}' not found")
        return self._entries[id]


class TestScheduleEndpoints:
    @pytest.fixture
    def sched_app(self, service):
        agents = {"greeter": StubAgent(name="greeter")}
        sched_svc = _FakeScheduleService()
        return create_app(
            agents=agents, session_service=service,
            schedule_service=sched_svc, dev_ui=False,
        )

    @pytest.fixture
    async def sched_client(self, sched_app):
        transport = ASGITransport(app=sched_app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c

    @pytest.mark.asyncio
    async def test_schedule_list_all(self, sched_client):
        resp = await sched_client.get("/schedule/list")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 2

    @pytest.mark.asyncio
    async def test_schedule_list_filter(self, sched_client):
        resp = await sched_client.get("/schedule/list?status=active")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["entries"][0]["id"] == "s1"

    @pytest.mark.asyncio
    async def test_schedule_get(self, sched_client):
        resp = await sched_client.get("/schedule/s1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "s1"
        assert data["status"] == "active"

    @pytest.mark.asyncio
    async def test_schedule_get_not_found(self, sched_client):
        resp = await sched_client.get("/schedule/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_no_schedule_endpoints_without_service(self, client):
        """Without schedule_service, endpoints don't exist."""
        resp = await client.get("/schedule/list")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Heartbeat endpoints (Doc 12)
# ---------------------------------------------------------------------------


class _FakeHeartbeatStore:
    """Minimal heartbeat store for API tests."""

    def __init__(self):
        self._records = [
            {"id": 1, "agent_name": "a1", "entry_id": "hb_a1",
             "fired_at": "2025-01-01T00:00:00", "result": "ok", "skipped": 0},
        ]

    def query(self, agent_name=None, limit=50, offset=0):
        records = self._records
        if agent_name:
            records = [r for r in records if r["agent_name"] == agent_name]
        return records[offset:offset + limit]

    def count(self, agent_name=None):
        if agent_name:
            return sum(1 for r in self._records if r["agent_name"] == agent_name)
        return len(self._records)


class TestHeartbeatEndpoints:
    @pytest.fixture
    def hb_app(self, service):
        agents = {"greeter": StubAgent(name="greeter")}
        hb_store = _FakeHeartbeatStore()
        return create_app(
            agents=agents, session_service=service,
            heartbeat_store=hb_store, dev_ui=False,
        )

    @pytest.fixture
    async def hb_client(self, hb_app):
        transport = ASGITransport(app=hb_app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c

    @pytest.mark.asyncio
    async def test_heartbeat_history_endpoint(self, hb_client):
        """GET /heartbeat/history returns list."""
        resp = await hb_client.get("/heartbeat/history")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_heartbeat_count_endpoint(self, hb_client):
        """GET /heartbeat/count returns count dict."""
        resp = await hb_client.get("/heartbeat/count")
        assert resp.status_code == 200
        assert "count" in resp.json()

    @pytest.mark.asyncio
    async def test_heartbeat_history_with_params(self, hb_client):
        """GET /heartbeat/history respects limit/offset params."""
        resp = await hb_client.get("/heartbeat/history?limit=5&offset=0")
        assert resp.status_code == 200
