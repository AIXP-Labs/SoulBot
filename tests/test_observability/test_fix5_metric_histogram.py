"""Fix 5 — 4 histograms record data points during ACP call.

- gen_ai.client.operation.duration  (every call)
- acp.pool.queue_time                (every call)
- acp.subprocess.ttft                (streaming only)
- soulbot.estimated.token.usage      (every call, input + output)

Uses a fresh MeterProvider per test via otel_metric fixture; the
get_llm_histograms cache is cleared so instruments bind to this provider.
"""
from __future__ import annotations

import pytest

from soulbot.models.acp_llm import ACPLlm
from soulbot.models.llm_request import LlmRequest


def _req(text: str = "hi") -> LlmRequest:
    from soulbot.events.event import Content, Part

    r = LlmRequest()
    r.contents.append(Content(role="user", parts=[Part(text=text)]))
    return r


def _collect_metrics(reader) -> dict:
    """Flatten reader output: {metric_name: HistogramDataPoint list}."""
    data = reader.get_metrics_data()
    out: dict = {}
    for rm in data.resource_metrics:
        for sm in rm.scope_metrics:
            for m in sm.metrics:
                out.setdefault(m.name, []).extend(m.data.data_points)
    return out


@pytest.mark.asyncio
async def test_fix5_duration_and_pool_queue_recorded(otel_metric, fake_acp_pool):
    llm = ACPLlm(model="claude-acp/sonnet-4.5")
    async for _ in llm.generate_content_async(_req(), stream=False):
        pass

    metrics = _collect_metrics(otel_metric)
    assert "gen_ai.client.operation.duration" in metrics
    assert metrics["gen_ai.client.operation.duration"][0].count == 1
    assert metrics["gen_ai.client.operation.duration"][0].sum > 0

    assert "acp.pool.queue_time" in metrics
    assert metrics["acp.pool.queue_time"][0].count == 1


@pytest.mark.asyncio
async def test_fix5_ttft_only_for_streaming(otel_metric, fake_acp_streaming):
    llm = ACPLlm(model="claude-acp/sonnet-4.5")
    async for _ in llm.generate_content_async(_req(), stream=True):
        pass

    metrics = _collect_metrics(otel_metric)
    assert "acp.subprocess.ttft" in metrics
    assert metrics["acp.subprocess.ttft"][0].count == 1
    assert metrics["acp.subprocess.ttft"][0].sum > 0


@pytest.mark.asyncio
async def test_fix5_token_usage_records_input_and_output(otel_metric, fake_acp_pool):
    llm = ACPLlm(model="claude-acp/sonnet-4.5")
    async for _ in llm.generate_content_async(_req(), stream=False):
        pass

    metrics = _collect_metrics(otel_metric)
    assert "soulbot.estimated.token.usage" in metrics
    points = metrics["soulbot.estimated.token.usage"]
    # Two data points: one for input tokens, one for output — distinguished by
    # gen_ai.token.type attribute
    token_types = {p.attributes.get("gen_ai.token.type") for p in points}
    assert "input" in token_types
    assert "output" in token_types
