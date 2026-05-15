"""Tests for acp_usage.py — token estimation + provider resolution."""
from __future__ import annotations

from soulbot.observability.acp_usage import (
    CHARS_PER_TOKEN,
    estimate_tokens,
    resolve_gen_ai_provider,
    resolve_provider_from_model,
)


class TestEstimateTokens:
    def test_empty_string(self):
        assert estimate_tokens("") == 0

    def test_none(self):
        assert estimate_tokens(None) == 0

    def test_short_string_minimum_one(self):
        # "hi" = 2 chars; 2//4 = 0; but max(1, ...) promotes to 1
        assert estimate_tokens("hi") == 1

    def test_formula(self):
        # 16 chars / 4 = 4 tokens
        assert estimate_tokens("a" * 16) == 4

    def test_long_string(self):
        # 1000 chars / 4 = 250 tokens
        assert estimate_tokens("x" * 1000) == 250

    def test_chars_per_token_is_4(self):
        assert CHARS_PER_TOKEN == 4


class TestResolveProviderFromModel:
    def test_claude_acp(self):
        assert resolve_provider_from_model("claude-acp/sonnet-4.5") == "claude"

    def test_gemini_acp(self):
        assert resolve_provider_from_model("gemini-acp/pro") == "gemini"

    def test_opencode_acp(self):
        assert resolve_provider_from_model("opencode-acp/default") == "opencode"

    def test_cursor_cli(self):
        assert resolve_provider_from_model("cursor-cli/sonnet") == "cursor"

    def test_openclaw_slash_only(self):
        assert resolve_provider_from_model("openclaw/sonnet") == "openclaw"

    def test_empty_string(self):
        assert resolve_provider_from_model("") == "unknown"

    def test_plain_model_no_separator(self):
        # If no separator, the whole string is treated as provider name
        assert resolve_provider_from_model("some-model") == "some"


class TestResolveGenAiProvider:
    def test_claude_to_anthropic(self):
        assert resolve_gen_ai_provider("claude") == "anthropic"

    def test_gemini_to_google(self):
        assert resolve_gen_ai_provider("gemini") == "google"

    def test_cursor_pass_through(self):
        assert resolve_gen_ai_provider("cursor") == "cursor"

    def test_openclaw_pass_through(self):
        assert resolve_gen_ai_provider("openclaw") == "openclaw"

    def test_unknown_pass_through(self):
        assert resolve_gen_ai_provider("randomxyz") == "randomxyz"
