"""Event — the basic unit of information flow in agent interactions."""

from __future__ import annotations

import time
import uuid
from typing import Optional

from pydantic import BaseModel, Field

from .event_actions import EventActions


# ---------------------------------------------------------------------------
# Content building blocks
# ---------------------------------------------------------------------------

class FunctionCall(BaseModel):
    """A request from the model to execute a tool."""

    name: str
    args: dict = Field(default_factory=dict)
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class FunctionResponse(BaseModel):
    """The result of a tool execution, sent back to the model."""

    name: str
    response: dict = Field(default_factory=dict)
    id: str = ""


class Part(BaseModel):
    """A single piece of content — text, function call, or function response."""

    text: str | None = None
    function_call: FunctionCall | None = None
    function_response: FunctionResponse | None = None


class Content(BaseModel):
    """A message consisting of one or more parts."""

    role: str = "model"  # "user" or "model"
    parts: list[Part] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Event
# ---------------------------------------------------------------------------

class Event(BaseModel):
    """An immutable record representing a specific point in agent execution.

    Events capture user messages, agent replies, tool calls/results,
    state changes, and control signals.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    """Unique identifier (assigned by SessionService)."""

    author: str = ""
    """'user' or agent name."""

    invocation_id: str = ""
    """Correlates all events within a single user→agent interaction."""

    timestamp: float = Field(default_factory=time.time)
    """Unix timestamp of event creation."""

    branch: str | None = None
    """Hierarchical path for parallel agent isolation (e.g. 'parallel.sub_a')."""

    content: Content | None = None
    """The message payload."""

    partial: bool = False
    """True if this is an intermediate streaming chunk."""

    actions: EventActions = Field(default_factory=EventActions)
    """Side effects: state changes, transfers, escalation."""

    error_code: str | None = None
    error_message: str | None = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get_function_calls(self) -> list[FunctionCall]:
        """Extract all function call parts from this event."""
        if not self.content:
            return []
        return [p.function_call for p in self.content.parts if p.function_call]

    def get_function_responses(self) -> list[FunctionResponse]:
        """Extract all function response parts from this event."""
        if not self.content:
            return []
        return [p.function_response for p in self.content.parts if p.function_response]

    def is_final_response(self) -> bool:
        """Whether this event represents the agent's final answer.

        Returns True when the event contains no pending function calls,
        no function responses, and is not a partial streaming chunk.
        """
        if self.partial:
            return False
        if not self.content or not self.content.parts:
            return False
        if self.get_function_calls():
            return False
        if self.get_function_responses():
            return False
        return True
