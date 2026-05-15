"""Fix 1 — ACP span carries all required attributes (non-streaming + streaming).

Doc 12 v2.3 §9.2:
- GEN_AI_PROVIDER_NAME mapped via resolve_gen_ai_provider (claude → anthropic)
- ACP_PROVIDER_NAME raw short name ("claude")
- ACP_PROMPT_LENGTH_CHARS exact char count
- GEN_AI_USAGE_INPUT_TOKENS estimated > 0
- Streaming: GEN_AI_SERVER_TTFT set and < total duration
"""
from __future__ import annotations

import pytest

from soulbot.models.acp_llm import ACPLlm
from soulbot.models.llm_request import LlmRequest
from soulbot.observability import semconv as sc


def _make_request(text: str = "hi") -> LlmRequest:
    # Empty request so _build_prompt produces just the user content
    from soulbot.events.event import Content, Part

    req = LlmRequest()
    req.contents.append(Content(role="user", parts=[Part(text=text)]))
    return req


@pytest.mark.asyncio
async def test_fix1_non_streaming_span_attributes(captured_spans, fake_acp_pool):
    llm = ACPLlm(model="claude-acp/sonnet-4.5")
    req = _make_request("hi")

    async for _ in llm.generate_content_async(req, stream=False):
        pass

    spans = [s for s in captured_spans.get_finished_spans()
             if s.name.startswith("invoke_agent")]
    assert spans, f"no invoke_agent span; got {[s.name for s in captured_spans.get_finished_spans()]}"
    attrs = spans[-1].attributes
    assert attrs[sc.GEN_AI_PROVIDER_NAME] == "anthropic"  # claude → anthropic
    assert attrs[sc.ACP_PROVIDER_NAME] == "claude"
    assert attrs[sc.GEN_AI_REQUEST_MODEL] == "claude-acp/sonnet-4.5"
    assert attrs[sc.ACP_PROMPT_LENGTH_CHARS] > 0
    assert attrs[sc.GEN_AI_USAGE_INPUT_TOKENS] >= 1


@pytest.mark.asyncio
async def test_fix1_streaming_ttft_recorded(captured_spans, fake_acp_streaming):
    llm = ACPLlm(model="claude-acp/sonnet-4.5")
    req = _make_request("hi")

    async for _ in llm.generate_content_async(req, stream=True):
        pass

    spans = [s for s in captured_spans.get_finished_spans()
             if s.name.startswith("invoke_agent stream")]
    assert spans
    attrs = spans[-1].attributes
    assert sc.GEN_AI_SERVER_TTFT in attrs
    ttft = float(attrs[sc.GEN_AI_SERVER_TTFT])
    assert ttft > 0
    # TTFT must be less than total span duration (in seconds)
    total_s = (spans[-1].end_time - spans[-1].start_time) / 1e9
    assert ttft < total_s


@pytest.mark.asyncio
async def test_fix1_streaming_flag_set(captured_spans, fake_acp_streaming):
    llm = ACPLlm(model="claude-acp/sonnet-4.5")
    req = _make_request("hi")

    async for _ in llm.generate_content_async(req, stream=True):
        pass

    spans = [s for s in captured_spans.get_finished_spans()
             if s.name.startswith("invoke_agent stream")]
    assert spans[-1].attributes[sc.SOULBOT_STREAMING] is True
