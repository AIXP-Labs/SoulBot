"""test_email_validate.py — Address validation unit tests (mock DNS)"""

from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest


class TestValidateAddress:
    def test_valid_aibp_address(self):
        from email_validate import validate_address

        # mock email-validator returns success
        mock_result = MagicMock()
        mock_result.normalized = "aibot-alice@gmail.com"
        mock_result.mx = [(10, "alt1.gmail-smtp-in.l.google.com")]

        with patch("email_validator.validate_email", return_value=mock_result):
            result = validate_address("aibot-alice@gmail.com")

        assert result["status"] == "ok"
        assert result["valid"] is True
        assert result["is_aibp"] is True
        assert result["suggestion"] is None

    def test_valid_non_aibp_address(self):
        from email_validate import validate_address

        mock_result = MagicMock()
        mock_result.normalized = "alice@gmail.com"
        mock_result.mx = [(10, "mx.google.com")]

        with patch("email_validator.validate_email", return_value=mock_result):
            result = validate_address("alice@gmail.com")

        assert result["valid"] is True
        assert result["is_aibp"] is False
        assert "aibot-" in result["suggestion"]

    def test_invalid_address(self):
        from email_validate import validate_address
        from email_validator import EmailNotValidError

        with patch(
            "email_validator.validate_email",
            side_effect=EmailNotValidError("Invalid email"),
        ):
            result = validate_address("not-an-email")

        assert result["valid"] is False
        assert result["is_aibp"] is False
