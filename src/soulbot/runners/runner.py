"""Runner — drives agent execution and manages the session lifecycle."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, AsyncGenerator, Optional

from ..agents.base_agent import BaseAgent
from ..agents.invocation_context import InvocationContext, RunConfig
from ..events.event import Content, Event, Part
from ..sessions.base_session_service import BaseSessionService

if TYPE_CHECKING:
    from ..bus.event_bus import EventBus
    from ..commands.executor import CommandExecutor
    from ..history.base_history_service import BaseChatHistoryService

logger = logging.getLogger(__name__)


# --- Doc 22 P3: per-turn OTel span (soft-fail if observability not installed) ---
try:
    from opentelemetry import trace as _otel_trace

    _otel_tracer = _otel_trace.get_tracer("soulbot.runner")
    from ..observability import semconv as _sc

    _OTEL_AVAILABLE = True
except ImportError:
    _otel_tracer = None
    _sc = None
    _OTEL_AVAILABLE = False


class _NoopSpan:
    def set_attribute(self, *a, **kw): pass
    def set_status(self, *a, **kw): pass
    def add_event(self, *a, **kw): pass
    def record_exception(self, *a, **kw): pass


class _NoopSpanCM:
    def __enter__(self): return _NoopSpan()
    def __exit__(self, *a): return False


class Runner:
    """Runs an agent in the context of a session.

    Usage::

        runner = Runner(
            agent=my_agent,
            app_name="my_app",
            session_service=InMemorySessionService(),
        )

        async for event in runner.run(user_id="u1", session_id="s1", message="Hello"):
            print(event)
    """

    def __init__(
        self,
        *,
        agent: BaseAgent,
        app_name: str,
        session_service: BaseSessionService,
        bus: Optional[EventBus] = None,
        cmd_executor: Optional[CommandExecutor] = None,
        history_service: Optional[BaseChatHistoryService] = None,
        agents_registry: Optional[dict] = None,
    ) -> None:
        """Construct a Runner.

        Args:
            agents_registry: Optional mapping {agent_name: agent_obj} of all
                agents in this SoulBot instance (siblings of ``agent``).
                When provided, each LLM call auto-injects an
                ``[AVAILABLE AGENTS]`` section into the system prompt so the
                model knows which peers it can dispatch to via
                ``message.send``. Populated by ``cli.py`` from the agents
                dict; left None for ad-hoc / test Runners.
        """
        self.agent = agent
        self.app_name = app_name  # semantic: cli_name (Doc 21)
        self.agent_name = agent.name  # agent soft-classification key (Doc 21)
        self.session_service = session_service
        self.bus = bus
        self._cmd_executor = cmd_executor
        self._history_service = history_service
        self._agents_registry = agents_registry

    async def run(
        self,
        *,
        user_id: str,
        session_id: str,
        message: str,
        run_config: Optional[RunConfig] = None,
    ) -> AsyncGenerator[Event, None]:
        """Run the agent with a user message and yield events.

        Steps:
        1. Get or create the session.
        2. Append the user message as an event.
        3. Record user message to history (Doc 22).
        4. Create an InvocationContext.
        5. Execute the agent and yield events (appending each to the session).
        6. Record assistant response to history (Doc 22).
        """
        # 1. Get or create session
        # Plan 18 / 01: pass agent_name so cross-agent sessions sharing the
        # same cli_name partition return None (forcing fresh session creation).
        session = await self.session_service.get_session(
            self.app_name, user_id, session_id, agent_name=self.agent_name
        )
        if session is None:
            # Auto-generate title from first message (Doc 20)
            title = message[:30].strip()
            if len(message) > 30:
                title += "..."
            session = await self.session_service.create_session(
                self.app_name, user_id, agent_name=self.agent_name,
                session_id=session_id, title=title,
            )
        else:
            # Update last_agent if changed (Doc 21 — agent soft classification)
            if session.last_agent != self.agent_name:
                await self.session_service.update_last_agent(
                    self.app_name, user_id, session_id, self.agent_name
                )
                session.last_agent = self.agent_name

        # 1.5 User message length guard — suggest file-based workflow
        max_msg_len = run_config.max_message_length if run_config else None
        if max_msg_len and len(message) > max_msg_len:
            yield Event(
                author="system",
                content=Content(
                    role="model",
                    parts=[Part(text=(
                        f"消息长度 {len(message)} 字符超过建议上限 {max_msg_len}。\n"
                        "建议：将内容保存为文件，然后告诉我文件路径，我会读取后回复。"
                    ))],
                ),
            )
            return

        # 2. Create and append user event
        user_event = Event(
            author="user",
            content=Content(role="user", parts=[Part(text=message)]),
        )
        await self.session_service.append_event(session, user_event)

        # Publish session event
        if self.bus:
            from ..bus.events import BusEvent, SESSION_UPDATED

            await self.bus.publish(BusEvent(
                type=SESSION_UPDATED,
                data={"session_id": session_id, "user_id": user_id},
                source="runner",
            ))

        # 3. Record user message to chat history (Doc 22)
        if self._history_service:
            try:
                await self._history_service.add_message(
                    user_id, self.agent_name, session_id, "user", message,
                )
            except Exception as exc:
                logger.warning("History write failed (user): %s", exc)

        # 4. Create InvocationContext. If an agents_registry was supplied at
        # construction time, inject it into run_config.context so the
        # LlmAgent layer can surface an [AVAILABLE AGENTS] section in the
        # system prompt (方案 A — runtime discovery for message.send).
        rc = run_config or RunConfig()
        if self._agents_registry:
            ctx_dict = dict(rc.context or {})
            ctx_dict.setdefault("agents_registry", self._agents_registry)
            rc.context = ctx_dict
        ctx = InvocationContext(
            session=session,
            agent=self.agent,
            session_service=self.session_service,
            run_config=rc,
            bus=self.bus,
            cmd_executor=self._cmd_executor,
        )

        # Doc 22 P3: per-turn span — wraps the whole agent.run_async loop so
        # invoke_agent / pipeline.node subprocess spans inherit this trace_id
        # (the Web UI /observability/traces groups by trace_id, giving a
        # per-turn tree instead of a sprawling bootstrap trace).
        # Manual span management (vs `with`) avoids re-indenting the
        # existing async-for loop body and keeps diff minimal.
        _turn_index = sum(1 for e in session.events if e.author == "user")
        _turn_id = f"{session.id}.turn.{_turn_index}"
        _turn_span = None
        _turn_ctx_token = None
        if _OTEL_AVAILABLE:
            from opentelemetry import context as _otel_context

            _turn_span = _otel_tracer.start_span(
                f"turn {_turn_index}",
                attributes={
                    _sc.SOULBOT_TURN_ID: _turn_id,
                    _sc.SOULBOT_TURN_INDEX: _turn_index,
                    _sc.GEN_AI_CONVERSATION_ID: session.id,
                    _sc.GEN_AI_AGENT_NAME: self.agent_name,
                },
            )
            _turn_ctx_token = _otel_context.attach(
                _otel_trace.set_span_in_context(_turn_span),
            )

        try:
            # change B (plan20/38 §6.6): wrap the agent loop so a fatal subprocess
            # crash (event.error_code == "ACP_CRASH") auto-resumes the pipeline. The
            # engine's programExec.step3 CRASH RECOVERY picks up from last_completed_node;
            # WAITING_USER never produces ACP_CRASH, so this is fail-closed — it never
            # auto-advances a sovereignty gate.
            resume_count = 0
            # 2026-06-16: raised 5 -> 100 (user). soulacp max_turns=100000 removed the
            # turn-limit stop, so this OOM/ACP_CRASH auto-resume cap is now rarely hit;
            # 100 gives a long progressing run ample crash-recovery headroom before
            # escalating to a human. NOTE: this is a TOTAL crash count per turn (NOT
            # reset on progress) — a genuinely-stuck node spins up to ~100x (≈97min with
            # the 60s-capped backoff) before escalation; acceptable since OOM is now rare.
            # (reset-on-progress + small cap = backlog if OOM-on-long-runs recurs.)
            MAX_AUTO_RESUME = 100
            while True:
                crashed = False
                # 5. Execute agent and yield events (all under per-turn span)
                async for event in self.agent.run_async(ctx):
                    event.invocation_id = ctx.invocation_id

                    # change B: fatal crash signal — do NOT surface as a final
                    # response; the auto-resume below takes over.
                    if event.error_code == "ACP_CRASH":
                        crashed = True
                        continue

                    # CMD processing moved to LlmAgent layer (Doc 26)

                    # Don't persist partial (streaming) events to session history
                    if not event.partial:
                        await self.session_service.append_event(session, event)

                    # Publish agent response event
                    if self.bus and event.is_final_response():
                        from ..bus.events import BusEvent, AGENT_RESPONSE

                        text = ""
                        if event.content:
                            text = " ".join(
                                p.text for p in event.content.parts if p.text
                            )
                        # trigger_type distinguishes scheduled fires from
                        # user-triggered responses. Web SSE endpoint filters on
                        # this to avoid double-rendering (user responses are
                        # already delivered via /run_sse).
                        run_context = (run_config.context if run_config else None) or {}
                        trigger_type = run_context.get("type", "user")
                        await self.bus.publish(BusEvent(
                            type=AGENT_RESPONSE,
                            data={
                                "agent": event.author,
                                "text": text,
                                "session_id": session_id,
                                "trigger_type": trigger_type,
                            },
                            source="runner",
                        ))

                    # 6. Record assistant response to chat history (Doc 22)
                    #    Split L1 (human text) / L2 (audit JSON) before saving
                    if self._history_service and event.is_final_response():
                        final_text = ""
                        if event.content:
                            final_text = " ".join(
                                p.text for p in event.content.parts if p.text
                            )
                        if final_text:
                            try:
                                from ..l2_splitter import split_l2
                                split = split_l2(final_text)
                                await self._history_service.add_message(
                                    user_id, self.agent_name, session_id,
                                    "assistant", split.l1, l2_json=split.l2_json,
                                )
                            except Exception as exc:
                                logger.warning("History write failed (assistant): %s", exc)

                    yield event

                # change B: after the agent loop ends, decide whether to auto-resume.
                if not crashed:
                    if resume_count > 0:
                        # observability: pipeline recovered from one or more crashes
                        logger.warning(
                            "ACP pipeline resumed successfully after %d auto-resume(s) "
                            "(session=%s)", resume_count, session_id,
                        )
                    break  # normal completion or WAITING_USER (no ACP_CRASH) → done
                resume_count += 1
                if resume_count > MAX_AUTO_RESUME:
                    logger.error(
                        "ACP pipeline still crashing after %d auto-resumes; escalating to "
                        "human (session=%s)", MAX_AUTO_RESUME, session_id,
                    )
                    yield Event(
                        author="system",
                        content=Content(role="model", parts=[Part(text=(
                            f"⚠️ 节点崩溃(OOM)已自动续跑 {MAX_AUTO_RESUME} 次仍未完成,"
                            "请回复「继续执行任务」手动续跑,或考虑拆分该重节点。"
                        ))]),
                    )
                    break
                # Back off (give the V8 heap / OS time to recover), then re-trigger a
                # normal run. Same session_id — the engine's CRASH RECOVERY resumes from
                # last_completed_node; agent.py prepare_cache reuses the in_progress turn.
                delay = min(5 * 2 ** (resume_count - 1), 60)
                # observability: surface each auto-resume attempt in the log stream so a
                # crash→resume→success/escalation sequence is visible without cache traces.
                logger.warning(
                    "ACP_CRASH detected; auto-resuming pipeline (attempt %d/%d) after %ds "
                    "backoff (session=%s)", resume_count, MAX_AUTO_RESUME, delay, session_id,
                )
                await asyncio.sleep(delay)
                await self.session_service.append_event(session, Event(
                    author="user",
                    content=Content(role="user", parts=[Part(text="继续执行任务")]),
                ))
                ctx = InvocationContext(
                    session=session,
                    agent=self.agent,
                    session_service=self.session_service,
                    run_config=rc,
                    bus=self.bus,
                    cmd_executor=self._cmd_executor,
                )
        finally:
            # Doc 22 P3: always close the per-turn span, even on
            # GeneratorExit (client disconnect) or exception.
            if _turn_ctx_token is not None:
                from opentelemetry import context as _otel_context

                _otel_context.detach(_turn_ctx_token)
            if _turn_span is not None:
                _turn_span.end()
