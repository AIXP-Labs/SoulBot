"""test_email_auth.py — Gmail OAuth2 auth unit tests (mock Google API, no network)"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

import pytest


class TestTokenManagement:
    """Token load/save/refresh"""

    def test_load_token_returns_none_when_no_file(self, mock_config, tmp_path):
        from email_auth import _load_token
        mock_config.aibp_oauth2_token = "nonexistent.json"
        with patch("email_auth._TOOLS_DIR", tmp_path):
            assert _load_token(mock_config) is None

    def test_save_and_load_roundtrip(self, mock_config, tmp_path):
        from email_auth import _save_token, _token_path

        mock_creds = MagicMock()
        mock_creds.to_json.return_value = '{"token": "fake", "refresh_token": "fake_refresh"}'

        with patch("email_auth._TOOLS_DIR", tmp_path):
            _save_token(mock_config, mock_creds)
            assert (tmp_path / "token.json").exists()
            content = json.loads((tmp_path / "token.json").read_text())
            assert content["token"] == "fake"

    def test_refresh_if_needed_skips_valid_token(self, mock_config):
        from email_auth import _refresh_if_needed

        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_creds.expired = False
        mock_creds.expiry = datetime.now(timezone.utc) + timedelta(hours=1)

        result = _refresh_if_needed(mock_config, mock_creds)
        assert result is mock_creds
        mock_creds.refresh.assert_not_called()

    def test_refresh_if_needed_refreshes_expired(self, mock_config, tmp_path):
        from email_auth import _refresh_if_needed

        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "fake_refresh"
        mock_creds.to_json.return_value = '{"refreshed": true}'

        with patch("email_auth._TOOLS_DIR", tmp_path):
            result = _refresh_if_needed(mock_config, mock_creds)
            mock_creds.refresh.assert_called_once()


class TestGetGmailService:
    """get_gmail_service integration logic"""

    def test_raises_when_no_token(self, mock_config, tmp_path):
        from email_auth import get_gmail_service
        mock_config.aibp_oauth2_token = "nonexistent.json"
        with patch("email_auth._TOOLS_DIR", tmp_path):
            with pytest.raises(RuntimeError, match="AUTH_OAUTH_EXPIRED"):
                get_gmail_service(mock_config)

    def test_builds_service_with_valid_token(self, mock_config, tmp_path):
        from email_auth import get_gmail_service

        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_creds.expired = False
        mock_creds.expiry = datetime.now(timezone.utc) + timedelta(hours=1)

        with patch("email_auth._load_token", return_value=mock_creds):
            with patch("googleapiclient.discovery.build") as mock_build:
                mock_build.return_value = MagicMock()
                service = get_gmail_service(mock_config)
                mock_build.assert_called_once_with(
                    "gmail", "v1", credentials=mock_creds, cache_discovery=False
                )


class TestInitAuth:
    """--init first-time authorization"""

    def test_missing_credentials_file(self, mock_config, tmp_path):
        from email_auth import init_auth
        mock_config.aibp_oauth2_credentials = "missing.json"
        with patch("email_auth._TOOLS_DIR", tmp_path):
            result = init_auth(mock_config)
            assert result["status"] == "error"
            assert result["error_code"] == "CONFIG_MISSING"

    def test_successful_init(self, mock_config, tmp_path):
        from email_auth import init_auth

        # Create fake credentials.json
        creds_file = tmp_path / "credentials.json"
        creds_file.write_text('{"installed": {}}')

        mock_creds = MagicMock()
        mock_creds.expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        mock_creds.to_json.return_value = '{"token": "new"}'

        mock_flow = MagicMock()
        mock_flow.run_local_server.return_value = mock_creds

        with patch("email_auth._TOOLS_DIR", tmp_path):
            with patch("google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file", return_value=mock_flow):
                result = init_auth(mock_config)

        assert result["status"] == "ok"
        assert result["status"] == "ok"


class TestCheckStatus:
    """--status token status check"""

    def test_no_token(self, mock_config, tmp_path):
        from email_auth import check_status
        mock_config.aibp_oauth2_token = "nonexistent.json"
        with patch("email_auth._TOOLS_DIR", tmp_path):
            result = check_status(mock_config)
            assert result["status"] == "error"

    def test_valid_token(self, mock_config):
        from email_auth import check_status

        mock_creds = MagicMock()
        mock_creds.expired = False
        mock_creds.expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        mock_creds.scopes = [
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/gmail.readonly",
        ]

        with patch("email_auth._load_token", return_value=mock_creds):
            result = check_status(mock_config)
            assert result["status"] == "ok"
            assert result["state"] == "valid"
            assert result["remaining_seconds"] > 0


    def test_expired_refreshable_token(self, mock_config):
        from email_auth import check_status

        mock_creds = MagicMock()
        mock_creds.expired = True
        mock_creds.refresh_token = "fake_refresh"
        mock_creds.expiry = datetime.now(timezone.utc) - timedelta(minutes=5)
        mock_creds.scopes = None

        with patch("email_auth._load_token", return_value=mock_creds):
            result = check_status(mock_config)
            assert result["status"] == "ok"
            assert result["state"] == "expired_refreshable"

    def test_scope_insufficient(self, mock_config):
        from email_auth import check_status

        mock_creds = MagicMock()
        mock_creds.expired = False
        mock_creds.expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        mock_creds.scopes = ["https://www.googleapis.com/auth/gmail.readonly"]  # missing gmail.send

        with patch("email_auth._load_token", return_value=mock_creds):
            result = check_status(mock_config)
            assert result["status"] == "error"
            assert "scope" in result["error"].lower()

    def test_corrupted_token_file(self, mock_config, tmp_path):
        from email_auth import _load_token

        token_file = tmp_path / "token.json"
        token_file.write_text("NOT VALID JSON {{{")

        mock_config.aibp_oauth2_token = "token.json"
        with patch("email_auth._TOOLS_DIR", tmp_path):
            result = _load_token(mock_config)
            assert result is None  # Corrupted file returns None without crash


class TestRevokeAuth:
    """--revoke token revocation"""

    def test_revoke_deletes_file(self, mock_config, tmp_path):
        from email_auth import revoke_auth

        token_file = tmp_path / "token.json"
        token_file.write_text('{"token": "old"}')

        mock_creds = MagicMock()
        mock_creds.token = "old_token"

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("email_auth._TOOLS_DIR", tmp_path):
            with patch("email_auth._load_token", return_value=mock_creds):
                with patch("urllib.request.urlopen", return_value=mock_resp):
                    result = revoke_auth(mock_config)

        assert result["status"] == "ok"
        assert result["revoked"] is True
        assert result["file_deleted"] is True
        assert not token_file.exists()
