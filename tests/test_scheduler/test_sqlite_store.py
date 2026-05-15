"""Tests for SqliteScheduleStore (Doc 23)."""

import json
from pathlib import Path

import pytest

from soulbot.scheduler.schedule_service import ScheduleEntry
from soulbot.scheduler.sqlite_store import SqliteScheduleStore


@pytest.fixture
def store(tmp_path: Path):
    return SqliteScheduleStore(str(tmp_path / "sched.db"))


def _make_entry(id: str = "test_1", **overrides) -> ScheduleEntry:
    defaults = dict(
        id=id,
        trigger_config={"type": "once", "delay": 60},
        status="active",
        created_at="2026-02-16T10:00:00",
    )
    defaults.update(overrides)
    return ScheduleEntry(**defaults)


class TestSaveAndGet:
    def test_save_and_get(self, store):
        entry = _make_entry()
        store.save_entry(entry)
        got = store.get_entry("test_1")
        assert got is not None
        assert got.id == "test_1"
        assert got.status == "active"
        assert got.trigger_config == {"type": "once", "delay": 60}

    def test_save_overwrites(self, store):
        entry = _make_entry(status="active")
        store.save_entry(entry)
        entry.status = "completed"
        store.save_entry(entry)
        got = store.get_entry("test_1")
        assert got.status == "completed"

    def test_get_not_found(self, store):
        assert store.get_entry("nonexistent") is None


class TestUpdateEntry:
    def test_update_status(self, store):
        entry = _make_entry()
        store.save_entry(entry)
        entry.status = "paused"
        entry.run_count = 5
        store.update_entry(entry)
        got = store.get_entry("test_1")
        assert got.status == "paused"
        assert got.run_count == 5

    def test_update_last_run(self, store):
        entry = _make_entry()
        store.save_entry(entry)
        entry.last_run = "2026-02-16T12:00:00"
        entry.last_result = "Task done!"
        store.update_entry(entry)
        got = store.get_entry("test_1")
        assert got.last_run == "2026-02-16T12:00:00"
        assert got.last_result == "Task done!"


class TestListEntries:
    def test_list_all(self, store):
        store.save_entry(_make_entry("a"))
        store.save_entry(_make_entry("b"))
        store.save_entry(_make_entry("c"))
        entries = store.list_entries()
        assert len(entries) == 3

    def test_list_filter_status(self, store):
        store.save_entry(_make_entry("a", status="active"))
        store.save_entry(_make_entry("b", status="completed"))
        store.save_entry(_make_entry("c", status="active"))
        active = store.list_entries(status="active")
        assert len(active) == 2
        completed = store.list_entries(status="completed")
        assert len(completed) == 1

    def test_list_empty(self, store):
        assert store.list_entries() == []


class TestDeleteEntry:
    def test_delete(self, store):
        store.save_entry(_make_entry())
        assert store.delete_entry("test_1") is True
        assert store.get_entry("test_1") is None

    def test_delete_not_found(self, store):
        assert store.delete_entry("nonexistent") is False


class TestJsonRoundtrip:
    def test_aisop_roundtrip(self, store):
        aisop = [
            {"role": "system", "content": {"id": "s1", "protocol": "AISOP"}},
            {"role": "user", "content": {"instruction": "do stuff"}},
        ]
        entry = _make_entry(aisop=aisop)
        store.save_entry(entry)
        got = store.get_entry("test_1")
        assert got.aisop == aisop

    def test_task_roundtrip(self, store):
        task = {"id": "t1", "message": "hello", "nested": {"key": [1, 2, 3]}}
        entry = _make_entry(task=task)
        store.save_entry(entry)
        got = store.get_entry("test_1")
        assert got.task == task

    def test_trigger_config_roundtrip(self, store):
        tc = {"type": "cron", "hour": "9", "minute": "0", "day_of_week": "mon-fri"}
        entry = _make_entry(trigger_config=tc)
        store.save_entry(entry)
        got = store.get_entry("test_1")
        assert got.trigger_config == tc


class TestDbCreation:
    def test_db_created_in_directory(self, tmp_path):
        db_path = str(tmp_path / "sub" / "dir" / "sched.db")
        store = SqliteScheduleStore(db_path)
        store.save_entry(_make_entry())
        assert Path(db_path).exists()
