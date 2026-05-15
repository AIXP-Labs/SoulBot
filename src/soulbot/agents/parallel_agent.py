"""ParallelAgent — executes sub-agents concurrently with branch isolation."""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator

from ..events.event import Event
from .base_agent import BaseAgent
from .invocation_context import InvocationContext


class ParallelAgent(BaseAgent):
    """Execute sub-agents in parallel, each in an isolated branch.

    Each sub-agent receives a copy of the invocation context with a unique
    ``branch`` identifier.  This ensures that the conversation history
    each sub-agent sees is isolated from the others.

    Events from all branches are yielded after all sub-agents complete.

    Example::

        parallel = ParallelAgent(
            name="research",
            sub_agents=[web_searcher, db_searcher, api_searcher],
        )
    """

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        if not self.sub_agents:
            return

        # Run all sub-agents concurrently with branch isolation
        tasks = [
            self._collect_events(agent, ctx) for agent in self.sub_agents
        ]
        all_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Yield events from each branch in order
        for agent, result in zip(self.sub_agents, all_results):
            if isinstance(result, Exception):
                yield Event(
                    author=self.name,
                    invocation_id=ctx.invocation_id,
                    error_code="PARALLEL_ERROR",
                    error_message=f"Sub-agent '{agent.name}' failed: {result}",
                )
            else:
                for event in result:
                    yield event

    async def _collect_events(
        self, agent: BaseAgent, parent_ctx: InvocationContext
    ) -> list[Event]:
        """Run a sub-agent in an isolated branch and collect its events."""
        # Create a branch context — the branch field isolates conversation history
        branch_ctx = parent_ctx.model_copy()
        branch_ctx.branch = f"{self.name}.{agent.name}"

        events: list[Event] = []
        async for event in agent.run_async(branch_ctx):
            event.branch = branch_ctx.branch
            events.append(event)
        return events
