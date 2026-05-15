"""test_data_erasure.py — GDPR data erasure tests"""

from __future__ import annotations

from unittest.mock import patch


class TestDataErasure:
    def test_erase_empty_db(self, tmp_path):
        from data_erasure import erase_agent_data
        # DB does not exist
        with patch("data_erasure._DB_PATH", tmp_path / "nonexistent.db"):
            result = erase_agent_data("alice@ex.com")
            assert result["status"] == "ok"
            assert result["erased"]["trust_records"] == 0

    def test_dry_run(self, mock_config, tmp_path):
        from trust_check import set_trust
        from data_erasure import erase_agent_data

        db_path = tmp_path / "aibp.db"
        with patch("trust_check._DATA_DIR", tmp_path), patch("trust_check._DB_PATH", db_path):
            set_trust("alice@ex.com", "T2", mock_config)

        with patch("data_erasure._DB_PATH", db_path):
            result = erase_agent_data("alice@ex.com", dry_run=True)
            assert result["dry_run"] is True
            assert result["would_erase"]["trust_records"] == 1

        # Confirm data still exists
        from trust_check import get_trust
        with patch("trust_check._DATA_DIR", tmp_path), patch("trust_check._DB_PATH", db_path):
            check = get_trust("alice@ex.com")
            assert check["exists"] is True

    def test_erase_trust(self, mock_config, tmp_path):
        from trust_check import set_trust, get_trust
        from data_erasure import erase_agent_data

        db_path = tmp_path / "aibp.db"
        with patch("trust_check._DATA_DIR", tmp_path), patch("trust_check._DB_PATH", db_path):
            set_trust("alice@ex.com", "T2", mock_config)
            set_trust("bob@ex.com", "T1", mock_config)

        with patch("data_erasure._DB_PATH", db_path):
            result = erase_agent_data("alice@ex.com")
            assert result["erased"]["trust_records"] == 1

        # alice deleted, bob still exists
        with patch("trust_check._DATA_DIR", tmp_path), patch("trust_check._DB_PATH", db_path):
            assert get_trust("alice@ex.com")["exists"] is False
            assert get_trust("bob@ex.com")["exists"] is True

    def test_erase_threads(self, tmp_path):
        from thread_manager import create_thread
        from data_erasure import erase_agent_data

        db_path = tmp_path / "aibp.db"
        with patch("thread_manager._DATA_DIR", tmp_path), patch("thread_manager._DB_PATH", db_path):
            create_thread("alice@ex.com", "Thread 1")
            create_thread("alice@ex.com", "Thread 2")
            create_thread("bob@ex.com", "Other")

        with patch("data_erasure._DB_PATH", db_path):
            result = erase_agent_data("alice@ex.com")
            assert result["erased"]["thread_records"] == 2

        from thread_manager import list_threads
        with patch("thread_manager._DATA_DIR", tmp_path), patch("thread_manager._DB_PATH", db_path):
            assert list_threads("alice@ex.com")["total"] == 0
            assert list_threads("bob@ex.com")["total"] == 1
