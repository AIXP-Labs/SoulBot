"""Singleton access to LLM histograms.

All LLM / ACP call sites (acp_llm, future tool instrumenters) MUST go through
get_llm_histograms() to ensure a single instrument per name. Without the
singleton, separate calls to meter.create_histogram() spawn independent
instruments and metric data gets split across series.

Reference: Doc 12 v2.3 §6.0 (C6 singleton)
"""
from __future__ import annotations

from functools import lru_cache
from typing import NamedTuple

from opentelemetry import metrics

from . import semconv as sc


class LLMHistograms(NamedTuple):
    """4 histograms recorded by the ACP LLM call path."""

    duration: metrics.Histogram              # gen_ai.client.operation.duration (s)
    estimated_token_usage: metrics.Histogram # soulbot.estimated.token.usage (tokens, estimated)
    acp_subprocess_ttft: metrics.Histogram   # acp.subprocess.ttft (s, streaming first chunk)
    acp_pool_queue_time: metrics.Histogram   # acp.pool.queue_time (s, pool wait)


@lru_cache(maxsize=1)
def get_llm_histograms() -> LLMHistograms:
    """Return the single set of LLM histograms. Created lazily on first call.

    Caller convention::

        from soulbot.observability.metrics import get_llm_histograms
        hist = get_llm_histograms()
        hist.duration.record(duration_s, attributes=labels)
        hist.estimated_token_usage.record(
            est_tokens, attributes={**labels, sc.METRIC_TOKEN_TYPE: "input"}
        )
        hist.acp_subprocess_ttft.record(ttft_s, attributes=labels)
        hist.acp_pool_queue_time.record(queue_s, attributes=labels)
    """
    meter = metrics.get_meter("soulbot.llm")
    return LLMHistograms(
        duration=meter.create_histogram(
            name=sc.METRIC_OPERATION_DURATION,
            unit="s",
            description="LLM operation total duration (ACP subprocess call-to-response).",
        ),
        estimated_token_usage=meter.create_histogram(
            name=sc.METRIC_ESTIMATED_TOKEN_USAGE,
            unit="{token}",
            description=(
                "Estimated token count (ACP mode: len(text)/4 rough estimate; "
                "NOT for billing — use Anthropic Console / Claude subscription "
                "dashboards for actual usage)."
            ),
        ),
        acp_subprocess_ttft=meter.create_histogram(
            name=sc.METRIC_ACP_SUBPROCESS_TTFT,
            unit="s",
            description="ACP streaming: time from query_stream start to first chunk.",
        ),
        acp_pool_queue_time=meter.create_histogram(
            name=sc.METRIC_ACP_POOL_QUEUE_TIME,
            unit="s",
            description="ACP ConnectionPool.acquire() wait time.",
        ),
    )
