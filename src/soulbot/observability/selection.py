"""Fix 15 — speaker_selection span helper.

Emit an independent ``speaker_selection`` span that the AlwaysKeepCriticalSampler
will always retain (via the ``gen_ai.operation.name = speaker_selection``
rule in :mod:`soulbot.observability.otel_sampler`).

Each candidate is recorded as a span event so reviewers can audit why a
particular speaker was chosen even under aggressive head-sampling.

Reference: Doc 12 v2.3 §8.3
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

try:
    from opentelemetry import trace

    from . import semconv as sc

    _OTEL_AVAILABLE = True
    _tracer = trace.get_tracer("soulbot.selection")
except ImportError:
    _OTEL_AVAILABLE = False
    _tracer = None


def record_speaker_selection(
    *,
    candidates: Iterable[Mapping[str, Any]],
    winner: str,
    strategy: str,
    round_index: int,
    coordinator: str,
) -> None:
    """Emit a ``speaker_selection`` span with candidate events.

    Args:
        candidates: iterable of ``{"name": str, "score": float, "reason": str}``
            dicts (extra keys are ignored). Only the first 10 are recorded as
            span events to keep cardinality bounded.
        winner: the chosen speaker's name (goes to ``soulbot.selection.winner``).
        strategy: free-form identifier of the selection algorithm (e.g.
            "highest_score", "round_robin").
        round_index: current debate round (>= 0).
        coordinator: the orchestrating agent's name (goes to ``gen_ai.agent.name``).

    Soft-fail: if OTel is not installed, this is a no-op.
    """
    if not _OTEL_AVAILABLE:
        return

    with _tracer.start_as_current_span("speaker_selection") as span:
        span.set_attribute(sc.GEN_AI_OPERATION_NAME, "speaker_selection")
        span.set_attribute(sc.GEN_AI_AGENT_NAME, coordinator)
        span.set_attribute("soulbot.selection.winner", winner)
        span.set_attribute("soulbot.selection.strategy", strategy)
        span.set_attribute("soulbot.selection.round_index", int(round_index))

        for c in list(candidates)[:10]:
            span.add_event(
                "candidate",
                attributes={
                    "soulbot.candidate.name": str(c.get("name", "")),
                    "soulbot.candidate.score": float(c.get("score", 0.0)),
                    "soulbot.candidate.reason": str(c.get("reason", ""))[:100],
                },
            )
