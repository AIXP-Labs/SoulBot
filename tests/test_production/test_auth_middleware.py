"""Tests for API key authentication — valid/invalid/missing key, disabled auth."""

import pytest

from soulbot.server.middleware import check_api_key


class TestCheckApiKey:
    def test_valid_key(self):
        assert check_api_key("my-secret", expected_key="my-secret") is True

    def test_invalid_key(self):
        assert check_api_key("wrong-key", expected_key="my-secret") is False

    def test_empty_provided(self):
        assert check_api_key("", expected_key="my-secret") is False

    def test_auth_disabled_no_key_set(self):
        assert check_api_key("anything", expected_key=None) is True

    def test_auth_disabled_empty_string(self):
        assert check_api_key("anything", expected_key="") is True

    def test_auth_disabled_no_provided_key(self):
        assert check_api_key("", expected_key=None) is True

    def test_exact_match_required(self):
        assert check_api_key("MY-SECRET", expected_key="my-secret") is False

    def test_whitespace_not_trimmed(self):
        assert check_api_key(" key ", expected_key="key") is False
