"""BusEvent model and predefined event type constants."""

import time

from pydantic import BaseModel, Field


class BusEvent(BaseModel):
    """An event transmitted through the EventBus."""

    type: str
    """Event type identifier, e.g. ``"agent.response"``."""

    data: dict = Field(default_factory=dict)
    """Arbitrary payload."""

    timestamp: float = Field(default_factory=time.time)
    """Unix timestamp of event creation."""

    source: str = ""
    """Publisher identifier."""


# ---------------------------------------------------------------------------
# Agent lifecycle
# ---------------------------------------------------------------------------
AGENT_START = "agent.start"
AGENT_RESPONSE = "agent.response"
AGENT_ERROR = "agent.error"
AGENT_TRANSFER = "agent.transfer"

# ---------------------------------------------------------------------------
# LLM calls
# ---------------------------------------------------------------------------
LLM_REQUEST = "llm.request"
LLM_RESPONSE = "llm.response"
LLM_ERROR = "llm.error"
LLM_STREAM_CHUNK = "llm.stream.chunk"

# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------
TOOL_CALL = "tool.call"
TOOL_RESULT = "tool.result"
TOOL_ERROR = "tool.error"

# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------
SESSION_CREATED = "session.created"
SESSION_UPDATED = "session.updated"
SESSION_DELETED = "session.deleted"

# ---------------------------------------------------------------------------
# Cron (Phase 7)
# ---------------------------------------------------------------------------
CRON_JOB_FIRED = "cron.job.fired"
CRON_JOB_COMPLETED = "cron.job.completed"
CRON_JOB_FAILED = "cron.job.failed"

# ---------------------------------------------------------------------------
# Plugin (Phase 4)
# ---------------------------------------------------------------------------
PLUGIN_STARTED = "plugin.started"
PLUGIN_STOPPED = "plugin.stopped"
PLUGIN_ERROR = "plugin.error"

# ---------------------------------------------------------------------------
# Command (Phase 6)
# ---------------------------------------------------------------------------
COMMAND_PARSED = "command.parsed"
COMMAND_EXECUTED = "command.executed"

# ---------------------------------------------------------------------------
# Schedule (Doc 17)
# ---------------------------------------------------------------------------
SCHEDULE_CREATED = "schedule.created"
SCHEDULE_EXECUTED = "schedule.executed"
SCHEDULE_CANCELLED = "schedule.cancelled"
SCHEDULE_FAILED = "schedule.failed"

# ---------------------------------------------------------------------------
# Agent Message (Doc 08)
# ---------------------------------------------------------------------------
AGENT_MESSAGE_SENT = "agent.message.sent"
AGENT_MESSAGE_DELIVERED = "agent.message.delivered"
AGENT_MESSAGE_FAILED = "agent.message.failed"
