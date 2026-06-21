"""ACP LLM adapter — connect to LLMs via CLI subprocess with connection pooling.

Uses the ACP (Agent Communication Protocol) JSON-RPC over stdio to communicate
with CLI tools (Claude Code, Gemini CLI, OpenCode, Cursor).  This allows using
subscription credentials without needing a separate API key.

Prerequisites (Claude):
    npm install -g @anthropic-ai/claude-code
    claude login

Usage::

    from soulbot.agents import LlmAgent
    agent = LlmAgent(name="my_agent", model="claude-acp/sonnet")
    agent = LlmAgent(name="my_agent", model="gemini-acp/pro")
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any, AsyncGenerator, ClassVar, Optional

from soulacp import ACPConfig, ACPConnectionPool, RPCError, resolve_client_class, resolve_provider
from soulacp.config import FALLBACK_MAP
from .base_llm import BaseLlm
from .llm_request import LlmRequest, LlmResponse

# --- OTel instrumentation (optional; soft-fail if observability extra not installed) ---
# Doc 12 v2.3 Phase 2: wrap ACPLlm.generate_content_async with span + metrics.
try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode

    from ..observability import semconv as sc
    from ..observability.acp_usage import (
        estimate_tokens,
        resolve_gen_ai_provider,
    )
    from ..observability.metrics import get_llm_histograms
    from ..observability.security import scan_for_injection

    _OTEL_AVAILABLE = True
    _otel_tracer = trace.get_tracer("soulbot.acp")
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

# Auth error keywords → re-login commands per provider
_AUTH_KEYWORDS = ("authentication required", "unauthorized", "not authenticated", "auth", "expired")
_RELOGIN_COMMANDS = {
    "claude": "claude login",
    "gemini": "gemini auth",
    "opencode": "opencode auth login",
    "openclaw": "openclaw login",
    "cursor": "cursor login",
}


def _enrich_auth_error(error_msg: str, model: str) -> str:
    """Append a re-login hint if the error looks like an auth failure."""
    lower = error_msg.lower()
    if not any(kw in lower for kw in _AUTH_KEYWORDS):
        return error_msg
    # Determine provider from model string (e.g. "claude-acp/sonnet" → "claude")
    provider = model.split("-")[0] if model else "claude"
    cmd = _RELOGIN_COMMANDS.get(provider, "claude login")
    return f"{error_msg}  [Hint: authentication may have expired. Run `{cmd}` to re-authenticate]"


def _extract_function_call(text: str) -> dict | None:
    """Extract a ``{"function_call": ...}`` JSON object from *text*.

    Uses a find-then-parse strategy: locate ``"function_call"`` in the text,
    walk back to the enclosing ``{``, then try ``json.loads`` on progressively
    longer substrings until a valid JSON object is found.  This handles
    nested braces and multi-line formatting correctly.
    """
    marker = '"function_call"'
    idx = text.find(marker)
    if idx == -1:
        return None

    # Walk backward to find the opening brace
    start = text.rfind("{", 0, idx)
    if start == -1:
        return None

    # Try parsing from start, extending end position via brace counting
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(text[start:i + 1])
                    if "function_call" in obj and "name" in obj["function_call"]:
                        return obj
                except (json.JSONDecodeError, TypeError):
                    pass
                return None
    return None


class ACPLlm(BaseLlm):
    """Adapter for LLMs via ACP CLI subprocesses with connection pooling.

    Supports multiple providers:
    - Claude (claude-acp/*) — via claude-code-acp CLI
    - Gemini (gemini-acp/*) — via gemini CLI
    - OpenCode (opencode-acp/*) — via opencode CLI
    - OpenClaw (openclaw/*) — via openclaw CLI (gateway-backed)
    - Cursor (cursor-cli/*) — via cursor-agent CLI (non-pooled)
    """

    _pools: ClassVar[dict[str, ACPConnectionPool]] = {}
    _provider_session_store: ClassVar[Optional[Any]] = None

    @classmethod
    def set_provider_session_store(cls, store: Any) -> None:
        """Inject a ProviderSessionStore for ACP session reuse (Doc 19)."""
        cls._provider_session_store = store

    @classmethod
    def supported_models(cls) -> list[str]:
        return [
            r"claude-acp/.*",
            r"gemini-acp/.*",
            r"opencode-acp/.*",
            r"openclaw/.*",
            r"cursor-cli/.*",
        ]

    async def generate_content_async(
        self, llm_request: LlmRequest, *, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        from ..events.event import Content, Part

        # change A (plan20/38 §6.6): set True on fatal subprocess exit (V8 OOM) so the
        # final yield reports error_code="ACP_CRASH" — Runner (change B) then auto-resumes
        # the pipeline from cache instead of surfacing a dead-end error.
        self._crashed = False
        provider = resolve_provider(self.model)
        skip_tools = provider == "openclaw"
        prompt = self._build_prompt(llm_request, skip_tools=skip_tools)
        pool = self._get_pool()

        # --- OTel: start outer span (soft-noop if observability extra not installed) ---
        # Doc 12 v2.3 §6.2: wrap whole ACP call with span; measure pool queue,
        # session rotation, retry events, TTFT for streaming, output length.
        # Doc 21 P2: gen_ai.conversation.id maps to SoulBot session_id
        # (populated by llm_agent.py _build_request metadata).
        _conversation_id = llm_request.metadata.get("session_id", "")

        _attrs: dict = {
            sc.GEN_AI_OPERATION_NAME: "invoke_agent",
            sc.GEN_AI_AGENT_NAME: getattr(self, "agent_name", ""),
            sc.GEN_AI_PROVIDER_NAME: resolve_gen_ai_provider(provider),
            sc.GEN_AI_REQUEST_MODEL: self.model,
            sc.ACP_PROVIDER_NAME: provider,
            sc.ACP_PROMPT_LENGTH_CHARS: len(prompt),
            sc.SOULBOT_STREAMING: stream,
            sc.GEN_AI_USAGE_INPUT_TOKENS: estimate_tokens(prompt),
        }
        if _conversation_id:
            _attrs[sc.GEN_AI_CONVERSATION_ID] = _conversation_id

        _span_cm = (
            _otel_tracer.start_as_current_span(
                f"invoke_agent stream {self.model}" if stream
                else f"invoke_agent {self.model}",
                attributes=_attrs,
            )
            if _OTEL_AVAILABLE
            else _NoopSpanCM()
        )

        with _span_cm as span:
            t_total_start = time.perf_counter()

            # --- Fix 13: prompt injection scan (observability-only, no blocking) ---
            # Scan final prompt for known attack patterns; emit span event for
            # alert_tailer to pick up. AlwaysKeepCriticalSampler ensures the
            # invoke_agent span is retained even under head sampling (via the
            # span event; separately, security.* prefix critical rule covers
            # dedicated security spans).
            if _OTEL_AVAILABLE:
                _injection_matches = scan_for_injection(prompt)
                if _injection_matches:
                    span.add_event(
                        "security.injection.suspected",
                        attributes={
                            "soulbot.security.agent": getattr(self, "agent_name", ""),
                            "soulbot.security.matched_patterns": _injection_matches[:3],
                            "soulbot.security.preview": prompt[:100],
                        },
                    )

            # --- ProviderSessionStore lookup (Doc 19) ---
            # Plan 18 / 01: scope key by agent_name so multiple agents sharing
            # the same CLI (provider) don't restore each other's CLI session.
            session_id: str | None = None
            user_id = llm_request.metadata.get("user_id")
            store = self._provider_session_store
            agent_name = getattr(self, "agent_name", "") or ""
            scoped_user = f"{agent_name}:{user_id}" if (agent_name and user_id) else user_id
            restored_from_store = False
            if store and user_id:
                try:
                    session_id = await store.get_session_id(scoped_user, provider)
                    restored_from_store = session_id is not None
                except Exception:
                    pass
            if _OTEL_AVAILABLE:
                span.set_attribute(sc.ACP_SESSION_RESTORED_FROM_STORE, restored_from_store)

            # Doc 10 A2: use config retries + catch TimeoutError + exponential backoff
            max_attempts = pool._config.max_retries
            base_delay = pool._config.retry_base_delay
            primary_err: Exception | None = None

            session_rotated = False  # Track whether we already rotated

            for attempt in range(1, max_attempts + 1):
                try:
                    # --- OTel: measure pool.acquire queue time ---
                    t_acquire_start = time.perf_counter()
                    async with pool.acquire(session_id=session_id) as (client, sid):
                        queue_time = time.perf_counter() - t_acquire_start
                        if _OTEL_AVAILABLE:
                            span.set_attribute(sc.ACP_POOL_QUEUE_TIME_S, round(queue_time, 4))
                            span.set_attribute(sc.ACP_POOL_ATTEMPT, attempt)
                            span.set_attribute(sc.ACP_SESSION_ID, sid or "")

                        # Detect session change (Doc 10 C3)
                        if session_id and sid != session_id:
                            logger.info("ACP session changed: %s -> %s (resume failed)", session_id, sid)
                            if _OTEL_AVAILABLE:
                                span.set_attribute(sc.ACP_SESSION_ROTATED, True)
                                span.add_event(
                                    "acp.session.rotated",
                                    {"old_session_id": session_id, "new_session_id": sid or ""},
                                )

                        # Save actual session_id back (Doc 19)
                        # Plan 18 / 01: store under agent-scoped key (see above)
                        if store and user_id and sid:
                            try:
                                await store.set_session_id(scoped_user, provider, sid)
                            except Exception:
                                pass

                        output_text = ""
                        ttft: float | None = None

                        if stream:
                            ttft_recorded = False
                            t_stream_start = time.perf_counter()
                            async for chunk in client.query_stream(prompt):
                                if not ttft_recorded:
                                    ttft = time.perf_counter() - t_stream_start
                                    if _OTEL_AVAILABLE:
                                        span.set_attribute(sc.GEN_AI_SERVER_TTFT, round(ttft, 4))
                                    ttft_recorded = True
                                output_text += chunk
                                yield LlmResponse(
                                    content=Content(role="model", parts=[Part(text=chunk)]),
                                    partial=True,
                                )
                            # Parse final accumulated text for function_call (Doc 25)
                            final = self._parse_response(output_text)
                            final.partial = False
                            yield final
                        else:
                            output_text = await client.query(prompt)
                            yield self._parse_response(output_text)

                        # --- OTel: record output + metrics ---
                        if _OTEL_AVAILABLE:
                            span.set_attribute(sc.ACP_OUTPUT_LENGTH_CHARS, len(output_text))
                            span.set_attribute(
                                sc.GEN_AI_USAGE_OUTPUT_TOKENS, estimate_tokens(output_text)
                            )
                            span.set_status(Status(StatusCode.OK))

                            total_duration = time.perf_counter() - t_total_start
                            labels = {
                                sc.GEN_AI_OPERATION_NAME: "invoke_agent",
                                sc.GEN_AI_PROVIDER_NAME: resolve_gen_ai_provider(provider),
                                sc.ACP_PROVIDER_NAME: provider,
                                sc.GEN_AI_REQUEST_MODEL: self.model,
                            }
                            try:
                                hist = get_llm_histograms()
                                hist.duration.record(total_duration, attributes=labels)
                                hist.acp_pool_queue_time.record(queue_time, attributes=labels)
                                if stream and ttft is not None:
                                    hist.acp_subprocess_ttft.record(ttft, attributes=labels)
                                hist.estimated_token_usage.record(
                                    estimate_tokens(prompt),
                                    attributes={**labels, sc.METRIC_TOKEN_TYPE: "input"},
                                )
                                hist.estimated_token_usage.record(
                                    estimate_tokens(output_text),
                                    attributes={**labels, sc.METRIC_TOKEN_TYPE: "output"},
                                )
                            except Exception as metric_err:
                                # Metrics recording must never break main pipeline
                                logger.debug("OTel metric record failed: %s", metric_err)

                    return  # success — exit (inside span context, auto-finalizes)
                except (ConnectionError, asyncio.TimeoutError) as ce:
                    # --- OTel: record retry as span event ---
                    if _OTEL_AVAILABLE:
                        span.add_event(
                            "acp.retry",
                            {
                                "attempt": attempt,
                                "error.type": type(ce).__name__,
                                "error.message": str(ce)[:200],
                            },
                        )
                    if attempt < max_attempts:
                        delay = min(base_delay * (2 ** (attempt - 1)), 30.0)
                        logger.warning(
                            "ACP error (attempt %d/%d), retrying in %.1fs: %s",
                            attempt, max_attempts, delay, ce,
                        )
                        # change A (plan20/38 §6.6): do NOT clear session_id — the
                        # session is user-controlled, the program must not spawn a new
                        # one. pool.acquire resumes the SAME session on a fresh subprocess;
                        # if resume keeps failing, the exhausted path below marks _crashed
                        # so Runner (change B) resumes the pipeline from cache.
                        await asyncio.sleep(delay)
                        continue
                    # Last attempt exhausted — connection is dead; treat as crash so
                    # Runner (change B) auto-resumes the pipeline (covers pipe-close OOM).
                    self._crashed = True
                    primary_err = ce
                    break
                except Exception as exc:
                    # --- Enrich span when this is a structured RPCError ---
                    # soulacp v2.0+ surfaces JSON-RPC code, method, elapsed,
                    # and stderr_tail; emit them as span attrs so opaque
                    # "Internal error" log lines have full provenance.
                    if isinstance(exc, RPCError):
                        if _OTEL_AVAILABLE:
                            if exc.code is not None:
                                span.set_attribute("acp.rpc.code", exc.code)
                            if exc.method:
                                span.set_attribute("acp.rpc.method", exc.method)
                            if exc.elapsed_ms is not None:
                                span.set_attribute("acp.rpc.elapsed_ms", exc.elapsed_ms)
                            if exc.stderr_tail:
                                span.set_attribute(
                                    "acp.rpc.stderr_tail",
                                    "\n".join(exc.stderr_tail[-10:])[:2000],
                                )
                            span.add_event(
                                "acp.rpc.error",
                                {
                                    "code": exc.code if exc.code is not None else 0,
                                    "message": exc.message[:200],
                                    "method": exc.method or "",
                                },
                            )
                        # change A (plan20/38 §6.6): fatal subprocess exit (V8 OOM) —
                        # re-sending the same giant prompt just re-OOMs, and the session
                        # is user-controlled (cannot rotate). Stop in-layer retry, mark
                        # crash, hand off to Runner (change B) which resumes the pipeline
                        # from last_completed_node via the engine's CRASH RECOVERY.
                        if exc._is_fatal_subprocess_exit():
                            logger.error(
                                "ACP fatal subprocess exit (no in-layer retry, "
                                "Runner will resume pipeline): %s", exc,
                            )
                            self._crashed = True
                            primary_err = exc
                            break
                        # Retry transient JSON-RPC codes (-32603, -32000~-32099)
                        # *unless* it is a context overflow — that needs
                        # session rotation, handled below.
                        if (
                            attempt < max_attempts
                            and exc.is_retryable
                            and "prompt is too long" not in str(exc).lower()
                        ):
                            delay = min(base_delay * (2 ** (attempt - 1)), 30.0)
                            logger.warning(
                                "ACP RPC retryable (attempt %d/%d, code=%s), retrying in %.1fs: %s",
                                attempt, max_attempts, exc.code, delay, exc,
                            )
                            # change A (plan20/38 §6.6): keep session_id (do NOT clear) —
                            # session is user-controlled; pool.acquire resumes it.
                            await asyncio.sleep(delay)
                            continue
                    # --- Session rotation on "Prompt is too long" ---
                    # CLI session memory is full. Discard the old session and
                    # retry once with a fresh session (new conversation).
                    # No history injection needed — [MEMORY] hint in sys prompt
                    # tells the agent to use search_history when it needs context.
                    if not session_rotated and "prompt is too long" in str(exc).lower():
                        logger.warning(
                            "CLI session context overflow (session=%s). "
                            "Rotating to fresh session.",
                            session_id,
                        )
                        session_rotated = True
                        session_id = None
                        if _OTEL_AVAILABLE:
                            span.set_attribute(sc.ACP_SESSION_ROTATED, True)
                            span.add_event(
                                "acp.session.rotated.prompt_too_long",
                                {"old_session_id": session_id or ""},
                            )
                        if store and user_id:
                            try:
                                await store.clear(user_id, provider)
                            except Exception:
                                pass
                        continue  # retry with fresh session, same prompt
                    # v2.3: auth error detection for downstream alert / span_status
                    if _OTEL_AVAILABLE and any(
                        kw in str(exc).lower() for kw in _AUTH_KEYWORDS
                    ):
                        span.set_attribute(sc.ACP_AUTH_ERROR_DETECTED, True)
                        span.add_event(
                            "acp.auth.error_detected",
                            {"error.message": str(exc)[:200]},
                        )
                    primary_err = exc
                    break

        # Attempt fallback if enabled
        config = self._get_config()
        fallback_model = FALLBACK_MAP.get(config.provider)
        if config.enable_fallback and fallback_model:
            logger.warning(
                "Primary %s failed (%s), falling back to %s",
                config.provider, primary_err, fallback_model,
            )
            try:
                async for resp in self._query_fallback(
                    prompt, fallback_model, stream
                ):
                    yield resp
                return
            except Exception as fallback_err:
                logger.error("Fallback also failed: %s", fallback_err)

        error_msg = str(primary_err)
        error_msg = _enrich_auth_error(error_msg, self.model)
        logger.error("ACP error: %s", error_msg)
        # change A (plan20/38 §6.6): signal a fatal crash distinctly (ACP_CRASH) so
        # Runner (change B) auto-resumes the pipeline; non-crash errors stay ACP_ERROR.
        yield LlmResponse(
            error_code="ACP_CRASH" if self._crashed else "ACP_ERROR",
            error_message=error_msg,
        )

    # ------------------------------------------------------------------
    # Fallback
    # ------------------------------------------------------------------

    async def _query_fallback(
        self, prompt: str, fallback_model: str, stream: bool
    ) -> AsyncGenerator[LlmResponse, None]:
        """Execute a query using a fallback model."""
        from ..events.event import Content, Part

        provider = resolve_provider(fallback_model)
        pool = self._get_pool_for(provider, fallback_model)

        async with pool.acquire() as (client, sid):
            if stream:
                full_text = ""
                async for chunk in client.query_stream(prompt):
                    full_text += chunk
                    yield LlmResponse(
                        content=Content(role="model", parts=[Part(text=chunk)]),
                        partial=True,
                    )
                final = self._parse_response(full_text)
                final.partial = False
                yield final
            else:
                text = await client.query(prompt)
                yield self._parse_response(text)

    # ------------------------------------------------------------------
    # Pool management
    # ------------------------------------------------------------------

    def _get_pool(self) -> ACPConnectionPool:
        """Get or create a connection pool for the current provider."""
        provider = resolve_provider(self.model)
        return self._get_pool_for(provider, self.model)

    @staticmethod
    def _build_extra_env() -> dict[str, str]:
        """Forward parent NODE_OPTIONS into the ACP subprocess so it overrides
        soulacp claude_client's unconditional setdefault(--max-old-space-size=8192)
        (adapters/claude_client.py:44 + base_client.py:320 env.update clobbers a
        bare parent NODE_OPTIONS). Unset -> {} (soulacp keeps 8192, no change)."""
        extra_env: dict[str, str] = {}
        node_opts = os.environ.get("NODE_OPTIONS", "").strip()
        if node_opts:
            extra_env["NODE_OPTIONS"] = node_opts
        return extra_env

    def _get_config(self) -> ACPConfig:
        """Get config for the current model."""
        provider = resolve_provider(self.model)
        return ACPConfig.from_env(
            provider=provider, model=self.model, extra_env=self._build_extra_env()
        )

    @classmethod
    def _get_pool_for(cls, provider: str, model: str) -> ACPConnectionPool:
        """Get or create a pool for a specific provider+model (Doc 10 C5).

        Pools are isolated per event loop: soulacp's CLI subprocesses
        bind stdin/stdout to the spawning loop, so reusing a client
        across loops raises "Future attached to a different loop".
        SoulBot runs Telegram bot in a background thread (its own loop)
        and Web UI on uvicorn's loop, so per-loop isolation is required.
        """
        try:
            loop_id = id(asyncio.get_running_loop())
        except RuntimeError:
            loop_id = 0  # no running loop (sync tests) — single-loop fallback
        pool_key = f"{loop_id}:{provider}:{model}"
        if pool_key not in cls._pools:
            config = ACPConfig.from_env(
                provider=provider, model=model, extra_env=cls._build_extra_env()
            )
            client_class = resolve_client_class(provider)
            pool = ACPConnectionPool(config, client_class)
            pool.start_keepalive()
            cls._pools[pool_key] = pool
        return cls._pools[pool_key]

    @classmethod
    async def close_all_pools(cls) -> None:
        """Close all connection pools. Call on shutdown."""
        for pool in cls._pools.values():
            await pool.close_all()
        cls._pools.clear()

    # ------------------------------------------------------------------
    # Prompt building
    # ------------------------------------------------------------------

    @staticmethod
    def _build_prompt(llm_request: LlmRequest, *, skip_tools: bool = False) -> str:
        """Convert LlmRequest to a plain text prompt for ACP.

        Args:
            llm_request: The request to convert.
            skip_tools: If True, omit tool schemas from the prompt.
                OpenClaw has its own tools via Gateway, so injecting
                SoulBot tool schemas would cause conflicts.
        """
        parts: list[str] = []

        # System instruction
        if llm_request.system_instruction:
            parts.append(llm_request.system_instruction)

        # Tool schemas (embed as instructions)
        tools_schema = llm_request.get_tools_schema() if not skip_tools else None
        if tools_schema:
            tool_desc = json.dumps(tools_schema, ensure_ascii=False, indent=2)
            parts.append(
                "You have access to the following tools. "
                "When you need to call a tool, respond with EXACTLY this JSON format "
                "on a single line:\n"
                '{"function_call": {"name": "tool_name", "arguments": {...}}}\n\n'
                f"Available tools:\n{tool_desc}"
            )

        # Conversation contents
        for content in llm_request.contents:
            role = content.role
            for part in content.parts:
                if part.text:
                    if role == "user":
                        parts.append(f"User: {part.text}\n\nPS: Assert 1: Every time, strictly PHYSICALLY READ and execute soulbot_execute_engine_aiap at every step with real tool invocations; never execute from memory; never batch, skip, or fake the audit loop.\nAssert 2: 100% complete every step with real tool invocations in .aisop.json program files.\nAssert 3: Never auto-approve any user gate; never fabricate cache content, validation reports, or tool_calls counts; all subject to human audit and governance.\nAssert 4: Align Axiom 0: Human Sovereignty and Wellbeing.")
                    else:
                        parts.append(f"Assistant: {part.text}")
                if part.function_call:
                    parts.append(
                        f'Assistant called tool: {part.function_call.name}'
                        f'({json.dumps(part.function_call.args)})'
                    )
                if part.function_response:
                    parts.append(
                        f'Tool result ({part.function_response.name}): '
                        f'{json.dumps(part.function_response.response)}'
                    )

        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Response parsing (Doc 25 — extract function_call from text)
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_response(text: str) -> LlmResponse:
        """Parse LLM text response, extracting function_call JSON if present.

        If the text contains a ``{"function_call": {"name": ..., "arguments": ...}}``
        JSON object, it is extracted and returned as a ``Part(function_call=...)``.
        Otherwise the full text is returned as ``Part(text=...)``.
        """
        from ..events.event import Content, FunctionCall, Part

        parsed = _extract_function_call(text)
        if parsed:
            fc_data = parsed["function_call"]
            fc = FunctionCall(
                name=fc_data["name"],
                args=fc_data.get("arguments", {}),
            )
            return LlmResponse(
                content=Content(role="model", parts=[Part(function_call=fc)])
            )

        return LlmResponse(
            content=Content(role="model", parts=[Part(text=text)])
        )
