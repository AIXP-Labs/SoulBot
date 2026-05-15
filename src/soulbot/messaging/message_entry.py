"""AgentMessageEntry dataclass + error code constants (Doc 08).

Separated from message_service.py so that sqlite_store.py can import the
dataclass without pulling in the full service implementation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Error codes (Doc 08 §4.13)
# ---------------------------------------------------------------------------
# Used as the prefix of ValueError messages raised from AgentMessageService.send().
# Format: f"{ERR_CODE}: <details>"
# LLMs match on the prefix to pick a recovery strategy (see message_guide.md).

ERR_SELF_LOOP = "self_loop"
ERR_DEPTH_EXCEEDED = "depth_exceeded"
ERR_LOOP_DETECTED = "loop_detected"
ERR_RATE_LIMITED = "rate_limited"
ERR_RECEIVER_UNKNOWN = "receiver_unknown"
ERR_PAYLOAD_TOO_LARGE = "payload_too_large"
ERR_SERVICE_CLOSED = "service_closed"

ALL_ERROR_CODES = (
    ERR_SELF_LOOP,
    ERR_DEPTH_EXCEEDED,
    ERR_LOOP_DETECTED,
    ERR_RATE_LIMITED,
    ERR_RECEIVER_UNKNOWN,
    ERR_PAYLOAD_TOO_LARGE,
    ERR_SERVICE_CLOSED,
)

# ---------------------------------------------------------------------------
# Status values
# ---------------------------------------------------------------------------
STATUS_PENDING = "pending"        # queued, dispatch task not started yet
STATUS_PROCESSING = "processing"  # dispatch task running
STATUS_DELIVERED = "delivered"    # receiver completed successfully
STATUS_FAILED = "failed"          # receiver raised or framework error
STATUS_CANCELLED = "cancelled"    # cancel() called before/during dispatch

TERMINAL_STATUSES = frozenset({STATUS_DELIVERED, STATUS_FAILED, STATUS_CANCELLED})

# ---------------------------------------------------------------------------
# Reply modes
# ---------------------------------------------------------------------------
REPLY_MODE_NONE = "none"          # fire-and-forget
REPLY_MODE_CALLBACK = "callback"  # receiver completion triggers a callback message


@dataclass
class AgentMessageEntry:
    """A persisted record of an inter-agent message.

    Stored in the agent_messages SQLite table (see sqlite_store.py).
    """

    id: str
    from_agent: str
    to_agent: str
    aisop: list[Any] = field(default_factory=list)
    status: str = STATUS_PENDING
    reply_mode: str = REPLY_MODE_NONE
    parent_id: str | None = None
    depth: int = 0
    created_at: str = ""
    delivered_at: str | None = None
    result: str | None = None
    error: str | None = None
