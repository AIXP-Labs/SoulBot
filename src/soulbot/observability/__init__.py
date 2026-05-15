"""SoulBot observability — OTel SDK + ACP-specific instrumentation.

Public API:
    init_otel() / shutdown_otel()      — lifespan hooks
    get_llm_histograms()               — metrics singleton
    estimate_tokens()                  — rough token estimation
    resolve_provider_from_model()      — ACP model → provider short name
    resolve_gen_ai_provider()          — ACP short name → OTel standard name
    semconv                            — OTel + ACP + SoulBot field constants

Reference: Doc 12 v2.3 path B.
"""
from __future__ import annotations

from . import semconv
from .acp_usage import (
    estimate_tokens,
    resolve_gen_ai_provider,
    resolve_provider_from_model,
)
from .metrics import LLMHistograms, get_llm_histograms
from .otel_sampler import (
    ALWAYS_KEEP_OPERATION_NAMES,
    ALWAYS_KEEP_PREFIXES,
    AlwaysKeepCriticalSampler,
)
from .otel_setup import FileSpanExporter, init_otel, shutdown_otel
from .security import AgentCapabilityFlags, scan_for_injection
from .selection import record_speaker_selection
from .trace_context import (
    build_traceparent,
    extract_to_context,
    inject_current,
    new_span_id,
    new_trace_id,
    parse_traceparent,
)

__all__ = [
    "semconv",
    "init_otel",
    "shutdown_otel",
    "FileSpanExporter",
    "get_llm_histograms",
    "LLMHistograms",
    "estimate_tokens",
    "resolve_provider_from_model",
    "resolve_gen_ai_provider",
    "inject_current",
    "extract_to_context",
    "new_trace_id",
    "new_span_id",
    "build_traceparent",
    "parse_traceparent",
    "AlwaysKeepCriticalSampler",
    "ALWAYS_KEEP_PREFIXES",
    "ALWAYS_KEEP_OPERATION_NAMES",
    "scan_for_injection",
    "AgentCapabilityFlags",
    "record_speaker_selection",
]
