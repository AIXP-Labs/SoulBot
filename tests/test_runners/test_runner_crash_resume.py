"""Tests for Runner auto-resume on fatal ACP crash (plan20/38 change B).

Verifies the auto-resume loop added to Runner.run:
- A fatal subprocess crash surfaces as Event(error_code="ACP_CRASH"); Runner
  swallows it, injects a "继续执行任务" turn, and re-runs the agent (engine
  CRASH RECOVERY resumes from last_completed_node) → final result delivered.
- Persistent crash stops after MAX_AUTO_RESUME and reports to the human.
- Normal completion (no ACP_CRASH) never triggers auto-resume.
- Non-crash errors (e.g. ACP_ERROR) do NOT trigger auto-resume — only the
  distinct ACP_CRASH signal does (fail-closed: WAITING_USER never produces it).
"""

import asyncio

import pytest

from soulbot.agents import LlmAgent
from soulbot.events.event import Content, Part
from soulbot.models.base_llm import BaseLlm
from soulbot.models.llm_request import LlmResponse
from soulbot.models.registry import ModelRegistry
from soulbot.runners import Runner
from soulbot.sessions import InMemorySessionService


class CrashMockLlm(BaseLlm):
    """Mock LLM whose queued responses drive Runner's crash/resume path.

    Each generate_content_async call pops one response, so a fresh agent run
    (Runner's auto-resume re-runs the agent) consumes the next queued item.
    """

    _responses: list = []

    @classmethod
    def set_responses(cls, responses):
        cls._responses = list(responses)

    @classmethod
    def supported_models(cls):
        return [r"crash-mock-.*"]

    async def generate_content_async(self, llm_request, *, stream=False):
        if self._responses:
            yield self._responses.pop(0)
        else:
            yield LlmResponse(content=Content(role="model", parts=[Part(text="default")]))


@pytest.fixture(autouse=True)
def setup_crash_mock():
    ModelRegistry.reset()
    ModelRegistry.register(r"crash-mock-.*", CrashMockLlm)
    yield
    ModelRegistry.reset()


@pytest.fixture(autouse=True)
def no_backoff(monkeypatch):
    """Skip the exponential backoff sleeps so exhaustion test is instant."""
    async def _instant(*_a, **_k):
        return None
    monkeypatch.setattr(asyncio, "sleep", _instant)


# --- helpers ---------------------------------------------------------------


def _agent():
    return LlmAgent(name="crash_agent", model="crash-mock-model", instruction="test")


def _crash():
    return LlmResponse(error_code="ACP_CRASH", error_message="V8 OOM exit 3221226505")


def _text(t):
    return LlmResponse(content=Content(role="model", parts=[Part(text=t)]))


async def _run(runner, message="hello"):
    events = []
    async for ev in runner.run(user_id="u1", session_id="s1", message=message):
        events.append(ev)
    return events


def _texts(events):
    out = []
    for e in events:
        if e.content:
            out.append(" ".join(p.text for p in e.content.parts if p.text))
    return out


async def _user_texts(svc):
    session = await svc.get_session("app", "u1", "s1")
    return [
        " ".join(p.text for p in e.content.parts if p.text)
        for e in session.events
        if e.author == "user" and e.content
    ]


# --- tests -----------------------------------------------------------------


async def test_auto_resume_on_acp_crash():
    """1 crash then success → Runner auto-resumes, final result delivered."""
    CrashMockLlm.set_responses([_crash(), _text("recovered")])
    svc = InMemorySessionService()
    runner = Runner(agent=_agent(), app_name="app", session_service=svc)

    events = await _run(runner)

    assert any("recovered" in t for t in _texts(events))           # resumed run succeeded
    assert all(e.error_code != "ACP_CRASH" for e in events)        # crash not surfaced
    assert "继续执行任务" in await _user_texts(svc)                # resume turn injected


async def test_resume_exhausted_reports_human():
    """Persistent crash → after MAX_AUTO_RESUME (100) stop and report to human.

    Feeds 105 crashes so the 100-resume ceiling is actually exceeded
    (backoff sleeps are skipped by the no_backoff fixture, so this is instant).
    """
    CrashMockLlm.set_responses([_crash()] * 105)
    svc = InMemorySessionService()
    runner = Runner(agent=_agent(), app_name="app", session_service=svc)

    events = await _run(runner)

    assert any(
        e.author == "system"
        and e.content
        and any("自动续跑" in (p.text or "") for p in e.content.parts)
        for e in events
    )


async def test_no_resume_on_normal_completion():
    """Normal completion (no ACP_CRASH) → no auto-resume, no injected turn."""
    CrashMockLlm.set_responses([_text("done")])
    svc = InMemorySessionService()
    runner = Runner(agent=_agent(), app_name="app", session_service=svc)

    await _run(runner)

    user_texts = await _user_texts(svc)
    assert "继续执行任务" not in user_texts
    assert user_texts.count("hello") == 1


async def test_fail_closed_non_crash_error_no_resume():
    """ACP_ERROR (non-crash) must NOT trigger auto-resume — only ACP_CRASH does.

    This mirrors the fail-closed guarantee: a WAITING_USER pause likewise never
    emits ACP_CRASH, so the loop never auto-advances a sovereignty gate.
    """
    CrashMockLlm.set_responses([LlmResponse(error_code="ACP_ERROR", error_message="other")])
    svc = InMemorySessionService()
    runner = Runner(agent=_agent(), app_name="app", session_service=svc)

    await _run(runner)

    assert "继续执行任务" not in await _user_texts(svc)
