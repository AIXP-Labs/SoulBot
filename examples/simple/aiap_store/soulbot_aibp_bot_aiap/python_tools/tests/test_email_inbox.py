"""test_email_inbox.py — Inbox logic unit tests (mock imap-tools, no network)"""

from __future__ import annotations

import time


class TestIdempotency:
    """Message-ID idempotent deduplication"""

    def test_is_processed_returns_false_for_new(self, memory_db):
        from email_inbox import _is_processed
        assert _is_processed(memory_db, "<new@example.com>") is False

    def test_is_processed_returns_true_after_mark(self, memory_db):
        from email_inbox import _mark_processed, _is_processed
        _mark_processed(memory_db, "uid1", "<msg1@ex.com>", "alice@ex.com")
        assert _is_processed(memory_db, "<msg1@ex.com>") is True

    def test_duplicate_mark_is_ignored(self, memory_db):
        from email_inbox import _mark_processed, _is_processed
        _mark_processed(memory_db, "uid1", "<msg1@ex.com>", "alice@ex.com")
        _mark_processed(memory_db, "uid1", "<msg1@ex.com>", "alice@ex.com")  # INSERT OR IGNORE
        assert _is_processed(memory_db, "<msg1@ex.com>") is True


class TestProcessingQueue:
    """Processing lock (prevent duplicate processing)"""

    def test_add_and_check(self, memory_db):
        from email_inbox import _add_to_processing, _is_in_processing
        _add_to_processing(memory_db, "uid1", "<msg1@ex.com>", "alice@ex.com")
        assert _is_in_processing(memory_db, "uid1") is True

    def test_not_in_processing_by_default(self, memory_db):
        from email_inbox import _is_in_processing
        assert _is_in_processing(memory_db, "uid999") is False

    def test_timeout_releases_lock(self, memory_db):
        from email_inbox import _add_to_processing, _is_in_processing, _PROCESSING_TIMEOUT
        # Insert an expired record
        memory_db.execute(
            "INSERT INTO processing_queue (uid, message_id, from_address, started_at) VALUES (?, ?, ?, ?)",
            ("uid_old", "<old@ex.com>", "bob@ex.com", time.time() - _PROCESSING_TIMEOUT - 1),
        )
        memory_db.commit()
        # Should auto-release after timeout
        assert _is_in_processing(memory_db, "uid_old") is False

    def test_mark_processed_removes_from_queue(self, memory_db):
        from email_inbox import _add_to_processing, _mark_processed, _is_in_processing
        _add_to_processing(memory_db, "uid1", "<msg1@ex.com>", "alice@ex.com")
        assert _is_in_processing(memory_db, "uid1") is True
        _mark_processed(memory_db, "uid1", "<msg1@ex.com>", "alice@ex.com")
        assert _is_in_processing(memory_db, "uid1") is False


class TestBounceDetection:
    """Bounce detection"""

    def test_mailer_daemon_is_bounce(self):
        from email_inbox import _detect_bounce
        from unittest.mock import MagicMock

        msg = MagicMock()
        msg.from_ = "MAILER-DAEMON@gmail.com"
        msg.subject = "Delivery Status Notification"
        msg.content_type = "multipart/report"
        msg.text = "550 5.1.1 User unknown"

        bounce = _detect_bounce(msg)
        assert bounce is not None
        assert bounce.type == "hard"

    def test_normal_email_not_bounce(self):
        from email_inbox import _detect_bounce
        from unittest.mock import MagicMock

        msg = MagicMock()
        msg.from_ = "aibot-alice@gmail.com"
        msg.subject = "[AIBP/CHAT] Hello"
        msg.content_type = "text/plain"
        msg.text = "Hello world"

        assert _detect_bounce(msg) is None

    def test_soft_bounce(self):
        from email_inbox import _detect_bounce
        from unittest.mock import MagicMock

        msg = MagicMock()
        msg.from_ = "postmaster@example.com"
        msg.subject = "Undeliverable"
        msg.content_type = "text/plain"
        msg.text = "Mailbox full, try again later"

        bounce = _detect_bounce(msg)
        assert bounce is not None
        assert bounce.type == "soft"

    def test_chinese_bounce_keyword(self):
        from email_inbox import _detect_bounce
        from unittest.mock import MagicMock

        msg = MagicMock()
        msg.from_ = "system@qq.com"
        msg.subject = "\u9000\u4fe1\u901a\u77e5"  # Chinese bounce keyword (must stay Chinese for test)
        msg.content_type = "text/plain"
        msg.text = "\u6536\u4ef6\u4eba\u5730\u5740\u4e0d\u5b58\u5728"  # Chinese: recipient does not exist

        bounce = _detect_bounce(msg)
        assert bounce is not None


class TestBackupDatabase:
    """SQLite backup tests"""

    def test_backup_no_db(self, tmp_path):
        from email_inbox import backup_database
        from unittest.mock import patch
        with patch("email_inbox._DB_PATH", tmp_path / "nonexistent.db"):
            result = backup_database()
            assert result["status"] == "ok"
            assert result["backed_up"] is False

    def test_backup_creates_bak_file(self, tmp_path):
        from email_inbox import backup_database
        from unittest.mock import patch
        import sqlite3

        db_path = tmp_path / "aibp.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE test (id INTEGER)")
        conn.execute("INSERT INTO test VALUES (1)")
        conn.commit()
        conn.close()

        with patch("email_inbox._DB_PATH", db_path), \
             patch("email_inbox._DATA_DIR", tmp_path):
            result = backup_database()
            assert result["status"] == "ok"
            assert result["backed_up"] is True
            assert (tmp_path / "aibp.db.bak").exists()
            assert result["size_kb"] > 0


class TestGracefulShutdown:
    """Graceful shutdown signal handling"""

    def test_is_shutting_down_default_false(self):
        from _config import is_shutting_down, _shutdown_event
        _shutdown_event.clear()  # reset
        assert is_shutting_down() is False

    def test_shutdown_event_set(self):
        from _config import is_shutting_down, _shutdown_event
        _shutdown_event.set()
        assert is_shutting_down() is True
        _shutdown_event.clear()  # cleanup
