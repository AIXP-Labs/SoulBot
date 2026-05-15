"""Session — a single conversation thread with state and event history."""

from __future__ import annotations

import time
import uuid

from pydantic import BaseModel, Field

from ..events.event import Event
from .state import State


class Session(BaseModel):
    """Represents one conversation between a user and an agent.

    Attributes:
        id: Unique session identifier.
        app_name: The CLI name this session belongs to (e.g. ``"claude_cli"``).
        user_id: The user who owns this session.
        agent_name: The entry agent that owns this session (immutable after creation).
        last_agent: Name of the last agent that responded in this session (mutable).
        title: Human-readable session title (auto-generated from first message).
        created_at: Unix timestamp of session creation.
        state: Delta-aware state store for this session.
        events: Ordered log of all events in this session.
        last_update_time: Unix timestamp of last modification.
    """

    model_config = {"arbitrary_types_allowed": True}

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    app_name: str = ""
    user_id: str = ""
    agent_name: str = ""
    last_agent: str = ""
    title: str = ""
    created_at: float = Field(default_factory=time.time)
    state: State = Field(default_factory=State)
    events: list[Event] = Field(default_factory=list)
    last_update_time: float = Field(default_factory=time.time)
