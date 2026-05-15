"""Tests for AgentMessageEntry dataclass + error code constants (Doc 08)."""

from soulbot.messaging.message_entry import (
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


class TestErrorCodes:
    def test_all_codes_listed(self):
        # ALL_ERROR_CODES must exactly match the 7 declared constants
        assert set(ALL_ERROR_CODES) == {
            ERR_SELF_LOOP, ERR_DEPTH_EXCEEDED, ERR_LOOP_DETECTED,
            ERR_RATE_LIMITED, ERR_RECEIVER_UNKNOWN, ERR_PAYLOAD_TOO_LARGE,
            ERR_SERVICE_CLOSED,
        }
        assert len(ALL_ERROR_CODES) == 7

    def test_codes_are_unique_strings(self):
        # Every code is a non-empty string and they are all distinct
        for c in ALL_ERROR_CODES:
            assert isinstance(c, str) and c
        assert len(set(ALL_ERROR_CODES)) == len(ALL_ERROR_CODES)


class TestStatusConstants:
    def test_terminal_set(self):
        assert TERMINAL_STATUSES == frozenset({
            STATUS_DELIVERED, STATUS_FAILED, STATUS_CANCELLED
        })

    def test_pending_processing_not_terminal(self):
        assert STATUS_PENDING not in TERMINAL_STATUSES
        assert STATUS_PROCESSING not in TERMINAL_STATUSES


class TestReplyModes:
    def test_modes_distinct(self):
        assert REPLY_MODE_NONE != REPLY_MODE_CALLBACK


class TestAgentMessageEntry:
    def test_minimal_construction(self):
        e = AgentMessageEntry(id="m1", from_agent="a", to_agent="b")
        assert e.id == "m1"
        assert e.status == STATUS_PENDING
        assert e.reply_mode == REPLY_MODE_NONE
        assert e.depth == 0
        assert e.parent_id is None
        assert e.aisop == []
        assert e.delivered_at is None
        assert e.result is None
        assert e.error is None

    def test_full_construction(self):
        e = AgentMessageEntry(
            id="m2", from_agent="a", to_agent="b",
            aisop=[{"role": "system"}],
            status=STATUS_DELIVERED,
            reply_mode=REPLY_MODE_CALLBACK,
            parent_id="m1", depth=2,
            created_at="2026-04-13T10:00:00",
            delivered_at="2026-04-13T10:00:05",
            result="done", error=None,
        )
        assert e.parent_id == "m1"
        assert e.depth == 2
        assert e.reply_mode == REPLY_MODE_CALLBACK
        assert e.result == "done"

    def test_aisop_default_is_independent(self):
        # Mutable default safety: each instance must get its own list
        e1 = AgentMessageEntry(id="x1", from_agent="a", to_agent="b")
        e2 = AgentMessageEntry(id="x2", from_agent="a", to_agent="b")
        e1.aisop.append({"role": "system"})
        assert e2.aisop == []
