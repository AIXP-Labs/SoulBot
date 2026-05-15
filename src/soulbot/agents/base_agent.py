"""BaseAgent — abstract base class for all agent types."""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, AsyncGenerator, Callable, Optional

from pydantic import BaseModel, Field

from ..events.event import Content, Event

if TYPE_CHECKING:
    from .invocation_context import InvocationContext

# Callback type aliases
BeforeAgentCallback = Callable[..., Optional[Content]]
AfterAgentCallback = Callable[..., Optional[Content]]


class BaseAgent(BaseModel):
    """Base class for all agents.

    Subclasses must implement :meth:`_run_async_impl` which contains
    the agent-specific execution logic.
    """

    model_config = {"arbitrary_types_allowed": True}

    name: str
    """Unique identifier.  Must be a valid Python identifier."""

    description: str = ""
    """Human-readable summary, used by other agents for routing decisions."""

    parent_agent: Optional["BaseAgent"] = Field(default=None, exclude=True)
    """Set automatically when this agent is added as a sub-agent."""

    sub_agents: list["BaseAgent"] = Field(default_factory=list)
    """Child agents that this agent can delegate to."""

    before_agent_callback: Optional[BeforeAgentCallback] = Field(default=None, exclude=True)
    after_agent_callback: Optional[AfterAgentCallback] = Field(default=None, exclude=True)

    def model_post_init(self, _context) -> None:
        """Wire up parent_agent references after construction."""
        for sub in self.sub_agents:
            sub.parent_agent = self

    # ------------------------------------------------------------------
    # Public entry point (final — do not override)
    # ------------------------------------------------------------------

    async def run_async(
        self, ctx: "InvocationContext"
    ) -> AsyncGenerator[Event, None]:
        """Run this agent within *ctx* and yield events.

        Handles before/after callbacks automatically.  Subclasses should
        only override :meth:`_run_async_impl`.
        """
        # --- before_agent_callback ---
        if self.before_agent_callback:
            result = self.before_agent_callback(ctx)
            if result is not None:
                yield Event(author=self.name, content=result)
                return

        # --- core execution ---
        async for event in self._run_async_impl(ctx):
            yield event

        # --- after_agent_callback ---
        if self.after_agent_callback:
            result = self.after_agent_callback(ctx)
            if result is not None:
                yield Event(author=self.name, content=result)

    # ------------------------------------------------------------------
    # Abstract — subclasses implement this
    # ------------------------------------------------------------------

    @abstractmethod
    async def _run_async_impl(
        self, ctx: "InvocationContext"
    ) -> AsyncGenerator[Event, None]:
        """Core agent logic.  Yield :class:`Event` instances."""
        ...
        # Make this an async generator
        if False:  # pragma: no cover
            yield  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Tree navigation helpers
    # ------------------------------------------------------------------

    @property
    def root_agent(self) -> "BaseAgent":
        """Walk up the parent chain to find the root."""
        agent = self
        while agent.parent_agent is not None:
            agent = agent.parent_agent
        return agent

    def find_agent(self, name: str) -> Optional["BaseAgent"]:
        """DFS search for an agent by *name* in the entire tree."""
        return self.root_agent._find_in_subtree(name)

    def find_sub_agent(self, name: str) -> Optional["BaseAgent"]:
        """Search only within direct and indirect sub-agents."""
        for sub in self.sub_agents:
            if sub.name == name:
                return sub
            found = sub.find_sub_agent(name)
            if found:
                return found
        return None

    def _find_in_subtree(self, name: str) -> Optional["BaseAgent"]:
        if self.name == name:
            return self
        for sub in self.sub_agents:
            found = sub._find_in_subtree(name)
            if found:
                return found
        return None
