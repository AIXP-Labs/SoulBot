"""W3C traceparent / tracestate helpers for SOULBOT_CMD envelope propagation.

Doc 12 v2.3 §7.1 Fix 8: SoulBot dispatches commands via an in-process envelope
(`ParsedCommand`), but some services persist commands for later execution
(e.g. `schedule`, `message.send` → another agent turn). Those persisted
envelopes need a W3C traceparent so replay / consumer paths can link back
to the originating trace.

This module wraps OTel's official `TraceContextTextMapPropagator` +
`W3CBaggagePropagator` so the rest of the codebase can talk in plain dict
carriers without importing OTel internals everywhere.

Key functions
-------------
- :func:`inject_current`    — snapshot current OTel context into a carrier dict
- :func:`extract_to_context` — parse a carrier dict back into an OTel context
- :func:`new_trace_id`      — random 128-bit hex trace id (for tests)
- :func:`new_span_id`       — random 64-bit hex span id (for tests)
- :func:`build_traceparent` — assemble W3C string from parts (for tests)
- :func:`parse_traceparent` — split W3C string into parts (for tests/debug)

Reference: https://www.w3.org/TR/trace-context/
"""
from __future__ import annotations

import os
import re
from typing import Optional

from opentelemetry import context as otel_context
from opentelemetry.baggage.propagation import W3CBaggagePropagator
from opentelemetry.trace.propagation.tracecontext import (
    TraceContextTextMapPropagator,
)

_TRACE_PROP = TraceContextTextMapPropagator()
_BAGGAGE_PROP = W3CBaggagePropagator()

# W3C traceparent: "00-<32 hex>-<16 hex>-<2 hex>"
_TRACEPARENT_RE = re.compile(r"^([0-9a-f]{2})-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$")


def inject_current(carrier: Optional[dict] = None) -> dict:
    """Inject current OTel context (traceparent + tracestate + baggage) into a carrier.

    Returns the carrier dict (mutated in place if provided, else new).
    """
    carrier = carrier if carrier is not None else {}
    _TRACE_PROP.inject(carrier)
    _BAGGAGE_PROP.inject(carrier)
    return carrier


def extract_to_context(carrier: dict) -> otel_context.Context:
    """Extract carrier dict into a fresh OTel context.

    Returns a Context suitable for ``context.attach(ctx)`` or for passing
    to ``tracer.start_as_current_span(..., context=ctx)``.
    """
    ctx = _TRACE_PROP.extract(carrier)
    ctx = _BAGGAGE_PROP.extract(carrier, context=ctx)
    return ctx


def new_trace_id() -> str:
    """Return a new random 32-hex-char (128-bit) trace id."""
    return os.urandom(16).hex()


def new_span_id() -> str:
    """Return a new random 16-hex-char (64-bit) span id."""
    return os.urandom(8).hex()


def build_traceparent(
    trace_id: str,
    span_id: str,
    *,
    sampled: bool = True,
    version: str = "00",
) -> str:
    """Build a W3C traceparent string.

    Args:
        trace_id: 32-hex-char trace id.
        span_id:  16-hex-char span id.
        sampled:  whether the trace-flags "sampled" bit is set.
        version:  W3C version byte (default "00" — current).
    """
    flags = "01" if sampled else "00"
    return f"{version}-{trace_id}-{span_id}-{flags}"


def parse_traceparent(traceparent: str) -> Optional[tuple[str, str, str, str]]:
    """Parse a W3C traceparent string into ``(version, trace_id, span_id, flags)``.

    Returns None if the string does not match W3C format.
    """
    m = _TRACEPARENT_RE.match(traceparent.strip())
    if not m:
        return None
    return m.group(1), m.group(2), m.group(3), m.group(4)
