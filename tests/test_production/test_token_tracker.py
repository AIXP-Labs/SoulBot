"""Tests for TokenTracker — record, estimate, stats, cost, per-model."""

import pytest

from soulbot.tracking.token_tracker import TokenTracker, MODEL_PRICING


class TestTokenRecord:
    def test_record_single(self):
        tracker = TokenTracker()
        tracker.record("claude-3-sonnet", prompt_tokens=100, completion_tokens=50)
        stats = tracker.get_stats()
        assert stats["total_prompt_tokens"] == 100
        assert stats["total_completion_tokens"] == 50
        assert stats["total_tokens"] == 150
        assert stats["request_count"] == 1

    def test_record_multiple(self):
        tracker = TokenTracker()
        tracker.record("claude-3-sonnet", 100, 50)
        tracker.record("claude-3-sonnet", 200, 100)
        stats = tracker.get_stats()
        assert stats["total_prompt_tokens"] == 300
        assert stats["total_completion_tokens"] == 150
        assert stats["request_count"] == 2

    def test_per_model_stats(self):
        tracker = TokenTracker()
        tracker.record("claude-3-sonnet", 100, 50)
        tracker.record("gemini-pro", 200, 100)
        stats = tracker.get_stats()
        assert "claude-3-sonnet" in stats["by_model"]
        assert "gemini-pro" in stats["by_model"]
        assert stats["by_model"]["claude-3-sonnet"]["count"] == 1
        assert stats["by_model"]["gemini-pro"]["prompt_tokens"] == 200

    def test_reset(self):
        tracker = TokenTracker()
        tracker.record("claude-3-sonnet", 100, 50)
        tracker.reset()
        stats = tracker.get_stats()
        assert stats["total_tokens"] == 0
        assert stats["request_count"] == 0
        assert stats["by_model"] == {}


class TestCostEstimation:
    def test_claude_sonnet_cost(self):
        tracker = TokenTracker()
        tracker.record("claude-3-sonnet", prompt_tokens=1000, completion_tokens=1000)
        stats = tracker.get_stats()
        # prompt: 1000 * 0.003 / 1000 = 0.003
        # completion: 1000 * 0.015 / 1000 = 0.015
        assert stats["total_cost_usd"] == pytest.approx(0.018, abs=0.001)

    def test_unknown_model_zero_cost(self):
        tracker = TokenTracker()
        tracker.record("unknown-model-xyz", 1000, 1000)
        stats = tracker.get_stats()
        assert stats["total_cost_usd"] == 0.0

    def test_longest_match(self):
        tracker = TokenTracker()
        # "claude-3.5-sonnet" should match "claude-3.5-sonnet" not "claude-3-sonnet"
        tracker.record("claude-3.5-sonnet-20241001", 1000, 1000)
        stats = tracker.get_stats()
        # Same pricing as claude-3-sonnet (both 0.003/0.015)
        assert stats["total_cost_usd"] > 0

    def test_gemini_cost(self):
        tracker = TokenTracker()
        tracker.record("gemini-2.5-flash-latest", 10000, 5000)
        stats = tracker.get_stats()
        # prompt: 10000 * 0.00015 / 1000 = 0.0015
        # completion: 5000 * 0.0006 / 1000 = 0.003
        assert stats["total_cost_usd"] == pytest.approx(0.0045, abs=0.001)

    def test_per_model_cost(self):
        tracker = TokenTracker()
        tracker.record("claude-3-haiku", 500, 200)
        stats = tracker.get_stats()
        model_stats = stats["by_model"]["claude-3-haiku"]
        assert model_stats["cost_usd"] > 0


class TestEstimateTokens:
    def test_simple_text(self):
        tracker = TokenTracker()
        count = tracker.estimate_tokens("hello world foo bar")
        assert count == 4

    def test_empty_text(self):
        tracker = TokenTracker()
        assert tracker.estimate_tokens("") == 0

    def test_long_text(self):
        tracker = TokenTracker()
        text = " ".join(["word"] * 100)
        assert tracker.estimate_tokens(text) == 100


class TestUptime:
    def test_uptime_positive(self):
        tracker = TokenTracker()
        stats = tracker.get_stats()
        assert stats["uptime_seconds"] >= 0
