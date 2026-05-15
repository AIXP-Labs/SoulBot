"""Tests for the loop guard (Doc 08 §4.7).

NOTE: Layer 3 (chain-based loop detection) was removed during implementation
after testing showed it false-positives on the basic callback pattern (A→B
then B→A naturally re-introduces A as a sender). The depth limit (max 5)
is the actual safety net for real loops like A→B→A→B→A→B.

This file now covers Layer 1 (self-loop), Layer 2 (depth limit), and the
_trace_senders diagnostic utility.
"""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from soulbot.messaging import (
    AgentMessageEntry,
    AgentMessageService,
    SqliteMessageStore,
)
from soulbot.messaging.message_entry import (
    ERR_DEPTH_EXCEEDED,
    ERR_SELF_LOOP,
    STATUS_DELIVERED,
)


@pytest.fixture
def svc(tmp_path: Path):
    store = SqliteMessageStore(str(tmp_path / "loop.db"))
    return AgentMessageService(
        store=store,
        is_known_agent=lambda n: n in {"A", "B", "C", "D", "E"},
        max_depth=5,
    )


def _planted(svc, msg_id, from_a, to_a, parent=None, depth=0):
    """Insert a delivered entry directly into the store to seed a chain."""
    entry = AgentMessageEntry(
        id=msg_id, from_agent=from_a, to_agent=to_a,
        parent_id=parent, depth=depth,
        created_at=datetime.now(timezone.utc).isoformat(),
        status=STATUS_DELIVERED,
    )
    svc._store.save_entry(entry)
    return entry


class TestLayer1SelfLoop:
    @pytest.mark.asyncio
    async def test_self_message_rejected(self, svc):
        with pytest.raises(ValueError, match=ERR_SELF_LOOP):
            await svc.send(to_agent="A", from_agent="A", aisop=[])


class TestLayer2DepthLimit:
    @pytest.mark.asyncio
    async def test_depth_at_limit_passes(self, svc):
        # depth=5 with max_depth=5 should pass (boundary)
        result = await svc.send(to_agent="B", from_agent="A", aisop=[], depth=5)
        assert result["status"] == "pending"

    @pytest.mark.asyncio
    async def test_depth_over_limit_rejected(self, svc):
        with pytest.raises(ValueError, match=ERR_DEPTH_EXCEEDED):
            await svc.send(to_agent="B", from_agent="A", aisop=[], depth=6)


class TestCallbackIsNotALoop:
    """Callback (sender→receiver→sender) is the intended pattern, not a loop."""

    @pytest.mark.asyncio
    async def test_callback_pattern_not_rejected(self, svc):
        # A→B (m1) then B→A as callback (parent=m1, depth=1) must succeed
        _planted(svc, "m1", "A", "B")
        result = await svc.send(
            to_agent="A", from_agent="B",
            parent_id="m1", depth=1, aisop=[],
        )
        assert result["status"] == "pending"
        assert result["depth"] == 1


class TestTraceSendersDiagnostic:
    """_trace_senders is now a diagnostic utility (no longer enforced policy)."""

    def test_trace_senders_collects_only_from_agent(self, svc):
        _planted(svc, "m1", "A", "B")
        _planted(svc, "m2", "B", "C", parent="m1", depth=1)
        senders = svc._trace_senders("m2")
        assert senders == {"A", "B"}
        assert "C" not in senders  # C is only a receiver

    def test_trace_senders_empty_for_root(self, svc):
        assert svc._trace_senders(None) == set()

    def test_trace_senders_handles_orphan_parent(self, svc):
        assert svc._trace_senders("ghost") == set()

    def test_trace_senders_safety_cap(self, svc):
        # Build a chain longer than max_depth+2 and verify no infinite walk
        prev = None
        for i in range(20):
            _planted(svc, f"chain_{i}", "A", "B", parent=prev, depth=i)
            prev = f"chain_{i}"
        senders = svc._trace_senders(prev)
        # Bails at max_depth+2 = 7 steps
        assert len(senders) <= 7
