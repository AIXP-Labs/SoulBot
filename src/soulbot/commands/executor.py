"""CommandExecutor — route and execute parsed commands."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from .parser import ParsedCommand

# --- OTel instrumentation (soft-fail; see acp_llm.py pattern) ---
# Doc 12 v2.3 §7 Fix 8 + Fix 12: carry W3C traceparent/tracestate/baggage
# across SOULBOT_CMD envelope so deferred consumers (schedule, message.send)
# can link back to the originating trace.
try:
    from opentelemetry import context as otel_context
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode

    from ..observability.trace_context import extract_to_context, inject_current

    _OTEL_AVAILABLE = True
    _otel_tracer = trace.get_tracer("soulbot.commands")
except ImportError:
    _OTEL_AVAILABLE = False
    _otel_tracer = None


class _NoopSpan:
    def set_attribute(self, *a, **kw): pass
    def set_status(self, *a, **kw): pass
    def add_event(self, *a, **kw): pass
    def record_exception(self, *a, **kw): pass


class _NoopSpanCM:
    def __enter__(self): return _NoopSpan()
    def __exit__(self, *a): return False


logger = logging.getLogger(__name__)


class CommandExecutor:
    """Route commands to registered service objects.

    Services are plain Python objects whose methods serve as actions.
    Both sync and async methods are supported.

    Usage::

        executor = CommandExecutor()
        executor.register_service("math", MathService())
        result = await executor.execute(ParsedCommand(
            service="math", action="add", params={"a": 1, "b": 2}, raw="..."
        ))
    """

    def __init__(self) -> None:
        self._services: dict[str, object] = {}

    def register_service(self, name: str, service: object) -> None:
        """Register a service object. Method names become actions."""
        self._services[name] = service

    def unregister_service(self, name: str) -> bool:
        """Remove a service. Returns True if found."""
        return self._services.pop(name, None) is not None

    @property
    def services(self) -> list[str]:
        """Return registered service names."""
        return list(self._services.keys())

    async def execute(
        self,
        cmd: ParsedCommand,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a single command.

        Returns:
            ``{"success": True, "data": ...}`` or
            ``{"success": False, "error": "..."}``
        """
        # --- OTel Fix 8/12: hydrate context from envelope or snapshot current ---
        # Two paths:
        #   (a) envelope already carries otel_headers (deferred consumer case —
        #       schedule worker, replay) → extract into a fresh ctx and attach.
        #   (b) no headers yet (direct in-process dispatch) → snapshot current
        #       OTel context into cmd.otel_headers so any service that persists
        #       the envelope (schedule.add, message.send) preserves the trace.
        attach_token = None
        if _OTEL_AVAILABLE:
            if cmd.otel_headers:
                ctx = extract_to_context(cmd.otel_headers)
                attach_token = otel_context.attach(ctx)
            else:
                inject_current(cmd.otel_headers)

        span_cm = (
            _otel_tracer.start_as_current_span(
                f"command {cmd.service}.{cmd.action}",
                attributes={
                    "soulbot.command.service": cmd.service,
                    "soulbot.command.action": cmd.action,
                },
            )
            if _OTEL_AVAILABLE
            else _NoopSpanCM()
        )

        try:
            with span_cm as span:
                service = self._services.get(cmd.service)
                if service is None:
                    err = f"Unknown service: {cmd.service}"
                    if _OTEL_AVAILABLE:
                        span.set_status(Status(StatusCode.ERROR, err))
                    return {"success": False, "error": err}

                method = getattr(service, cmd.action, None)
                if method is None or not callable(method):
                    err = f"Unknown action: {cmd.service}.{cmd.action}"
                    if _OTEL_AVAILABLE:
                        span.set_status(Status(StatusCode.ERROR, err))
                    return {"success": False, "error": err}

                # Pop framework-level params before forwarding to service method
                params = dict(cmd.params)
                timeout = params.pop("timeout", None)

                try:
                    if asyncio.iscoroutinefunction(method):
                        coro = method(**params)
                        if timeout:
                            result = await asyncio.wait_for(coro, timeout=timeout)
                        else:
                            result = await coro
                    else:
                        result = method(**params)
                    if _OTEL_AVAILABLE:
                        span.set_status(Status(StatusCode.OK))
                    return {"success": True, "data": result}
                except asyncio.TimeoutError:
                    logger.warning(
                        "Command %s.%s timed out after %ss",
                        cmd.service, cmd.action, timeout,
                    )
                    if _OTEL_AVAILABLE:
                        span.set_status(Status(StatusCode.ERROR, "timeout"))
                    return {"success": False, "error": f"Timed out after {timeout}s"}
                except Exception as exc:
                    logger.warning(
                        "Command %s.%s failed: %s", cmd.service, cmd.action, exc,
                    )
                    if _OTEL_AVAILABLE:
                        span.record_exception(exc)
                        span.set_status(Status(StatusCode.ERROR, str(exc)[:200]))
                    return {"success": False, "error": str(exc)}
        finally:
            if attach_token is not None:
                otel_context.detach(attach_token)

    async def execute_all(
        self,
        commands: list[ParsedCommand],
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a batch of commands sequentially.

        Applies security rules:
        - Blocks nested scheduling (schedule commands from scheduled context).

        Returns:
            List of result dicts, one per command.
        """
        results: list[dict[str, Any]] = []
        for cmd in commands:
            # Security: block nested scheduling (unless explicitly allowed)
            if (
                context
                and context.get("type") == "scheduled"
                and cmd.service == "schedule"
                and not context.get("allow_nested_schedule", False)
            ):
                results.append({
                    "success": False,
                    "error": "Nested scheduling blocked",
                })
                continue
            # Heartbeat chain preservation: auto-inject origin_channel
            # so LLM doesn't need to remember to include it in SOULBOT_CMD
            if (
                context
                and context.get("origin_channel") == "heartbeat"
                and cmd.service == "schedule"
                and cmd.action == "add"
            ):
                cmd.params.setdefault("origin_channel", "heartbeat")
                cmd.params.setdefault("to_agent", context.get("to_agent", ""))

            # Agent Message (Doc 08) — sender-spoofing protection policy:
            #
            #   LAYER 1 (trusted source): LlmAgent._inject_cmd_routing already
            #   sets params["from_agent"] = self.name BEFORE execute_all runs.
            #   That is the authoritative identity for user-initiated chats.
            #
            #   LAYER 2 (chain anti-spoofing): when the command itself is
            #   running INSIDE a message dispatch (context.type == "message"),
            #   we force params["from_agent"] to context.to_agent — this
            #   prevents a receiver agent from pretending a downstream
            #   message came from someone else.
            #
            # NOTE on parent_id / depth (changed in fix-008):
            #   We do NOT auto-propagate parent_id+depth from the dispatch
            #   context anymore. Each LLM-initiated message.send is a NEW
            #   root (depth=0) by default — multi-round agent debates need
            #   this. The framework still maintains chain semantics for
            #   true callbacks: ``message_service._dispatch`` explicitly
            #   sets parent_id+depth+1 when synthesizing the callback
            #   message (``_build_callback_aisop``). LLM-initiated sends
            #   that happen to occur during a callback's processing are
            #   independent new roots, not chain continuations.
            #   Loop protection still applies via Layer 1 self-loop reject
            #   + per-sender rate limit (10/s default).
            #
            # If from_agent cannot be derived, reject.
            if (
                context is not None
                and cmd.service == "message"
                and cmd.action == "send"
            ):
                if context.get("type") == "message":
                    # Chained dispatch context: override LLM-supplied
                    # from_agent with the actual executing agent (anti-
                    # spoofing). Do NOT touch parent_id/depth — they stay
                    # at whatever the LLM (usually nothing) supplied so
                    # this send becomes a new root (depth=0).
                    executing_agent = (
                        context.get("to_agent") or context.get("from_agent", "")
                    )
                    if executing_agent:
                        cmd.params["from_agent"] = executing_agent
                # Forward origin_channel for audit trail
                if context.get("origin_channel"):
                    cmd.params.setdefault(
                        "origin_channel", context["origin_channel"],
                    )
                # Final safety: if nobody populated from_agent, reject.
                if not cmd.params.get("from_agent"):
                    results.append({
                        "success": False,
                        "error": (
                            "message.send blocked: no executing-agent "
                            "identity available. Either run inside an "
                            "LlmAgent (auto-injects from self.name) or a "
                            "message dispatch (populates context.to_agent)."
                        ),
                    })
                    continue

            result = await self.execute(cmd, context)
            results.append(result)
        return results
