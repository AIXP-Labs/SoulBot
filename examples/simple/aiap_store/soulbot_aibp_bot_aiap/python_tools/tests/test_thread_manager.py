"""test_thread_manager.py — Thread manager tests (in-memory SQLite)"""

from __future__ import annotations

from unittest.mock import patch


class TestThreadManager:
    def test_create_thread(self, tmp_path):
        from thread_manager import create_thread
        with patch("thread_manager._DATA_DIR", tmp_path), patch("thread_manager._DB_PATH", tmp_path / "aibp.db"):
            result = create_thread("alice@ex.com", "Hello", "<msg1@ex.com>")
            assert result["status"] == "ok"
            assert result["thread_id"]
            assert result["message_id_chain"] == ["<msg1@ex.com>"]

    def test_get_thread(self, tmp_path):
        from thread_manager import create_thread, get_thread
        with patch("thread_manager._DATA_DIR", tmp_path), patch("thread_manager._DB_PATH", tmp_path / "aibp.db"):
            created = create_thread("alice@ex.com", "Test")
            tid = created["thread_id"]
            result = get_thread(tid)
            assert result["status"] == "ok"
            assert result["subject"] == "Test"
            assert result["agent"] == "alice@ex.com"

    def test_get_nonexistent(self, tmp_path):
        from thread_manager import get_thread
        with patch("thread_manager._DATA_DIR", tmp_path), patch("thread_manager._DB_PATH", tmp_path / "aibp.db"):
            result = get_thread("nonexistent-id")
            assert result["status"] == "error"

    def test_add_message_builds_chain(self, tmp_path):
        from thread_manager import create_thread, add_message, get_thread
        with patch("thread_manager._DATA_DIR", tmp_path), patch("thread_manager._DB_PATH", tmp_path / "aibp.db"):
            created = create_thread("alice@ex.com", "Chat", "<msg1@ex.com>")
            tid = created["thread_id"]

            add_message(tid, "<msg2@bot.aibp>")
            add_message(tid, "<msg3@ex.com>")

            result = get_thread(tid)
            assert result["message_count"] == 3
            assert result["message_id_chain"] == ["<msg1@ex.com>", "<msg2@bot.aibp>", "<msg3@ex.com>"]
            assert result["in_reply_to"] == "<msg3@ex.com>"
            assert "<msg1@ex.com>" in result["references"]

    def test_add_duplicate_message_ignored(self, tmp_path):
        from thread_manager import create_thread, add_message, get_thread
        with patch("thread_manager._DATA_DIR", tmp_path), patch("thread_manager._DB_PATH", tmp_path / "aibp.db"):
            created = create_thread("alice@ex.com", "Test", "<msg1@ex.com>")
            tid = created["thread_id"]
            add_message(tid, "<msg1@ex.com>")  # duplicate
            result = get_thread(tid)
            assert result["message_count"] == 1  # should not increase

    def test_list_threads(self, tmp_path):
        from thread_manager import create_thread, list_threads
        with patch("thread_manager._DATA_DIR", tmp_path), patch("thread_manager._DB_PATH", tmp_path / "aibp.db"):
            create_thread("alice@ex.com", "Thread 1")
            create_thread("alice@ex.com", "Thread 2")
            create_thread("bob@ex.com", "Other thread")

            result = list_threads("alice@ex.com")
            assert result["total"] == 2

    def test_find_thread_by_message_id(self, tmp_path):
        from thread_manager import create_thread, add_message, find_thread_by_message_id
        with patch("thread_manager._DATA_DIR", tmp_path), patch("thread_manager._DB_PATH", tmp_path / "aibp.db"):
            created = create_thread("alice@ex.com", "Test", "<msg1@ex.com>")
            tid = created["thread_id"]
            add_message(tid, "<msg2@bot.aibp>")

            result = find_thread_by_message_id("<msg2@bot.aibp>")
            assert result["found"] is True
            assert result["thread_id"] == tid

    def test_find_nonexistent_message(self, tmp_path):
        from thread_manager import find_thread_by_message_id
        with patch("thread_manager._DATA_DIR", tmp_path), patch("thread_manager._DB_PATH", tmp_path / "aibp.db"):
            result = find_thread_by_message_id("<nonexistent@ex.com>")
            assert result["found"] is False

    def test_close_thread(self, tmp_path):
        from thread_manager import create_thread, close_thread, get_thread
        with patch("thread_manager._DATA_DIR", tmp_path), patch("thread_manager._DB_PATH", tmp_path / "aibp.db"):
            created = create_thread("alice@ex.com", "Test")
            tid = created["thread_id"]

            result = close_thread(tid)
            assert result["status"] == "ok"
            assert result["thread_status"] == "closed"

            # Verify actual state
            thread = get_thread(tid)
            assert thread["thread_status"] == "closed"

    def test_close_nonexistent_thread(self, tmp_path):
        from thread_manager import close_thread
        with patch("thread_manager._DATA_DIR", tmp_path), patch("thread_manager._DB_PATH", tmp_path / "aibp.db"):
            result = close_thread("nonexistent-id")
            assert result["status"] == "error"
