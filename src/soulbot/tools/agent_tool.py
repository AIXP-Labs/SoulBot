"""AgentTool — wraps an Agent so it can be called as a tool by another Agent."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from .base_tool import BaseTool

if TYPE_CHECKING:
    from ..agents.base_agent import BaseAgent
    from ..agents.context import ToolContext


class AgentTool(BaseTool):
    """Expose an agent as a callable tool.

    When the parent LLM decides to call this tool, the wrapped agent is
    executed with the ``request`` text as a user message injected into the
    conversation.
    """

    def __init__(self, agent: "BaseAgent") -> None:
        super().__init__(name=agent.name, description=agent.description)
        self.agent = agent

    def get_declaration(self) -> Optional[dict]:
        return {
            "name": self.name,
            "description": self.description or f"Delegate to the {self.name} agent.",
            "parameters": {
                "type": "object",
                "properties": {
                    "request": {
                        "type": "string",
                        "description": "The request or question to send to this agent.",
                    }
                },
                "required": ["request"],
            },
        }

    async def run_async(
        self, *, args: dict[str, Any], tool_context: "ToolContext"
    ) -> Any:
        from ..events.event import Content, Event, Part

        ctx = tool_context.invocation_context

        # Inject the request as a user message
        request_text = args.get("request", "")
        if request_text:
            user_event = Event(
                author="user",
                invocation_id=ctx.invocation_id,
                branch=ctx.branch,
                content=Content(role="user", parts=[Part(text=request_text)]),
            )
            if ctx.session_service:
                await ctx.session_service.append_event(ctx.session, user_event)
            else:
                ctx.session.events.append(user_event)

        # Run the wrapped agent and collect results
        result_parts: list[str] = []
        async for event in self.agent.run_async(ctx):
            if ctx.session_service:
                await ctx.session_service.append_event(ctx.session, event)
            else:
                ctx.session.events.append(event)

            if event.content and not event.partial:
                for part in event.content.parts:
                    if part.text:
                        result_parts.append(part.text)

        return {"response": " ".join(result_parts)} if result_parts else {"response": ""}
