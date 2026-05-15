"""Doc 21 P2 — invoke_agent span carries gen_ai.conversation.id when
llm_request.metadata provides session_id.

Reference: semconv.py `GEN_AI_CONVERSATION_ID = "gen_ai.conversation.id"`
(maps to SoulBot session_id for OTel dashboard turn-group filtering).
"""
from __future__ import annotations

import pytest

from soulbot.events.event import Content, Part
from soulbot.models.acp_llm import ACPLlm
from soulbot.models.llm_request import LlmRequest
from soulbot.observability import semconv as sc


def _make_request(text: str = "hi", session_id: str | None = None) -> LlmRequest:
    req = LlmRequest()
    req.contents.append(Content(role="user", parts=[Part(text=text)]))
    if session_id is not None:
        req.metadata["session_id"] = session_id
    return req


@pytest.mark.asyncio
async def test_invoke_agent_span_has_conversation_id_when_session_provided(
    captured_spans, fake_acp_pool,
):
    llm = ACPLlm(model="claude-acp/sonnet-4.5")
    req = _make_request("hi", session_id="session_abc123")

    async for _ in llm.generate_content_async(req, stream=False):
        pass

    spans = [
        s for s in captured_spans.get_finished_spans()
        if s.name.startswith("invoke_agent")
    ]
    assert spans
    attrs = spans[-1].attributes
    assert attrs[sc.GEN_AI_CONVERSATION_ID] == "session_abc123"


@pytest.mark.asyncio
async def test_invoke_agent_span_omits_conversation_id_when_absent(
    captured_spans, fake_acp_pool,
):
    """Backward compat: if metadata has no session_id, attribute is not set."""
    llm = ACPLlm(model="claude-acp/sonnet-4.5")
    req = _make_request("hi", session_id=None)

    async for _ in llm.generate_content_async(req, stream=False):
        pass

    spans = [
        s for s in captured_spans.get_finished_spans()
        if s.name.startswith("invoke_agent")
    ]
    assert spans
    attrs = spans[-1].attributes
    assert sc.GEN_AI_CONVERSATION_ID not in attrs


@pytest.mark.asyncio
async def test_invoke_agent_span_omits_conversation_id_when_empty_string(
    captured_spans, fake_acp_pool,
):
    """Empty session_id is treated as absent (avoid noisy empty attrs)."""
    llm = ACPLlm(model="claude-acp/sonnet-4.5")
    req = _make_request("hi", session_id="")

    async for _ in llm.generate_content_async(req, stream=False):
        pass

    spans = [
        s for s in captured_spans.get_finished_spans()
        if s.name.startswith("invoke_agent")
    ]
    assert spans
    attrs = spans[-1].attributes
    assert sc.GEN_AI_CONVERSATION_ID not in attrs
