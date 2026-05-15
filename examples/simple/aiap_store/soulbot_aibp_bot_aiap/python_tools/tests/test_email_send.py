"""test_email_send.py — Email send unit tests (mock smtplib, no network)"""

from __future__ import annotations

import json
import time
from unittest.mock import patch, MagicMock

import pytest


class TestBuildMessage:
    """Email construction tests"""

    def test_basic_headers(self, mock_config):
        from email_send import _build_message
        msg = _build_message(mock_config, "bob@example.com", "Test", "Hello")

        assert msg["To"] == "bob@example.com"
        assert "TestBot" in msg["From"]
        assert msg["Subject"] == "Test"
        assert msg["Message-ID"] is not None
        assert "@gmail.com>" in msg["Message-ID"]  # Uses sender domain

    def test_aibp_headers(self, mock_config):
        from email_send import _build_message
        msg = _build_message(mock_config, "bob@example.com", "Test", "Hello")

        assert msg["X-AIBP-Version"] == "AIBP V1.0.0"
        assert msg["X-AIBP-AI-Generated"] == "true"
        assert msg["X-AIBP-Bot-Name"] == "TestBot"
        assert msg["X-AIBP-Operator"] == "TestOrg"

    def test_reply_threading_headers(self, mock_config):
        from email_send import _build_message
        msg = _build_message(
            mock_config, "bob@example.com", "Re: Hello", "Reply",
            in_reply_to="<orig@example.com>",
            references="<prev@example.com> <orig@example.com>",
        )

        assert msg["In-Reply-To"] == "<orig@example.com>"
        assert "<prev@example.com>" in msg["References"]
        assert "<orig@example.com>" in msg["References"]

    def test_no_reply_headers_when_not_reply(self, mock_config):
        from email_send import _build_message
        msg = _build_message(mock_config, "bob@example.com", "New", "Hi")

        assert msg["In-Reply-To"] is None
        assert msg["References"] is None

    def test_body_passed_as_is(self, mock_config):
        """email_send _build_message (traditional mode) passes body as-is, no auto-append"""
        from email_send import _build_message
        msg = _build_message(mock_config, "bob@example.com", "Test", "Hello world")
        body = msg.get_content().strip()
        assert body == "Hello world"

    def test_axiom0_header_present(self, mock_config):
        from email_send import _build_message
        msg = _build_message(mock_config, "bob@example.com", "Test", "Hello")
        assert msg["X-AIBP-Axiom-0"] == "Human Sovereignty and Wellbeing"

    def test_subject_sanitized(self, mock_config):
        from email_send import _build_message
        msg = _build_message(mock_config, "bob@example.com", "Test\r\nInjected: evil", "Hello")
        assert "\r" not in msg["Subject"]
        assert "\n" not in msg["Subject"]


class TestRateLimit:
    """Rate limit tests (SQLite persistent)"""

    def test_check_passes_when_under_limit(self, mock_config, memory_db, tmp_path):
        from email_send import _check_rate_limit, _DATA_DIR
        with patch("email_send._DATA_DIR", tmp_path):
            with patch("email_send.sqlite3.connect") as mock_conn:
                mock_conn.return_value = memory_db
                _check_rate_limit(mock_config)  # Should not raise

    def test_record_send_inserts_row(self, tmp_path):
        from email_send import _record_send
        # Use real temp dir (_record_send connects + closes itself)
        with patch("email_send._DATA_DIR", tmp_path):
            _record_send()
        # Verify record was written
        import sqlite3
        conn = sqlite3.connect(str(tmp_path / "aibp.db"))
        count = conn.execute("SELECT COUNT(*) FROM send_log").fetchone()[0]
        conn.close()
        assert count == 1
