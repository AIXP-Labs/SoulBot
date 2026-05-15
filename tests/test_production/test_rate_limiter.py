"""Tests for RateLimiter — allow/deny, window expiry, multi-client isolation."""

import time

import pytest

from soulbot.server.middleware import RateLimiter


class TestRateLimiterBasic:
    def test_allows_within_limit(self):
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        for _ in range(5):
            assert limiter.is_allowed("client1") is True

    def test_blocks_over_limit(self):
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        for _ in range(3):
            limiter.is_allowed("client1")
        assert limiter.is_allowed("client1") is False

    def test_retry_after(self):
        limiter = RateLimiter(max_requests=5, window_seconds=30)
        assert limiter.retry_after == 30

    def test_remaining_count(self):
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        assert limiter.get_remaining("client1") == 5
        limiter.is_allowed("client1")
        limiter.is_allowed("client1")
        assert limiter.get_remaining("client1") == 3


class TestRateLimiterWindow:
    def test_window_expiry(self):
        limiter = RateLimiter(max_requests=2, window_seconds=1)
        limiter.is_allowed("c1")
        limiter.is_allowed("c1")
        assert limiter.is_allowed("c1") is False
        time.sleep(1.1)
        assert limiter.is_allowed("c1") is True


class TestRateLimiterIsolation:
    def test_different_clients_independent(self):
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        limiter.is_allowed("a")
        limiter.is_allowed("a")
        assert limiter.is_allowed("a") is False
        assert limiter.is_allowed("b") is True

    def test_many_clients(self):
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        for i in range(100):
            assert limiter.is_allowed(f"client-{i}") is True
        # First client is now blocked
        assert limiter.is_allowed("client-0") is False
