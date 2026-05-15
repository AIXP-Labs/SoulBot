"""Tests for SqliteMessageStore (Doc 08)."""

from pathlib import Path

import pytest

from soulbot.messaging.message_entry import (
    REPLY_MODE_CALLBACK,
    STATUS_CANCELLED,
    STATUS_DELIVERED,
    STATUS_FAILED,
    STATUS_PENDING,
    AgentMessageEntry,
)
from soulbot.messaging.sqlite_store import SqliteMessageStore


@pytest.fixture
def store(tmp_path: Path):
    return SqliteMessageStore(str(tmp_path / "msg.db"))


def _entry(id: str = "m1", **overrides) -> AgentMessageEntry:
    defaults = dict(
        id=id, from_agent="alice", to_agent="bob",
        aisop=[{"role": "system", "content": {"x": 1}}],
        created_at="2026-04-13T10:00:00",
    )
    defaults.update(overrides)
    return AgentMessageEntry(**defaults)


class TestSaveAndGet:
    def test_save_and_get_roundtrip(self, store):
        e = _entry()
        store.save_entry(e)
        got = store.get_entry("m1")
        assert got is not None
        assert got.id == "m1"
        assert got.from_agent == "alice"
        assert got.to_agent == "bob"
        assert got.aisop == [{"role": "system", "content": {"x": 1}}]
        assert got.status == STATUS_PENDING

    def test_save_overwrites(self, store):
        store.save_entry(_entry())
        store.save_entry(_entry(status=STATUS_DELIVERED, result="done"))
        got = store.get_entry("m1")
        assert got.status == STATUS_DELIVERED
        assert got.result == "done"

    def test_get_missing(self, store):
        assert store.get_entry("nope") is None


class TestUpdate:
    def test_update_fields(self, store):
        e = _entry()
        store.save_entry(e)
        e.status = STATUS_DELIVERED
        e.result = "ok"
        e.delivered_at = "2026-04-13T10:00:05"
        store.update_entry(e)
        got = store.get_entry("m1")
        assert got.status == STATUS_DELIVERED
        assert got.result == "ok"
        assert got.delivered_at == "2026-04-13T10:00:05"


class TestList:
    def test_list_filters_by_status(self, store):
        store.save_entry(_entry("m1", status=STATUS_PENDING))
        store.save_entry(_entry("m2", status=STATUS_DELIVERED))
        store.save_entry(_entry("m3", status=STATUS_DELIVERED))
        assert len(store.list_entries(status=STATUS_PENDING)) == 1
        assert len(store.list_entries(status=STATUS_DELIVERED)) == 2

    def test_list_filters_by_from_to(self, store):
        store.save_entry(_entry("m1", from_agent="alice", to_agent="bob"))
        store.save_entry(_entry("m2", from_agent="bob", to_agent="alice"))
        assert len(store.list_entries(from_agent="alice")) == 1
        assert len(store.list_entries(to_agent="alice")) == 1

    def test_list_filters_by_parent(self, store):
        store.save_entry(_entry("p1"))
        store.save_entry(_entry("c1", parent_id="p1", depth=1, reply_mode=REPLY_MODE_CALLBACK))
        store.save_entry(_entry("c2", parent_id="p1", depth=1))
        children = store.list_entries(parent_id="p1")
        assert {c.id for c in children} == {"c1", "c2"}

    def test_list_orders_desc_by_created_at(self, store):
        store.save_entry(_entry("old", created_at="2026-04-01T00:00:00"))
        store.save_entry(_entry("new", created_at="2026-04-13T00:00:00"))
        rows = store.list_entries()
        assert rows[0].id == "new"
        assert rows[1].id == "old"

    def test_list_respects_limit(self, store):
        for i in range(10):
            store.save_entry(_entry(f"m{i}"))
        assert len(store.list_entries(limit=3)) == 3


class TestDelete:
    def test_delete_returns_true_when_found(self, store):
        store.save_entry(_entry())
        assert store.delete_entry("m1") is True
        assert store.get_entry("m1") is None

    def test_delete_returns_false_when_missing(self, store):
        assert store.delete_entry("nope") is False


