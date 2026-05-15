"""ModelRegistry — regex-based model name → adapter resolution with LRU cache."""

from __future__ import annotations

import re
import threading
from functools import lru_cache
from typing import Type

from .base_llm import BaseLlm


class ModelRegistry:
    """Registry that maps model name patterns to LLM adapter classes.

    Patterns are matched in reverse registration order (last registered wins).
    Resolution results are cached with LRU for performance.

    Thread-safe: a :class:`threading.Lock` protects ``_entries`` mutations
    and ``resolve`` cache invalidation from concurrent access.
    """

    _entries: list[tuple[str, Type[BaseLlm]]] = []
    _lock: threading.Lock = threading.Lock()

    @classmethod
    def register(cls, pattern: str, adapter_class: Type[BaseLlm]) -> None:
        """Register a regex *pattern* → *adapter_class* mapping."""
        with cls._lock:
            cls._entries.append((pattern, adapter_class))
            # Invalidate cache when new entries are added
            cls.resolve.cache_clear()

    @classmethod
    @lru_cache(maxsize=64)
    def resolve(cls, model_name: str) -> BaseLlm:
        """Find and instantiate the adapter for *model_name*.

        Raises:
            ValueError: If no registered pattern matches.
        """
        with cls._lock:
            for pattern, adapter_cls in reversed(cls._entries):
                if re.fullmatch(pattern, model_name):
                    return adapter_cls(model=model_name)
        raise ValueError(
            f"No adapter registered for model '{model_name}'. "
            f"Registered patterns: {[p for p, _ in cls._entries]}"
        )

    @classmethod
    def reset(cls) -> None:
        """Clear all registrations (useful for testing)."""
        with cls._lock:
            cls._entries.clear()
            cls.resolve.cache_clear()
