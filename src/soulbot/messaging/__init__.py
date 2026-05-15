"""Messaging — async agent-to-agent message dispatch (Doc 08)."""

from .message_entry import (
    ALL_ERROR_CODES,
    ERR_DEPTH_EXCEEDED,
    ERR_LOOP_DETECTED,
    ERR_PAYLOAD_TOO_LARGE,
    ERR_RATE_LIMITED,
    ERR_RECEIVER_UNKNOWN,
    ERR_SELF_LOOP,
    ERR_SERVICE_CLOSED,
    REPLY_MODE_CALLBACK,
    REPLY_MODE_NONE,
    STATUS_CANCELLED,
    STATUS_DELIVERED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_PROCESSING,
    TERMINAL_STATUSES,
    AgentMessageEntry,
)
from .message_service import AgentMessageService
from .sqlite_store import SqliteMessageStore

__all__ = [
    "AgentMessageEntry",
    "AgentMessageService",
    "SqliteMessageStore",
    # error codes
    "ALL_ERROR_CODES",
    "ERR_DEPTH_EXCEEDED",
    "ERR_LOOP_DETECTED",
    "ERR_PAYLOAD_TOO_LARGE",
    "ERR_RATE_LIMITED",
    "ERR_RECEIVER_UNKNOWN",
    "ERR_SELF_LOOP",
    "ERR_SERVICE_CLOSED",
    # reply modes
    "REPLY_MODE_CALLBACK",
    "REPLY_MODE_NONE",
    # statuses
    "STATUS_CANCELLED",
    "STATUS_DELIVERED",
    "STATUS_FAILED",
    "STATUS_PENDING",
    "STATUS_PROCESSING",
    "TERMINAL_STATUSES",
]