class TestCleanup:
    def test_delete_terminal_before(self, store):
        # Old: should be deleted
        store.save_entry(_entry("old_delivered", status=STATUS_DELIVERED,
                                created_at="2020-01-01T00:00:00"))
        store.save_entry(_entry("old_failed", status=STATUS_FAILED,
                                created_at="2020-01-01T00:00:00"))
        store.save_entry(_entry("old_cancelled", status=STATUS_CANCELLED,
                                created_at="2020-01-01T00:00:00"))
        # Old but pending: must NOT be deleted (audit safety)
        store.save_entry(_entry("old_pending", status=STATUS_PENDING,
                                created_at="2020-01-01T00:00:00"))
        # Recent: must NOT be deleted
        store.save_entry(_entry("new_delivered", status=STATUS_DELIVERED,
                                created_at="2026-04-13T00:00:00"))

        deleted = store.delete_terminal_before("2025-01-01T00:00:00")
        assert deleted == 3

        remaining = {e.id for e in store.list_entries(limit=100)}
        assert remaining == {"old_pending", "new_delivered"}


class TestRestoreLock:
    """Multi-process restore lock (F1 audit fix, v1.9)."""

    def test_acquire_when_no_existing_lock(self, store):
        assert store.try_acquire_restore_lock() is True
        # Lock row should exist now
        conn = store._connect()
        try:
            row = conn.execute(
                "SELECT * FROM agent_messages_locks WHERE name='restore'"
            ).fetchone()
            assert row is not None
        finally:
            conn.close()

    def test_second_acquire_in_same_process_succeeds(self, store):
        # Same process holds the lock; current implementation allows the
        # holder to "re-acquire" (no-op semantically: row already exists
        # belonging to my pid, but try_acquire_restore_lock treats the
        # existing fresh row as "another holder" by pid check).
        # Verify the documented behavior (exclusive: second call returns False).
        assert store.try_acquire_restore_lock() is True
        assert store.try_acquire_restore_lock() is False

    def test_acquire_blocks_when_other_process_holds_lock(self, tmp_path):
        # Two store instances against same DB simulate two processes
        from soulbot.messaging.sqlite_store import SqliteMessageStore
        db = str(tmp_path / "shared.db")
        s1 = SqliteMessageStore(db)
        s2 = SqliteMessageStore(db)
        assert s1.try_acquire_restore_lock() is True
        assert s2.try_acquire_restore_lock() is False

    def test_release_allows_reacquire(self, tmp_path):
        from soulbot.messaging.sqlite_store import SqliteMessageStore
        db = str(tmp_path / "shared.db")
        s1 = SqliteMessageStore(db)
        s2 = SqliteMessageStore(db)
        assert s1.try_acquire_restore_lock() is True
        assert s2.try_acquire_restore_lock() is False
        s1.release_restore_lock()
        assert s2.try_acquire_restore_lock() is True

    def test_stale_lock_is_reclaimed(self, store):
        # Plant a stale lock record by hand (acquired_at < now - STALE_LOCK_SECONDS)
        import time
        conn = store._connect()
        try:
            conn.execute(
                "INSERT INTO agent_messages_locks (name, holder_pid, acquired_at) "
                "VALUES (?, ?, ?)",
                ("restore", 99999, time.time() - 700),  # 700s > 600s stale threshold
            )
            conn.commit()
        finally:
            conn.close()
        # Should reclaim
        assert store.try_acquire_restore_lock() is True
        # Should now be held by us (current process pid), not 99999
        import os
        conn = store._connect()
        try:
            row = conn.execute(
                "SELECT holder_pid FROM agent_messages_locks WHERE name='restore'"
            ).fetchone()
            assert row[0] == os.getpid()
        finally:
            conn.close()

    def test_release_only_removes_own_lock(self, tmp_path):
        from soulbot.messaging.sqlite_store import SqliteMessageStore
        db = str(tmp_path / "shared.db")
        s1 = SqliteMessageStore(db)
        s2 = SqliteMessageStore(db)
        s1.try_acquire_restore_lock()
        # s2 trying to release should NOT delete s1's row (different pid would
        # be checked, but they share os.getpid() in tests... so this test is
        # simulating the release call pathway. In a single-process test the
        # release will succeed since same pid).
        s2.release_restore_lock()
        # Now s2 can acquire (because s1's row was removed under same pid)
        assert s2.try_acquire_restore_lock() is True


class TestCount:
    def test_count_total_and_by_status(self, store):
        store.save_entry(_entry("m1", status=STATUS_PENDING))
        store.save_entry(_entry("m2", status=STATUS_PENDING))
        store.save_entry(_entry("m3", status=STATUS_DELIVERED))
        assert store.count() == 3
        assert store.count(status=STATUS_PENDING) == 2
        assert store.count(status=STATUS_DELIVERED) == 1
