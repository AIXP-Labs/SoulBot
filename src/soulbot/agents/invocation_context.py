"""InvocationContext — per-invocation state shared across agents."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, Optional

from pydantic import BaseModel, Field

from ..sessions.base_session_service import BaseSessionService
from ..sessions.session import Session
from .base_agent import BaseAgent

if TYPE_CHECKING:
    from ..bus.event_bus import EventBus


class RunConfig(BaseModel):
    """Configuration for a single invocation run."""

    max_llm_calls: int = 50
    streaming: bool = False
    response_modality: str = "text"
    context: dict = Field(default_factory=dict)

    # Timeout settings (seconds). None = no timeout.
    tool_timeout: Optional[float] = None
    cmd_timeout: Optional[float] = None
    llm_timeout: Optional[float] = None

    # Conversation history sliding window.  Only the most recent N events
    # are included in the LLM prompt to prevent "Prompt is too long" errors.
    # Set to 0 or None to disable (include all events — not recommended for
    # long-running sessions).
    max_history_events: Optional[int] = 100

    # Runner entry-point soft limit on user message length (characters).
    # Messages exceeding this are rejected with a suggestion to save as file.
    # None = no limit.
    max_message_length: Optional[int] = None


class InvocationContext(BaseModel):
    """Shared context for one ``Runner.run()`` invocation.

    Holds references to the session, the current agent, service
    dependencies, and runtime counters.
    """

    model_config = {"arbitrary_types_allowed": True}

    invocation_id: str = Field(
        default_factory=lambda: f"e-{uuid.uuid4().hex[:12]}"
    )

    # Core references
    session: Session
    agent: "BaseAgent"

    # Branch isolation (used by ParallelAgent)
    branch: Optional[str] = None

    # Service injection
    session_service: Optional["BaseSessionService"] = Field(
        default=None, exclude=True
    )

    # EventBus (optional, injected by Runner)
    bus: Optional[Any] = Field(default=None, exclude=True)

    # CMD executor (optional, injected by Runner for system tool support — Doc 26)
    cmd_executor: Optional[Any] = Field(default=None, exclude=True)

    # Run configuration
    run_config: RunConfig = Field(default_factory=RunConfig)

    # Runtime state
    end_invocation: bool = False
    llm_call_count: int = 0

    def increment_llm_call_count(self) -> None:
        """Increment and guard against runaway loops."""
        self.llm_call_count += 1
        if self.llm_call_count > self.run_config.max_llm_calls:
            raise RuntimeError(
                f"Exceeded max LLM calls ({self.run_config.max_llm_calls}). "
                "Possible infinite loop."
            )
