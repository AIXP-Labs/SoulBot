"""Production middleware — rate limiting, API key auth, trace ID."""

from __future__ import annotations

import hmac
import os
import time
import uuid
from collections import defaultdict, deque
from typing import Any


# ======================================================================
# Rate Limiter
# ======================================================================


class RateLimiter:
    """Sliding-window rate limiter keyed by client identifier (e.g. IP).

    Uses :class:`~collections.deque` per client so expired entries are
    drained from the left in O(k) (where *k* = number of expired) instead
    of rebuilding the entire list on every check.

    Args:
        max_requests: Maximum requests allowed per window.
        window_seconds: Window duration in seconds.
    """

    def __init__(
        self, max_requests: int = 60, window_seconds: int = 60
    ) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._store: dict[str, deque[float]] = defaultdict(deque)

    def is_allowed(self, client_id: str) -> bool:
        """Check whether *client_id* may issue another request."""
        now = time.time()
        timestamps = self._store[client_id]
        cutoff = now - self._window
        # Drain expired entries from the left — O(k) amortised
        while timestamps and timestamps[0] < cutoff:
            timestamps.popleft()
        if len(timestamps) >= self._max:
            return False
        timestamps.append(now)
        return True

    @property
    def retry_after(self) -> int:
        """Seconds clients should wait before retrying."""
        return self._window

    def get_remaining(self, client_id: str) -> int:
        """Return the number of requests still allowed for *client_id*."""
        now = time.time()
        timestamps = self._store.get(client_id)
        if not timestamps:
            return self._max
        cutoff = now - self._window
        # Count only non-expired entries
        active = sum(1 for t in timestamps if t >= cutoff)
        return max(0, self._max - active)


# ======================================================================
# API Key Authentication
# ======================================================================


def check_api_key(
    provided_key: str,
    expected_key: str | None = None,
) -> bool:
    """Validate an API key using constant-time comparison.

    If *expected_key* is ``None`` or empty, authentication is disabled
    (always returns ``True``).
    """
    if not expected_key:
        return True  # auth disabled
    return hmac.compare_digest(provided_key.encode(), expected_key.encode())


# ======================================================================
# Trace ID
# ======================================================================


def generate_trace_id(incoming: str | None = None) -> str:
    """Return *incoming* if provided, otherwise generate a new trace ID."""
    if incoming:
        return incoming
    return uuid.uuid4().hex[:8]
