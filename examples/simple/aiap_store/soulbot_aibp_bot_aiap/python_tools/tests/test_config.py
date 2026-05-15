"""test_config.py — _config.py unit tests"""

from __future__ import annotations

import pytest


class TestAibpConfig:
    """AibpConfig validation tests"""

    def test_default_values(self, mock_config):
        assert mock_config.aibp_auth_method == "password"
        assert mock_config.aibp_watch_mode == "poll"
        assert mock_config.aibp_credential_store == "env"
        assert mock_config.aibp_poll_interval == 30
        assert mock_config.aibp_rate_limit_hour == 20
        assert mock_config.aibp_rate_limit_day == 100
        assert mock_config.aibp_default_trust == "T1"
        assert mock_config.aibp_max_auto_trust == "T2"
        assert mock_config.aibp_ai_disclosure is True
        assert mock_config.aibp_data_retention_days == 365

    def test_invalid_auth_method(self):
        from _config import AibpConfig
        with pytest.raises(ValueError, match="aibp_auth_method"):
            AibpConfig(
                aibp_email_address="test@gmail.com",
                aibp_auth_method="invalid",
            )

    def test_invalid_watch_mode(self):
        from _config import AibpConfig
        with pytest.raises(ValueError, match="aibp_watch_mode"):
            AibpConfig(
                aibp_email_address="test@gmail.com",
                aibp_watch_mode="invalid",
            )

    def test_invalid_credential_store(self):
        from _config import AibpConfig
        with pytest.raises(ValueError, match="aibp_credential_store"):
            AibpConfig(
                aibp_email_address="test@gmail.com",
                aibp_credential_store="invalid",
            )

    def test_password_is_secret_str(self, mock_config):
        # SecretStr does not expose password directly
        assert "test-app-password" not in str(mock_config.aibp_email_password)
        assert mock_config.aibp_email_password.get_secret_value() == "test-app-password"


class TestParseAibpType:
    """parse_aibp_type tests"""

    def test_valid_types(self):
        from _config import parse_aibp_type
        assert parse_aibp_type("[AIBP/INTRODUCE] Hello") == "INTRODUCE"
        assert parse_aibp_type("[AIBP/CHAT] Message") == "CHAT"
        assert parse_aibp_type("[AIBP/WELCOME] Hi") == "WELCOME"
        assert parse_aibp_type("[AIBP/BLOCK] Bye") == "BLOCK"

    def test_case_insensitive(self):
        from _config import parse_aibp_type
        assert parse_aibp_type("[AIBP/chat] msg") == "CHAT"
        assert parse_aibp_type("[AIBP/Chat] msg") == "CHAT"

    def test_invalid_type_returns_none(self):
        from _config import parse_aibp_type
        assert parse_aibp_type("[AIBP/HACKED] evil") is None
        assert parse_aibp_type("[AIBP/UNKNOWN] test") is None

    def test_no_aibp_prefix(self):
        from _config import parse_aibp_type
        assert parse_aibp_type("Hello World") is None
        assert parse_aibp_type("") is None

    def test_malformed_brackets(self):
        from _config import parse_aibp_type
        assert parse_aibp_type("[AIBP/CHAT") is None  # missing ]
        assert parse_aibp_type("AIBP/CHAT]") is None  # missing [


class TestDetectServer:
    """_detect_server tests"""

    def test_manual_config_takes_priority(self, mock_config):
        from _config import detect_imap_server
        mock_config.aibp_imap_host = "manual.example.com"
        mock_config.aibp_imap_port = 1993
        host, port = detect_imap_server(mock_config)
        assert host == "manual.example.com"
        assert port == 1993

    def test_fallback_for_gmail(self, mock_config):
        from _config import detect_imap_server, detect_smtp_server
        mock_config.aibp_imap_host = None
        mock_config.aibp_smtp_host = None
        # Gmail fallback should read from email_config.json
        host, port = detect_imap_server(mock_config)
        assert host == "imap.gmail.com"
        assert port == 993

        host, port = detect_smtp_server(mock_config)
        assert host == "smtp.gmail.com"
        assert port == 465

    def test_unknown_domain_raises(self):
        from _config import AibpConfig, detect_imap_server
        config = AibpConfig(
            aibp_email_address="test@unknowndomain12345.xyz",
        )
        with pytest.raises(RuntimeError, match="Cannot detect"):
            detect_imap_server(config)
