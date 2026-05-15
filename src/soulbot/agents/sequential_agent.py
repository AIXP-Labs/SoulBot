"""SequentialAgent — executes sub-agents one after another."""

from __future__ import annotations

from typing import AsyncGenerator

from ..events.event import Event
from .base_agent import BaseAgent
from .invocation_context import InvocationContext


class SequentialAgent(BaseAgent):
    """Execute sub-agents sequentially in declaration order.

    Each sub-agent sees the full session history (including events
    produced by previous sub-agents), enabling pipeline-style workflows.

    Example::

        pipeline = SequentialAgent(
            name="pipeline",
            sub_agents=[researcher, writer, reviewer],
        )
    """

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        for agent in self.sub_agents:
            async for event in agent.run_async(ctx):
                yield event
                # Stop the pipeline if an agent signals escalation
                if event.actions and event.actions.escalate:
                    return
