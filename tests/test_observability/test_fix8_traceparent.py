"""Fix 8: SOULBOT_CMD envelope carries W3C traceparent.

When CommandExecutor.execute() runs, it must:
1. If cmd.otel_headers is empty → snapshot current OTel context into it
   (so deferred consumers like schedule/message.send preserve the trace).
2. If cmd.otel_headers is already populated → extract into a context so
   the child span links to the originating trace, not a new root.

Reference: Doc 12 v2.3 §7.1
"""
from __future__ import annotations

import pytest
from opentelemetry import trace

from soulbot.commands.executor import CommandExecutor
from soulbot.commands.parser import ParsedCommand
from soulbot.observability.trace_context import inject_current, parse_traceparent


class _MathService:
    def add(self, a: int, b: int) -> int:
        return a + b


@pytest.mark.asyncio
async def test_execute_populates_otel_headers(otel_trace):
    """Path (b): direct dispatch — executor snapshots current ctx into envelope."""
    executor = CommandExecutor()
    executor.register_service("math", _MathService())

    cmd = ParsedCommand(
        service="math", action="add", params={"a": 2, "b": 3}, raw=""
    )
    # Pre-condition: no headers yet
    assert cmd.otel_headers == {}

    tracer = trace.get_tracer("test")
    with tracer.start_as_current_span("outer"):
        result = await executor.execute(cmd)

    assert result == {"success": True, "data": 5}
    # Post-condition: envelope now carries a valid W3C traceparent
    assert "traceparent" in cmd.otel_headers, cmd.otel_headers
    parsed = parse_traceparent(cmd.otel_headers["traceparent"])
    assert parsed is not None


@pytest.mark.asyncio
async def test_execute_extracts_preexisting_traceparent(otel_trace):
    """Path (a): deferred consumer — envelope already has traceparent.

    The span active inside the service method must share trace_id with the
    originator's span (not start a fresh root).

    Note: we don't read from the InMemorySpanExporter because OTel's global
    TracerProvider can only be set once per process; by the time this test
    runs, an earlier test may have set the global, so the executor's tracer
    routes spans to whatever exporter that earlier provider had. Instead we
    inspect the current-span trace_id at execution time via a probe service.
    """
    tracer = trace.get_tracer("test")

    # Simulate a "producer" that injected its context into the envelope
    with tracer.start_as_current_span("producer") as producer_span:
        producer_trace_id = producer_span.get_span_context().trace_id
        carrier: dict = {}
        inject_current(carrier)

    # Probe captures trace_id of current span while the command runs
    captured: dict = {}

    class _Probe:
        def record(self) -> int:
            span = trace.get_current_span()
            captured["trace_id"] = span.get_span_context().trace_id
            return 0

    executor = CommandExecutor()
    executor.register_service("probe", _Probe())
    cmd = ParsedCommand(
        service="probe",
        action="record",
        params={},
        raw="",
        otel_headers=carrier,
    )

    result = await executor.execute(cmd)
    assert result == {"success": True, "data": 0}
    assert captured.get("trace_id") == producer_trace_id, (
        f"command span did not inherit trace_id from envelope "
        f"(producer={producer_trace_id}, captured={captured.get('trace_id')})"
    )


@pytest.mark.asyncio
async def test_execute_error_returns_structured_result(otel_trace):
    """Command that raises returns success=False with the error message."""
    class _Failing:
        def boom(self):
            raise ValueError("kaboom")

    executor = CommandExecutor()
    executor.register_service("svc", _Failing())

    cmd = ParsedCommand(service="svc", action="boom", params={}, raw="")
    result = await executor.execute(cmd)
    assert result["success"] is False
    assert "kaboom" in result["error"]


@pytest.mark.asyncio
async def test_unknown_service_does_not_crash(otel_trace):
    executor = CommandExecutor()
    cmd = ParsedCommand(service="ghost", action="x", params={}, raw="")
    result = await executor.execute(cmd)
    assert result == {"success": False, "error": "Unknown service: ghost"}
