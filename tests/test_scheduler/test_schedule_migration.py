"""Tests for JSON-to-SQLite migration (Doc 23)."""

import json
from pathlib import Path

import pytest

from soulbot.scheduler.sqlite_store import SqliteScheduleStore


def _write_json(path: Path, data: list) -> str:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(path)


SAMPLE_ENTRIES = [
    {
        "id": "remind_water",
        "trigger_config": {"type": "once", "delay": 30},
        "aisop": [{"role": "system", "content": {"id": "remind_water"}}],
        "task": {},
        "status": "completed",
        "origin_channel": "telegram",
        "origin_user": "123",
        "from_agent": "agent_a",
        "to_agent": "agent_b",
        "created_at": "2026-02-16T05:00:00",
        "last_run": "2026-02-16T05:00:30",
        "run_count": 1,
        "last_result": "Done!",
        "last_error": None,
    },
    {
        "id": "daily_report",
        "trigger_config": {"type": "cron", "hour": "9", "minute": "0"},
        "aisop": [],
        "task": {"message": "Generate daily report"},
        "status": "active",
        "origin_channel": "web",
        "origin_user": "default",
        "from_agent": "report_agent",
        "to_agent": "report_agent",
        "created_at": "2026-02-15T10:00:00",
        "last_run": None,
        "run_count": 0,
        "last_result": None,
        "last_error": None,
    },
]


class TestMigrateFromJson:
    def test_migrate_entries(self, tmp_path):
        json_path = _write_json(tmp_path / "schedules.json", SAMPLE_ENTRIES)
        db_path = str(tmp_path / "sched.db")
        store = SqliteScheduleStore(db_path, migrate_json=json_path)
        entries = store.list_entries()
        assert len(entries) == 2
        ids = {e.id for e in entries}
        assert ids == {"remind_water", "daily_report"}

    def test_migrate_creates_backup(self, tmp_path):
        json_path = tmp_path / "schedules.json"
        _write_json(json_path, SAMPLE_ENTRIES)
        SqliteScheduleStore(str(tmp_path / "sched.db"), migrate_json=str(json_path))
        assert not json_path.exists()
        assert (tmp_path / "schedules.json.bak").exists()

    def test_migrate_no_json_noop(self, tmp_path):
        db_path = str(tmp_path / "sched.db")
        store = SqliteScheduleStore(db_path, migrate_json=str(tmp_path / "missing.json"))
        assert store.list_entries() == []

    def test_migrate_idempotent(self, tmp_path):
        json_path = _write_json(tmp_path / "schedules.json", SAMPLE_ENTRIES)
        db_path = str(tmp_path / "sched.db")
        store = SqliteScheduleStore(db_path, migrate_json=json_path)
        assert len(store.list_entries()) == 2
        # Second call — JSON is now .bak, no duplicate
        store2 = SqliteScheduleStore(db_path, migrate_json=json_path)
        assert len(store2.list_entries()) == 2

    def test_migrate_preserves_data(self, tmp_path):
        json_path = _write_json(tmp_path / "schedules.json", SAMPLE_ENTRIES)
        db_path = str(tmp_path / "sched.db")
        store = SqliteScheduleStore(db_path, migrate_json=json_path)
        entry = store.get_entry("remind_water")
        assert entry.origin_channel == "telegram"
        assert entry.from_agent == "agent_a"
        assert entry.run_count == 1
        assert entry.last_result == "Done!"
        assert entry.aisop[0]["role"] == "system"

    def test_migrate_backward_compat_agent_name(self, tmp_path):
        """Old entries with agent_name should be migrated to from_agent/to_agent."""
        old_data = [
            {
                "id": "old_entry",
                "trigger_config": {"type": "interval", "minutes": 5},
                "aisop": [],
                "task": {"message": "hi"},
                "status": "active",
                "agent_name": "legacy_agent",
                "origin_channel": "",
                "origin_user": "",
                "created_at": "2026-01-01T00:00:00",
                "last_run": None,
                "run_count": 0,
                "last_result": None,
                "last_error": None,
            }
        ]
        json_path = _write_json(tmp_path / "schedules.json", old_data)
        store = SqliteScheduleStore(str(tmp_path / "sched.db"), migrate_json=json_path)
        entry = store.get_entry("old_entry")
        assert entry.from_agent == "legacy_agent"
        assert entry.to_agent == "legacy_agent"
