"""Tests for AgentMessageService._RateLimiter (Doc 08 §4.8)."""

import time

import pytest

from soulbot.messaging.message_service import _RateLimiter


@pytest.fixture
def limiter():
    return _RateLimiter(max_per_second=10)


class TestAllow:
    def test_under_limit_passes(self, limiter):
        for _ in range(10):
            assert limiter.allow("alice") is True

    def test_exceeds_limit_blocks(self, limiter):
        for _ in range(10):
            limiter.allow("alice")
        assert limiter.allow("alice") is False

    def test_per_sender_independent(self, limiter):
        for _ in range(10):
            limiter.allow("alice")
        # alice maxed out, bob should still be fine
        assert limiter.allow("alice") is False
        assert limiter.allow("bob") is True

    def test_window_slides(self, limiter):
        # Saturate alice
        for _ in range(10):
            limiter.allow("alice")
        assert limiter.allow("alice") is False

        # After 1.05s the window has slid; bucket should be empty
        time.sleep(1.05)
        assert limiter.allow("alice") is True


class TestCustomLimit:
    def test_custom_max(self):
        lim = _RateLimiter(max_per_second=3)
        assert lim.allow("a") is True
        assert lim.allow("a") is True
        assert lim.allow("a") is True
        assert lim.allow("a") is False

    def test_zero_max_blocks_all(self):
        lim = _RateLimiter(max_per_second=0)
        assert lim.allow("a") is False
