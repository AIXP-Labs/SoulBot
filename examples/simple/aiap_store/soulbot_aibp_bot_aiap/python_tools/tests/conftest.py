"""Shared fixtures — in-memory SQLite / mock config / temp directory"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Ensure python_tools/ is in the import path
_TOOLS_DIR = Path(__file__).resolve().parent.parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))


@pytest.fixture
def mock_config():
    """Preset AibpConfig (no .env reading, pure in-memory)"""
    from _config import AibpConfig

    return AibpConfig(
        aibp_email_address="aibot-test@gmail.com",
        aibp_auth_method="password",
        aibp_email_password="test-app-password",
        aibp_bot_name="TestBot",
        aibp_operator="TestOrg",
        aibp_operator_contact="https://example.com",
        aibp_rate_limit_hour=20,
        aibp_rate_limit_day=100,
        aibp_data_retention_days=365,
    )


@pytest.fixture
def memory_db():
    """In-memory SQLite connection (auto-closed after test)"""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS processed_emails (
            uid TEXT,
            message_id TEXT UNIQUE,
            from_address TEXT,
            processed_at TEXT,
            result TEXT,
            response_message_id TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS processing_queue (
            uid TEXT PRIMARY KEY,
            message_id TEXT,
            from_address TEXT,
            started_at REAL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS send_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient TEXT NOT NULL DEFAULT '',
            sent_at REAL NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_send_log_at ON send_log(sent_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_send_log_rcpt ON send_log(recipient, sent_at)")
    conn.commit()
    yield conn
    conn.close()
