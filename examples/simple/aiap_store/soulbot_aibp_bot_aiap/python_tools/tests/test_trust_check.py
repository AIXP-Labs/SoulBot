"""test_trust_check.py — Trust level management tests (in-memory SQLite)"""

from __future__ import annotations

from unittest.mock import patch
import pytest


class TestTrustCheck:
    def test_unknown_agent_is_t0(self, tmp_path):
        from trust_check import check_trust
        with patch("trust_check._DATA_DIR", tmp_path), patch("trust_check._DB_PATH", tmp_path / "aibp.db"):
            result = check_trust("unknown@example.com", "T0")
            assert result["status"] == "ok"
            assert result["current_level"] == "T0"
            assert result["allowed"] is True

    def test_unknown_agent_fails_t1(self, tmp_path):
        from trust_check import check_trust
        with patch("trust_check._DATA_DIR", tmp_path), patch("trust_check._DB_PATH", tmp_path / "aibp.db"):
            result = check_trust("unknown@example.com", "T1")
            assert result["allowed"] is False

    def test_set_and_check(self, mock_config, tmp_path):
        from trust_check import set_trust, check_trust
        with patch("trust_check._DATA_DIR", tmp_path), patch("trust_check._DB_PATH", tmp_path / "aibp.db"):
            set_result = set_trust("alice@example.com", "T2", mock_config)
            assert set_result["status"] == "ok"
            assert set_result["level"] == "T2"

            check_result = check_trust("alice@example.com", "T1")
            assert check_result["allowed"] is True
            assert check_result["current_level"] == "T2"

    def test_set_exceeds_max_auto(self, mock_config, tmp_path):
        from trust_check import set_trust
        mock_config.aibp_max_auto_trust = "T2"
        with patch("trust_check._DATA_DIR", tmp_path), patch("trust_check._DB_PATH", tmp_path / "aibp.db"):
            result = set_trust("alice@example.com", "T3", mock_config)
            assert result["status"] == "error"
            assert "exceeds max auto" in result["error"].lower() or "TRUST_EXCEEDS_MAX_AUTO" in str(result)

    def test_get_nonexistent(self, tmp_path):
        from trust_check import get_trust
        with patch("trust_check._DATA_DIR", tmp_path), patch("trust_check._DB_PATH", tmp_path / "aibp.db"):
            result = get_trust("nobody@example.com")
            assert result["exists"] is False

    def test_get_existing(self, mock_config, tmp_path):
        from trust_check import set_trust, get_trust
        with patch("trust_check._DATA_DIR", tmp_path), patch("trust_check._DB_PATH", tmp_path / "aibp.db"):
            set_trust("bob@example.com", "T1", mock_config)
            result = get_trust("bob@example.com")
            assert result["exists"] is True
            assert result["level"] == "T1"
            assert result["interaction_count"] == 1

    def test_list_agents(self, mock_config, tmp_path):
        from trust_check import set_trust, list_agents
        with patch("trust_check._DATA_DIR", tmp_path), patch("trust_check._DB_PATH", tmp_path / "aibp.db"):
            set_trust("a@ex.com", "T1", mock_config)
            set_trust("b@ex.com", "T2", mock_config)
            result = list_agents()
            assert result["total"] == 2

    def test_record_interaction(self, mock_config, tmp_path):
        from trust_check import set_trust, record_interaction, get_trust
        with patch("trust_check._DATA_DIR", tmp_path), patch("trust_check._DB_PATH", tmp_path / "aibp.db"):
            set_trust("alice@ex.com", "T1", mock_config)
            record_interaction("alice@ex.com")
            result = get_trust("alice@ex.com")
            assert result["interaction_count"] == 2

    def test_block_agent(self, mock_config, tmp_path):
        from trust_check import set_trust, block_agent, get_trust
        with patch("trust_check._DATA_DIR", tmp_path), patch("trust_check._DB_PATH", tmp_path / "aibp.db"):
            set_trust("alice@ex.com", "T2", mock_config)
            result = block_agent("alice@ex.com")
            assert result["status"] == "ok"
            assert result["level"] == "T0"
            assert result["previous_level"] == "T2"
            # Verify actual data
            check = get_trust("alice@ex.com")
            assert check["level"] == "T0"
            assert "BLOCKED" in check["notes"]

    def test_block_unknown_agent(self, tmp_path):
        from trust_check import block_agent, get_trust
        with patch("trust_check._DATA_DIR", tmp_path), patch("trust_check._DB_PATH", tmp_path / "aibp.db"):
            result = block_agent("unknown@ex.com")
            assert result["status"] == "ok"
            assert result["level"] == "T0"
            # Should create new record
            check = get_trust("unknown@ex.com")
            assert check["exists"] is True

    def test_decay_inactive(self, mock_config, tmp_path):
        """Trust decay: T3 + 100 days inactive → should decay to T2"""
        import sqlite3 as _sqlite3
        from trust_check import decay_inactive, _TRUST_LEVELS
        db_path = tmp_path / "aibp.db"

        # Build table + insert expired record directly (bypass set_trust timestamp issue)
        conn = _sqlite3.connect(str(db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trust (
                agent_address TEXT PRIMARY KEY, level TEXT NOT NULL DEFAULT 'T0',
                first_seen TEXT NOT NULL, last_interaction TEXT NOT NULL,
                interaction_count INTEGER NOT NULL DEFAULT 0,
                consent_status TEXT DEFAULT 'pending', notes TEXT DEFAULT ''
            )
        """)
        conn.execute(
            "INSERT INTO trust (agent_address, level, first_seen, last_interaction, interaction_count) VALUES (?, ?, ?, ?, ?)",
            ("alice@ex.com", "T3", "2025-01-01 00:00:00", "2025-01-01 00:00:00", 5),
        )
        conn.commit()
        conn.close()

        with patch("trust_check._DATA_DIR", tmp_path), patch("trust_check._DB_PATH", db_path):
            result = decay_inactive(days=90)
            assert result["total"] == 1
            assert result["decayed"][0]["from"] == "T3"
            assert result["decayed"][0]["to"] == "T2"

    def test_decay_skips_t1_and_t0(self, mock_config, tmp_path):
        import sqlite3
        from trust_check import set_trust, decay_inactive
        db_path = tmp_path / "aibp.db"
        with patch("trust_check._DATA_DIR", tmp_path), patch("trust_check._DB_PATH", db_path):
            set_trust("a@ex.com", "T1", mock_config)
            set_trust("b@ex.com", "T0", mock_config)
            # Set to 100 days ago
            conn = sqlite3.connect(str(db_path))
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("UPDATE trust SET last_interaction = datetime('now', '-100 days')")
            conn.commit()
            conn.close()

            result = decay_inactive(days=90)
            assert result["total"] == 0  # T0 and T1 do not decay
