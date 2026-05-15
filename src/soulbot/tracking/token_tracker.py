"""Token usage tracking with per-model cost estimation."""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Built-in defaults — USD per 1 000 tokens
_DEFAULT_PRICING: dict[str, dict[str, float]] = {
    "claude-3-opus": {"prompt": 0.015, "completion": 0.075},
    "claude-3-sonnet": {"prompt": 0.003, "completion": 0.015},
    "claude-3-haiku": {"prompt": 0.00025, "completion": 0.00125},
    "claude-3.5-sonnet": {"prompt": 0.003, "completion": 0.015},
    "claude-4-sonnet": {"prompt": 0.003, "completion": 0.015},
    "gemini-pro": {"prompt": 0.00025, "completion": 0.0005},
    "gemini-1.5-pro": {"prompt": 0.00125, "completion": 0.005},
    "gemini-2.5-flash": {"prompt": 0.00015, "completion": 0.0006},
}


def _load_pricing() -> dict[str, dict[str, float]]:
    """Load pricing from ``~/.soulbot/pricing.json``, falling back to defaults.

    The external file is merged on top of the defaults so users only need
    to specify overrides or additions.
    """
    config_path = Path.home() / ".soulbot" / "pricing.json"
    if not config_path.exists():
        return dict(_DEFAULT_PRICING)
    try:
        user_pricing = json.loads(config_path.read_text(encoding="utf-8"))
        merged = dict(_DEFAULT_PRICING)
        merged.update(user_pricing)
        logger.info("Loaded pricing overrides from %s", config_path)
        return merged
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load %s: %s — using defaults", config_path, exc)
        return dict(_DEFAULT_PRICING)


MODEL_PRICING: dict[str, dict[str, float]] = _load_pricing()


@dataclass
class TokenStats:
    """Aggregated token usage statistics."""

    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_cost_usd: float = 0.0
    request_count: int = 0
    by_model: dict[str, dict[str, Any]] = field(default_factory=dict)
    start_time: float = field(default_factory=time.time)

    @property
    def total_tokens(self) -> int:
        return self.total_prompt_tokens + self.total_completion_tokens


class TokenTracker:
    """Track token usage across requests and estimate costs.

    Usage::

        tracker = TokenTracker()
        tracker.record("claude-3-sonnet", prompt_tokens=100, completion_tokens=50)
        print(tracker.get_stats())
    """

    def __init__(self) -> None:
        self._stats = TokenStats()
        self._lock = threading.Lock()

    def record(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        """Record a single request's token usage (thread-safe)."""
        cost = self._estimate_cost(model, prompt_tokens, completion_tokens)
        with self._lock:
            self._stats.total_prompt_tokens += prompt_tokens
            self._stats.total_completion_tokens += completion_tokens
            self._stats.request_count += 1
            self._stats.total_cost_usd += cost

            # Per-model aggregation
            if model not in self._stats.by_model:
                self._stats.by_model[model] = {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "cost_usd": 0.0,
                    "count": 0,
                }
            m = self._stats.by_model[model]
            m["prompt_tokens"] += prompt_tokens
            m["completion_tokens"] += completion_tokens
            m["cost_usd"] += cost
            m["count"] += 1

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Rough token estimate via word splitting (suitable for ACP mode)."""
        return len(text.split())

    def get_stats(self) -> dict[str, Any]:
        """Return a snapshot of current statistics (thread-safe)."""
        with self._lock:
            return {
                "total_tokens": self._stats.total_tokens,
                "total_prompt_tokens": self._stats.total_prompt_tokens,
                "total_completion_tokens": self._stats.total_completion_tokens,
                "total_cost_usd": round(self._stats.total_cost_usd, 6),
                "request_count": self._stats.request_count,
                "by_model": dict(self._stats.by_model),
                "uptime_seconds": round(time.time() - self._stats.start_time, 1),
            }

    def reset(self) -> None:
        """Reset all statistics (thread-safe)."""
        with self._lock:
            self._stats = TokenStats()

    @staticmethod
    def _estimate_cost(
        model: str, prompt: int, completion: int
    ) -> float:
        """Estimate cost using longest-matching key in MODEL_PRICING."""
        model_lower = model.lower()
        best_key: str | None = None
        best_len = 0
        for key in MODEL_PRICING:
            if key in model_lower and len(key) > best_len:
                best_key = key
                best_len = len(key)
        if not best_key:
            return 0.0
        price = MODEL_PRICING[best_key]
        return (prompt * price["prompt"] + completion * price["completion"]) / 1000


# Global singleton
token_tracker = TokenTracker()
