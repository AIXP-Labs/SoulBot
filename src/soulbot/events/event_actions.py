"""EventActions — side effects and control signals attached to an Event."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EventActions(BaseModel):
    """Side effects and control signals carried by an Event.

    These fields are processed by the Runner / SessionService after an event
    is yielded by an agent.
    """

    state_delta: dict[str, object] = Field(default_factory=dict)
    """Session state changes produced during this step."""

    artifact_delta: dict[str, int] = Field(default_factory=dict)
    """Artifact version changes (artifact_name -> version)."""

    transfer_to_agent: str | None = None
    """If set, the Runner should hand control to the named agent."""

    escalate: bool | None = None
    """If True, signals LoopAgent to exit the loop."""

    skip_summarization: bool | None = None
    """If True, tool result is used as the final response without LLM summarization."""
