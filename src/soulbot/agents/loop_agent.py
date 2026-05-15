"""LoopAgent — repeatedly executes sub-agents until a stop condition is met."""

from __future__ import annotations

from typing import AsyncGenerator

from ..events.event import Event
from .base_agent import BaseAgent
from .invocation_context import InvocationContext


class LoopAgent(BaseAgent):
    """Execute sub-agents in a loop.

    The loop continues until one of:
    - ``max_iterations`` is reached.
    - A sub-agent produces an event with ``actions.escalate = True``.

    Example::

        loop = LoopAgent(
            name="refine",
            sub_agents=[drafter, critic],
            max_iterations=3,
        )
    """

    max_iterations: int = 10

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        for _iteration in range(self.max_iterations):
            escalated = False
            for agent in self.sub_agents:
                async for event in agent.run_async(ctx):
                    yield event
                    if event.actions and event.actions.escalate:
                        escalated = True
                if escalated:
                    return
