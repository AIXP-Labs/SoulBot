"""LlmAgent — an agent powered by a large language model."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, AsyncGenerator, Callable, Optional, Union

from pydantic import Field

from ..events.event import Content, Event, FunctionCall, FunctionResponse, Part
from ..events.event_actions import EventActions
from ..models.llm_request import GenerateContentConfig, LlmRequest, LlmResponse
from ..models.registry import ModelRegistry
from ..tools.base_tool import BaseTool
from ..tools.function_tool import FunctionTool
from .base_agent import BaseAgent
from .invocation_context import InvocationContext

logger = logging.getLogger(__name__)

# Callback type aliases
BeforeModelCallback = Callable[..., Optional[LlmResponse]]
AfterModelCallback = Callable[..., Optional[LlmResponse]]
BeforeToolCallback = Callable[..., Optional[dict]]
AfterToolCallback = Callable[..., Optional[dict]]


class LlmAgent(BaseAgent):
    """An agent driven by an LLM with optional tool-calling support.

    Attributes:
        model: Model identifier (e.g. ``"gpt-4o-mini"``).
        instruction: System instruction.  Supports ``{state_key}`` variable
            substitution from session state.  Can also be a callable that
            receives the :class:`InvocationContext` and returns a string.
        tools: List of tools (``BaseTool`` instances or plain functions).
        generate_content_config: Generation parameters.
        output_key: If set, the agent's final text response is written to
            ``session.state[output_key]`` automatically.
        include_contents: Controls which conversation events are sent to the LLM.

            - ``"default"`` — full history (with ``max_history_events`` sliding window).
            - ``"current_turn"`` — only events from the latest user message onward.
              **Recommended for ACP models** where the CLI subprocess maintains its
              own session memory; sending full history would duplicate context.
            - ``"none"`` — no conversation history (instruction + tools only).
    """

    model: str = ""
    instruction: Union[str, Callable[..., str]] = ""
    tools: list[Any] = Field(default_factory=list)

    generate_content_config: Optional[GenerateContentConfig] = None
    include_contents: str = "default"
    output_key: Optional[str] = None

    # Heartbeat configuration — None means disabled.
    # Example: {"cron": "0 0 * * *", "aisop": "heartbeat"}
    heartbeat: Optional[dict] = None

    # Callbacks
    before_model_callback: Optional[BeforeModelCallback] = Field(
        default=None, exclude=True
    )
    after_model_callback: Optional[AfterModelCallback] = Field(
        default=None, exclude=True
    )
    before_tool_callback: Optional[BeforeToolCallback] = Field(
        default=None, exclude=True
    )
    after_tool_callback: Optional[AfterToolCallback] = Field(
        default=None, exclude=True
    )

    def model_post_init(self, _context) -> None:
        """Normalize tools and wire up sub-agents."""
        super().model_post_init(_context)
        self.tools = [self._ensure_tool(t) for t in self.tools]

    # ------------------------------------------------------------------
    # Core execution
    # ------------------------------------------------------------------

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """LLM call loop: build request → call model → handle tool calls → repeat."""
        # Publish agent start
        await self._bus_publish(ctx, "agent.start", {"agent": self.name, "model": self.model})

        while not ctx.end_invocation:
            ctx.increment_llm_call_count()

            # 1. Build LlmRequest
            llm_request = self._build_request(ctx)

            # 2. before_model_callback
            if self.before_model_callback:
                override = self.before_model_callback(ctx, llm_request)
                if override is not None:
                    event = self._response_to_event(ctx, override)
                    yield event
                    if self._is_terminal(event):
                        break
                    continue

            # 3. Call the model
            await self._bus_publish(ctx, "llm.request", {"model": llm_request.model or self.model})

            llm = ModelRegistry.resolve(llm_request.model or self.model)
            llm_response: Optional[LlmResponse] = None
            _stream = ctx.run_config.streaming
            try:
                async with asyncio.timeout(ctx.run_config.llm_timeout):
                    async for resp in llm.generate_content_async(llm_request, stream=_stream):
                        llm_response = resp
                        # In streaming, yield partial events
                        if resp.partial:
                            yield Event(
                                author=self.name,
                                invocation_id=ctx.invocation_id,
                                branch=ctx.branch,
                                content=resp.content,
                                partial=True,
                            )
            except asyncio.TimeoutError:
                _t = ctx.run_config.llm_timeout
                await self._bus_publish(ctx, "llm.error", {"error": "TIMEOUT"})
                yield Event(
                    author=self.name,
                    invocation_id=ctx.invocation_id,
                    branch=ctx.branch,
                    error_code="TIMEOUT",
                    error_message=f"LLM call timed out after {_t}s",
                )
                break

            if llm_response is None:
                await self._bus_publish(ctx, "llm.error", {"error": "NO_RESPONSE"})
                yield Event(
                    author=self.name,
                    invocation_id=ctx.invocation_id,
                    branch=ctx.branch,
                    error_code="NO_RESPONSE",
                    error_message="Model returned no response",
                )
                break

            # Handle error
            if llm_response.error_code:
                await self._bus_publish(ctx, "llm.error", {
                    "error": llm_response.error_code,
                    "message": llm_response.error_message or "",
                })
                yield Event(
                    author=self.name,
                    invocation_id=ctx.invocation_id,
                    branch=ctx.branch,
                    error_code=llm_response.error_code,
                    error_message=llm_response.error_message,
                )
                break

            await self._bus_publish(ctx, "llm.response", {"model": self.model})

            # 4. after_model_callback
            if self.after_model_callback:
                override = self.after_model_callback(ctx, llm_response)
                if override is not None:
                    llm_response = override

            # 5. Build the model event
            model_event = self._response_to_event(ctx, llm_response)

            # 6. Check for function calls
            function_calls = model_event.get_function_calls()
            if function_calls:
                # Yield the model's function call event
                yield model_event

                # Publish tool calls
                for fc in function_calls:
                    await self._bus_publish(ctx, "tool.call", {
                        "tool": fc.name, "args": fc.args,
                    })

                # Execute tools and build response event
                tool_response_event = await self._handle_function_calls(
                    ctx, llm_request, function_calls
                )

                # Publish tool results
                for part in (tool_response_event.content.parts if tool_response_event.content else []):
                    if part.function_response:
                        await self._bus_publish(ctx, "tool.result", {
                            "tool": part.function_response.name,
                            "response": part.function_response.response,
                        })

                yield tool_response_event

                # Check for transfer
                if tool_response_event.actions.transfer_to_agent:
                    transfer_target = tool_response_event.actions.transfer_to_agent
                    await self._bus_publish(ctx, "agent.transfer", {
                        "from": self.name, "to": transfer_target,
                    })
                    target_agent = self.find_agent(transfer_target)
                    if target_agent:
                        async for event in target_agent.run_async(ctx):
                            yield event
                    break

                # Loop continues — LLM will see tool results
                continue

            # 6.5 Check for SOULBOT_CMD (system tools — Doc 26)
            if ctx.cmd_executor:
                cmd_text = " ".join(
                    p.text for p in (
                        model_event.content.parts if model_event.content else []
                    ) if p.text
                )
                from ..commands.parser import parse_commands

                commands, cleaned = parse_commands(cmd_text)
                if commands:
                    # Strip CMD markers — user sees clean text
                    # Create new Content to avoid mutating the original LlmResponse
                    model_event.content = Content(
                        role=model_event.content.role,
                        parts=[Part(text=cleaned)],
                    )
                    yield model_event

                    # Inject routing info
                    self._inject_cmd_routing(ctx, commands)

                    # Execute commands
                    run_context = ctx.run_config.context or {}
                    _cmd_timeout = ctx.run_config.cmd_timeout
                    try:
                        _coro = ctx.cmd_executor.execute_all(
                            commands, context=run_context
                        )
                        if _cmd_timeout:
                            results = await asyncio.wait_for(_coro, timeout=_cmd_timeout)
                        else:
                            results = await _coro
                    except asyncio.TimeoutError:
                        logger.error("CMD execution timed out after %ss", _cmd_timeout)
                        results = [
                            {"success": False, "error": f"Timed out after {_cmd_timeout}s"}
                            for _ in commands
                        ]
                    except Exception as exc:
                        logger.error("CMD execution failed: %s", exc)
                        results = [
                            {"success": False, "error": str(exc)}
                            for _ in commands
                        ]

                    # Build function_response event (same format as tool results)
                    cmd_parts: list[Part] = []
                    for cmd, result in zip(commands, results):
                        if result.get("success"):
                            response_data = result.get("data", {})
                        else:
                            response_data = {
                                "error": result.get("error", "Unknown error")
                            }
                        if not isinstance(response_data, dict):
                            response_data = {"result": response_data}
                        cmd_parts.append(Part(
                            function_response=FunctionResponse(
                                name=f"{cmd.service}.{cmd.action}",
                                response=response_data,
                            )
                        ))

                    cmd_response_event = Event(
                        author=self.name,
                        invocation_id=ctx.invocation_id,
                        branch=ctx.branch,
                        content=Content(role="user", parts=cmd_parts),
                    )
                    yield cmd_response_event

                    # Publish CMD execution events
                    for cmd, result in zip(commands, results):
                        await self._bus_publish(ctx, "cmd.executed", {
                            "service": cmd.service,
                            "action": cmd.action,
                            "success": result.get("success", False),
                        })

                    continue  # back to while — LLM sees function_response

            # 7. Final text response
            yield model_event
            self._apply_output_key(ctx, model_event)
            break

    # ------------------------------------------------------------------
    # Request building
    # ------------------------------------------------------------------

    def _build_request(self, ctx: InvocationContext) -> LlmRequest:
        """Build the LlmRequest for this turn."""
        config = self.generate_content_config or GenerateContentConfig()
        request = LlmRequest(
            model=self.model,
            config=config,
        )

        # System instruction
        instruction = self._render_instruction(ctx)
        if instruction:
            request.system_instruction = instruction

        # Conversation contents
        if self.include_contents == "current_turn":
            request.contents = self._build_current_turn_contents(ctx)
        elif self.include_contents == "default":
            request.contents = self._build_contents(ctx)

        # Tools
        resolved_tools = self._resolve_tools()
        if resolved_tools:
            request.append_tools(resolved_tools)

        # Propagate user context for downstream stores (Doc 19)
        request.metadata["user_id"] = ctx.session.user_id

        # Doc 21 P2: propagate session_id so invoke_agent span can set
        # gen_ai.conversation.id (OTel GenAI semconv for dashboard grouping)
        request.metadata["session_id"] = ctx.session.id

        return request

    def _render_instruction(self, ctx: InvocationContext) -> str:
        """Render the instruction, substituting {state_key} placeholders.

        Also auto-appends an ``[AVAILABLE AGENTS]`` block if the Runner
        supplied an ``agents_registry`` via ``run_config.context``. This
        lets the LLM know which peers it can dispatch to via
        ``SOULBOT_CMD service='message'`` — no need to hardcode names.
        """
        if callable(self.instruction):
            raw = self.instruction(ctx)
        else:
            raw = self.instruction

        # Substitute {key} from session state in the raw part
        def _replace(match: re.Match) -> str:
            key = match.group(1)
            val = ctx.session.state.get(key)
            if val is not None:
                return str(val)
            return match.group(0)  # leave as-is if not found

        rendered = re.sub(r"\{(\w[\w:.]*)\}", _replace, raw) if raw else ""

        # Append peer-agent registry hint (if available). Skip self (the
        # agent would never send a message to itself — self-loop is
        # rejected by the framework anyway).
        registry = (
            (ctx.run_config.context or {}).get("agents_registry")
            if ctx.run_config else None
        )
        if registry:
            lines = ["\n\n[AVAILABLE AGENTS IN THIS INSTANCE]"]
            for name, ag in sorted(registry.items()):
                if name == self.name:
                    continue
                desc = getattr(ag, "description", "") or "(no description)"
                # Truncate description to one line for prompt economy
                desc_line = desc.strip().split("\n", 1)[0][:200]
                lines.append(f"- {name}: {desc_line}")
            if len(lines) > 1:  # at least one peer
                lines.append(
                    "Use these names as ``to_agent`` in SOULBOT_CMD message.send."
                )
                rendered = rendered + "\n".join(lines)

        return rendered

    def _build_contents(self, ctx: InvocationContext) -> list[Content]:
        """Collect conversation history from session events.

        Applies a sliding window (``RunConfig.max_history_events``) to
        prevent the prompt from exceeding the model's context window in
        long-running sessions.
        """
        events = ctx.session.events

        # Apply sliding window — keep only the most recent N events
        max_events = ctx.run_config.max_history_events
        if max_events and max_events > 0 and len(events) > max_events:
            events = events[-max_events:]

        contents: list[Content] = []
        for event in events:
            # Filter by branch if set
            if ctx.branch and event.branch and event.branch != ctx.branch:
                continue
            if event.content and not event.partial:
                contents.append(event.content)
        return contents

    def _build_current_turn_contents(self, ctx: InvocationContext) -> list[Content]:
        """Only include events from the latest user message onward.

        Recommended for ACP models where the CLI subprocess maintains its
        own session memory (``session/prompt`` appends to the same conversation).
        Sending full history would duplicate what the CLI already knows,
        causing the prompt to grow quadratically and eventually hit
        "Prompt is too long" errors.

        Events included: latest user message + any tool_call / tool_response
        events from the current turn (same invocation).
        """
        events = ctx.session.events
        if not events:
            return []

        # Find the index of the last user event
        last_user_idx = -1
        for i in range(len(events) - 1, -1, -1):
            if events[i].author == "user":
                last_user_idx = i
                break

        if last_user_idx < 0:
            return []

        contents: list[Content] = []
        for event in events[last_user_idx:]:
            if ctx.branch and event.branch and event.branch != ctx.branch:
                continue
            if event.content and not event.partial:
                contents.append(event.content)
        return contents

    def _resolve_tools(self) -> list[BaseTool]:
        """Return the list of tools as BaseTool instances.

        Automatically injects :class:`TransferToAgentTool` when the agent
        has sub_agents that can be transferred to.
        """
        tools: list[BaseTool] = [t for t in self.tools if isinstance(t, BaseTool)]

        # Auto-inject TransferToAgentTool when sub_agents exist
        transfer_targets = self._get_transfer_targets()
        if transfer_targets:
            from ..tools.transfer_to_agent_tool import TransferToAgentTool

            tools.append(TransferToAgentTool(transfer_targets))

        return tools

    def _get_transfer_targets(self) -> list[dict[str, str]]:
        """Compute the list of agents this agent can transfer to."""
        targets: list[dict[str, str]] = []
        # Sub-agents are always transferable
        for sub in self.sub_agents:
            targets.append({"name": sub.name, "description": sub.description})
        return targets

    # ------------------------------------------------------------------
    # CMD routing (Doc 26)
    # ------------------------------------------------------------------

    def _inject_cmd_routing(
        self, ctx: InvocationContext, commands: list
    ) -> None:
        """Inject routing metadata for schedule / message commands.

        Doc 17: schedule.add — origin_channel / origin_user / from_agent / to_agent
        Doc 08: message.send — from_agent (self.name is the authoritative
                source; the executor layer's anti-spoofing override applies
                ONLY for chained dispatches where context.type='message').
        """
        run_context = ctx.run_config.context or {}
        for cmd in commands:
            if cmd.service == "schedule" and cmd.action == "add":
                cmd.params.setdefault(
                    "origin_channel", run_context.get("channel", ""),
                )
                cmd.params.setdefault(
                    "origin_user", run_context.get("user_id", ""),
                )
                cmd.params.setdefault("from_agent", self.name)
                cmd.params.setdefault(
                    "to_agent", cmd.params.get("to_agent", self.name),
                )
            elif cmd.service == "message" and cmd.action == "send":
                # Inject sender identity from the executing agent (self.name).
                # LLM-supplied from_agent is overwritten here to prevent
                # spoofing — regardless of what the model wrote.
                cmd.params["from_agent"] = self.name

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    async def _handle_function_calls(
        self,
        ctx: InvocationContext,
        llm_request: LlmRequest,
        function_calls: list[FunctionCall],
    ) -> Event:
        """Execute function calls (in parallel) and return a tool response event."""
        tasks = [
            self._run_single_tool(ctx, llm_request, fc) for fc in function_calls
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        parts: list[Part] = []
        actions = EventActions()

        for fc, result in zip(function_calls, results):
            if isinstance(result, Exception):
                response_data = {"error": str(result)}
            else:
                response_data, result_actions = result
                # Merge actions
                if result_actions:
                    if result_actions.transfer_to_agent:
                        actions.transfer_to_agent = result_actions.transfer_to_agent
                    if result_actions.escalate:
                        actions.escalate = result_actions.escalate
                    actions.state_delta.update(result_actions.state_delta)

            if not isinstance(response_data, dict):
                response_data = {"result": response_data}

            parts.append(
                Part(
                    function_response=FunctionResponse(
                        name=fc.name, response=response_data, id=fc.id
                    )
                )
            )

        return Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            branch=ctx.branch,
            content=Content(role="user", parts=parts),
            actions=actions,
        )

    async def _run_single_tool(
        self,
        ctx: InvocationContext,
        llm_request: LlmRequest,
        fc: FunctionCall,
    ) -> tuple[Any, Optional[EventActions]]:
        """Execute a single tool call with before/after callbacks."""
        tool = llm_request.tools_dict.get(fc.name)
        if tool is None:
            return {"error": f"Unknown tool: {fc.name}"}, None

        args = fc.args

        # before_tool_callback
        if self.before_tool_callback:
            override = self.before_tool_callback(ctx, fc.name, args)
            if override is not None:
                return override, None

        # Create a ToolContext
        from .context import Context

        tool_ctx = Context(
            invocation_context=ctx,
            agent_name=self.name,
            function_call_id=fc.id,
        )

        # Execute the tool (with optional timeout)
        _tool_timeout = tool.timeout or ctx.run_config.tool_timeout
        try:
            if _tool_timeout:
                result = await asyncio.wait_for(
                    tool.run_async(args=args, tool_context=tool_ctx),
                    timeout=_tool_timeout,
                )
            else:
                result = await tool.run_async(args=args, tool_context=tool_ctx)
        except asyncio.TimeoutError:
            return {"error": f"Tool '{fc.name}' timed out after {_tool_timeout}s"}, None

        # Flush state delta from tool context
        tool_ctx.commit_state_delta()

        # after_tool_callback
        if self.after_tool_callback:
            override = self.after_tool_callback(ctx, fc.name, result)
            if override is not None:
                result = override

        return result, tool_ctx.actions

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _response_to_event(
        self, ctx: InvocationContext, response: LlmResponse
    ) -> Event:
        """Convert an LlmResponse to an Event."""
        return Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            branch=ctx.branch,
            content=response.content,
            partial=response.partial,
        )

    @staticmethod
    def _is_terminal(event: Event) -> bool:
        """Check if an event should end the loop."""
        if not event.content:
            return True
        return event.is_final_response()

    def _apply_output_key(self, ctx: InvocationContext, event: Event) -> None:
        """If output_key is set, save the final text to session state."""
        if not self.output_key or not event.content:
            return
        text_parts = [p.text for p in event.content.parts if p.text]
        if text_parts:
            ctx.session.state[self.output_key] = " ".join(text_parts)

    @staticmethod
    def _ensure_tool(tool: Any) -> BaseTool:
        """Auto-wrap plain functions as FunctionTool."""
        if isinstance(tool, BaseTool):
            return tool
        if callable(tool):
            return FunctionTool(tool)
        raise TypeError(
            f"Expected BaseTool or callable, got {type(tool).__name__}"
        )

    @staticmethod
    async def _bus_publish(ctx: InvocationContext, event_type: str, data: dict) -> None:
        """Publish an event to the bus if available. No-op if bus is None."""
        if ctx.bus is None:
            return
        from ..bus.events import BusEvent

        await ctx.bus.publish(BusEvent(type=event_type, data=data, source="llm_agent"))
