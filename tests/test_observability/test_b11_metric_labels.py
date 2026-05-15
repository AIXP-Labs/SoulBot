"""B11 — metric labels must stay on the low-cardinality whitelist.

Doc 12 v2.3 §9.1 property layering rules:

- Metric label layer accepts only:
    gen_ai.operation.name  (~5 values)
    gen_ai.provider.name   (~4 values)
    acp.provider.name      (~5 values)
    gen_ai.request.model   (~10 values)
    gen_ai.token.type      ("input" | "output")
- Everything else (soulbot.turn.id, user_id, acp.session.id, etc.) stays on
  the span, never on a metric — else Prometheus series explode.

This test verifies that the labels actually recorded by the ACP call path
fall entirely within the whitelist. Run with a fake pool so no real CLI
subprocess is spawned.
"""
from __future__ import annotations

import pytest

from soulbot.models.acp_llm import ACPLlm
from soulbot.models.llm_request import LlmRequest


LABEL_WHITELIST = frozenset(
    {
        "gen_ai.operation.name",
        "gen_ai.provider.name",
        "acp.provider.name",
        "gen_ai.request.model",
        "gen_ai.token.type",
    }
)


def _req(text: str = "hi") -> LlmRequest:
    from soulbot.events.event import Content, Part

    r = LlmRequest()
    r.contents.append(Content(role="user", parts=[Part(text=text)]))
    return r


@pytest.mark.asyncio
async def test_b11_all_metric_labels_on_whitelist(otel_metric, fake_acp_streaming):
    llm = ACPLlm(model="claude-acp/sonnet-4.5")
    async for _ in llm.generate_content_async(_req(), stream=True):
        pass

    data = otel_metric.get_metrics_data()
    assert data is not None
    bad: list[tuple[str, str]] = []
    for rm in data.resource_metrics:
        for sm in rm.scope_metrics:
            for metric in sm.metrics:
                for point in metric.data.data_points:
                    for key in point.attributes:
                        if key not in LABEL_WHITELIST:
                            bad.append((metric.name, key))

    assert not bad, f"high-cardinality label(s) leaked into metrics: {bad}"
