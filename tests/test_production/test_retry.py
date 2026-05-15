"""Tests for retry_async — retryable detection, exponential backoff, max retries."""

import asyncio
import time

import pytest

from soulacp.retry import is_retryable, retry_async


class TestIsRetryable:
    def test_timeout_retryable(self):
        assert is_retryable(Exception("Connection timeout")) is True

    def test_connection_refused(self):
        assert is_retryable(Exception("Connection refused")) is True

    def test_rate_limit(self):
        assert is_retryable(Exception("429 rate_limit exceeded")) is True

    def test_503_retryable(self):
        assert is_retryable(Exception("503 Service Unavailable")) is True

    def test_502_retryable(self):
        assert is_retryable(Exception("502 Bad Gateway")) is True

    def test_overloaded(self):
        assert is_retryable(Exception("Server overloaded")) is True

    def test_not_retryable(self):
        assert is_retryable(Exception("Invalid argument")) is False

    def test_case_insensitive(self):
        assert is_retryable(Exception("CONNECTION TIMEOUT")) is True

    def test_reset_retryable(self):
        assert is_retryable(Exception("Connection reset by peer")) is True


class TestRetryAsync:
    async def test_success_no_retry(self):
        call_count = 0

        async def succeed():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = await retry_async(succeed, max_retries=3)
        assert result == "ok"
        assert call_count == 1

    async def test_retry_then_succeed(self):
        call_count = 0

        async def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Connection timeout")
            return "recovered"

        result = await retry_async(
            fail_then_succeed, max_retries=3, base_delay=0.01
        )
        assert result == "recovered"
        assert call_count == 3

    async def test_max_retries_exhausted(self):
        async def always_fail():
            raise Exception("Connection timeout forever")

        with pytest.raises(Exception, match="timeout"):
            await retry_async(always_fail, max_retries=2, base_delay=0.01)

    async def test_non_retryable_raises_immediately(self):
        call_count = 0

        async def bad_arg():
            nonlocal call_count
            call_count += 1
            raise ValueError("Invalid input")

        with pytest.raises(ValueError, match="Invalid input"):
            await retry_async(bad_arg, max_retries=3, base_delay=0.01)
        assert call_count == 1

    async def test_exponential_backoff_timing(self):
        call_count = 0

        async def fail_twice():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise Exception("Connection refused")
            return "ok"

        start = time.time()
        await retry_async(
            fail_twice, max_retries=3, base_delay=0.1, max_delay=1.0
        )
        elapsed = time.time() - start
        # With full jitter, delays are randomized in [0, max_backoff].
        # 1st retry: uniform(0, 0.1), 2nd retry: uniform(0, 0.2)
        # Total is non-deterministic, just verify it completed with retries.
        assert call_count == 3
        assert elapsed < 1.0

    async def test_max_delay_cap(self):
        call_count = 0

        async def fail_many():
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                raise Exception("timeout")
            return "ok"

        start = time.time()
        await retry_async(
            fail_many, max_retries=4, base_delay=0.1, max_delay=0.15
        )
        elapsed = time.time() - start
        # With full jitter, each delay is uniform(0, min(backoff, 0.15))
        # Total is bounded by 3 * 0.15 = 0.45s max
        assert elapsed < 1.0
        assert call_count == 4

    async def test_passes_args_and_kwargs(self):
        async def add(a, b, extra=0):
            return a + b + extra

        result = await retry_async(add, 3, 4, extra=10, max_retries=1)
        assert result == 17
