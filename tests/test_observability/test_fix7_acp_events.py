"""Fix 7 — ACP span carries session / retry / rotation events.

Covered:
- Default call: ACP_SESSION_ID / ACP_POOL_QUEUE_TIME_S / ACP_POOL_ATTEMPT=1 set
- Flaky pool: one retry → acp.retry event + final ACP_POOL_ATTEMPT=2
- Rotating pool: stored sid != returned sid → acp.session.rotated event
"""
from __future__ import annotations

import pytest

from soulbot.models.acp_llm import ACPLlm
from soulbot.models.llm_request import LlmRequest
from soulbot.observability import semconv as sc


def _req(text: str = "hi") -> LlmRequest:
    from soulbot.events.event import Content, Part

    r = LlmRequest()
    r.contents.append(Content(role="user", parts=[Part(text=text)]))
    return r


def _invoke_spans(exporter):
    return [s for s in exporter.get_finished_spans()
            if s.name.startswith("invoke_agent")]


@pytest.mark.asyncio
async def test_fix7_session_attributes_on_default_call(captured_spans, fake_acp_pool):
    llm = ACPLlm(model="claude-acp/sonnet-4.5")
    async for _ in llm.generate_content_async(_req(), stream=False):
        pass

    spans = _invoke_spans(captured_spans)
    attrs = spans[-1].attributes
    assert sc.ACP_SESSION_ID in attrs
    assert sc.ACP_POOL_QUEUE_TIME_S in attrs
    assert attrs[sc.ACP_POOL_ATTEMPT] == 1
    assert sc.ACP_PROMPT_LENGTH_CHARS in attrs


@pytest.mark.asyncio
async def test_fix7_retry_event_on_flaky_pool(captured_spans, fake_acp_pool_flaky):
    llm = ACPLlm(model="claude-acp/sonnet-4.5")
    async for _ in llm.generate_content_async(_req(), stream=False):
        pass

    spans = _invoke_spans(captured_spans)
    retry_events = [e for e in spans[-1].events if e.name == "acp.retry"]
    assert len(retry_events) == 1, (
        f"expected 1 acp.retry event, got {len(retry_events)} "
        f"(events={[e.name for e in spans[-1].events]})"
    )
    # The successful attempt is the 2nd
    assert spans[-1].attributes[sc.ACP_POOL_ATTEMPT] == 2


@pytest.mark.asyncio
async def test_fix7_session_rotation_event(captured_spans, fake_acp_pool_rotating):
    """When caller requests an old sid but pool returns a different one,
    span must carry acp.session.rotated=True + acp.session.rotated event.

    We simulate this by passing user_id + injecting a ProviderSessionStore
    that returns "old-session" for the lookup — pool returns "new-session".
    """
    # Inject a tiny in-memory store so ACPLlm asks for a session first
    class _Store:
        def __init__(self, sid):
            self.sid = sid
            self.cleared = False

        async def get_session_id(self, user_id, provider):
            return self.sid

        async def set_session_id(self, user_id, provider, sid):
            self.sid = sid

        async def clear(self, user_id, provider):
            self.cleared = True
            self.sid = None

    ACPLlm.set_provider_session_store(_Store("old-session"))
    try:
        llm = ACPLlm(model="claude-acp/sonnet-4.5")
        req = _req()
        req.metadata["user_id"] = "user-1"
        async for _ in llm.generate_content_async(req, stream=False):
            pass
    finally:
        ACPLlm.set_provider_session_store(None)

    spans = _invoke_spans(captured_spans)
    attrs = spans[-1].attributes
    assert attrs.get(sc.ACP_SESSION_ROTATED) is True
    rot_events = [e for e in spans[-1].events if e.name == "acp.session.rotated"]
    assert len(rot_events) == 1
