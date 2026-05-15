"""AlwaysKeepCriticalSampler — Fix 11 head sampler wrapper.

Wraps a fallback sampler (typically ``ParentBased(TraceIdRatioBased(r))``);
forces RECORD_AND_SAMPLE when the span looks critical:

- name starts with a critical prefix (``security.*``, ``cost.*``,
  ``pipeline.breaker.*``, ``pipeline.exception``, ``pipeline.guardrail.*``,
  ``pipeline.speaker.*``, ``pipeline.stage.resume``, ``guardrail.abort``), OR
- ``gen_ai.operation.name`` ∈ {"guardrail_abort", "speaker_selection", "resume"}, OR
- ``status`` attribute ∈ {"fail", "error"}, OR
- ``wallclock_elapsed_s`` > ``SOULBOT_SLOW_THRESHOLD_S`` (default 10.0), OR
- ``acp.session.rotated`` is True, OR
- ``acp.auth.error_detected`` is True, OR
- ``gen_ai.usage.output_tokens`` > ``SOULBOT_TOKEN_THRESHOLD`` (default 5000)

Otherwise defers to the fallback sampler.

Caveats
-------
``should_sample`` is called at **span start**; some attributes
(status, wallclock_elapsed_s, output_tokens, session_rotated) are only set
mid-span via ``set_attribute``. For those, the sampler cannot see the
final value. This is fine for the head-sampling use case because critical
events are typically known at start (by name prefix or operation.name);
late-breaking criticality (e.g. slow call, error) is left to tail sampling
(a future ``on_end`` SpanProcessor filter — not in Phase 4 scope).

Reference: Doc 12 v2.3 §8.1 Fix 11.
"""
from __future__ import annotations

import os
from typing import Optional, Sequence

from opentelemetry.context import Context
from opentelemetry.sdk.trace.sampling import Decision, Sampler, SamplingResult
from opentelemetry.trace import Link, SpanKind
from opentelemetry.trace.span import TraceState
from opentelemetry.util.types import Attributes


# Span name prefixes that MUST be kept even when fallback samples=0.
ALWAYS_KEEP_PREFIXES = (
    "security.",
    "cost.",
    "pipeline.breaker.",
    "pipeline.exception",
    "pipeline.guardrail.",
    "pipeline.speaker.",
    "pipeline.stage.resume",
    "guardrail.abort",
)

# gen_ai.operation.name values that MUST be kept.
ALWAYS_KEEP_OPERATION_NAMES = frozenset({
    "guardrail_abort",
    "speaker_selection",
    "resume",
})


def _slow_threshold_s() -> float:
    return float(os.environ.get("SOULBOT_SLOW_THRESHOLD_S", "10.0"))


def _token_threshold() -> int:
    return int(os.environ.get("SOULBOT_TOKEN_THRESHOLD", "5000"))


class AlwaysKeepCriticalSampler(Sampler):
    """See module docstring."""

    def __init__(self, fallback: Sampler):
        self.fallback = fallback

    def should_sample(
        self,
        parent_context: Optional[Context],
        trace_id: int,
        name: str,
        kind: Optional[SpanKind] = None,
        attributes: Attributes = None,
        links: Optional[Sequence[Link]] = None,
        trace_state: Optional[TraceState] = None,
    ) -> SamplingResult:
        # 1. Name prefix
        if any(name.startswith(p) for p in ALWAYS_KEEP_PREFIXES):
            return SamplingResult(Decision.RECORD_AND_SAMPLE)

        attrs = dict(attributes or {})

        # 2. Operation-name attribute
        op = attrs.get("gen_ai.operation.name")
        if op in ALWAYS_KEEP_OPERATION_NAMES:
            return SamplingResult(Decision.RECORD_AND_SAMPLE)

        # 3. Explicit failure status
        if attrs.get("status") in ("fail", "error"):
            return SamplingResult(Decision.RECORD_AND_SAMPLE)

        # 4. Slow call
        elapsed = attrs.get("wallclock_elapsed_s")
        if elapsed is not None and float(elapsed) > _slow_threshold_s():
            return SamplingResult(Decision.RECORD_AND_SAMPLE)

        # 5. ACP session rotated / auth error → always keep
        if attrs.get("acp.session.rotated") is True:
            return SamplingResult(Decision.RECORD_AND_SAMPLE)
        if attrs.get("acp.auth.error_detected") is True:
            return SamplingResult(Decision.RECORD_AND_SAMPLE)

        # 6. Heavy output token proxy (ACP has no USD cost)
        est_tokens = attrs.get("gen_ai.usage.output_tokens")
        if est_tokens is not None and int(est_tokens) > _token_threshold():
            return SamplingResult(Decision.RECORD_AND_SAMPLE)

        # Fallback
        return self.fallback.should_sample(
            parent_context, trace_id, name, kind, attributes, links, trace_state,
        )

    def get_description(self) -> str:
        return (
            f"AlwaysKeepCriticalSampler(fallback={self.fallback.get_description()})"
        )
