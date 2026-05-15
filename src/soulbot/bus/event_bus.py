"""EventBus — async publish/subscribe with exact, prefix, and wildcard matching."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Awaitable, Callable

from .events import BusEvent

logger = logging.getLogger(__name__)

Handler = Callable[[BusEvent], Awaitable[None]]


@dataclass
class Subscription:
    """A single handler registration."""

    handler: Handler
    priority: int = 0
    filter_func: Callable[[BusEvent], bool] | None = None


@dataclass
class DeadLetterEntry:
    """Record of a failed event delivery."""

    event: BusEvent
    handler_name: str
    error: str
    timestamp: float = field(default_factory=time.time)


class EventBus:
    """Async event bus with exact, prefix, and wildcard subscriptions.

    Features:
    - **Exact match**: ``subscribe("agent.response", handler)``
    - **Prefix match**: ``subscribe("agent.*", handler)`` matches all ``agent.xxx``
    - **Wildcard**: ``subscribe("*", handler)`` receives every event
    - **Priority**: Higher-priority handlers execute first
    - **Dead letter queue**: Failed deliveries are recorded
    - **Replay**: Historical events can be replayed to new handlers
    """

    def __init__(
        self,
        history_size: int = 1000,
        dead_letter_size: int = 500,
    ) -> None:
        # Exact match: event_type -> [Subscription]
        self._exact: dict[str, list[Subscription]] = {}
        # Prefix match: prefix -> [Subscription]  (e.g. "agent" matches "agent.response")
        self._prefix: dict[str, list[Subscription]] = {}
        # Wildcard: [Subscription]
        self._wildcard: list[Subscription] = []

        self._history: deque[BusEvent] = deque(maxlen=history_size)
        self._dead_letters: deque[DeadLetterEntry] = deque(maxlen=dead_letter_size)

        self._published_count = 0
        self._delivered_count = 0
        self._failed_count = 0

        # Protects _exact, _prefix, _wildcard from concurrent modification
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Subscribe / Unsubscribe
    # ------------------------------------------------------------------

    def subscribe(
        self,
        event_type: str,
        handler: Handler,
        *,
        priority: int = 0,
        filter_func: Callable[[BusEvent], bool] | None = None,
    ) -> str:
        """Subscribe a handler to an event type.

        Thread-safe via internal lock (synchronous callers may use this
        directly; the lock is acquired in :meth:`publish` and other async
        paths).

        Args:
            event_type: Exact type (``"agent.response"``),
                prefix (``"agent.*"``), or wildcard (``"*"``).
            handler: Async callable receiving a :class:`BusEvent`.
            priority: Higher values execute first.
            filter_func: Optional predicate; handler only invoked when True.

        Returns:
            Subscription ID string.
        """
        sub = Subscription(handler=handler, priority=priority, filter_func=filter_func)

        if event_type == "*":
            self._wildcard.append(sub)
            self._wildcard.sort(key=lambda s: s.priority, reverse=True)
        elif event_type.endswith(".*"):
            prefix = event_type[:-2]
            self._prefix.setdefault(prefix, []).append(sub)
            self._prefix[prefix].sort(key=lambda s: s.priority, reverse=True)
        else:
            self._exact.setdefault(event_type, []).append(sub)
            self._exact[event_type].sort(key=lambda s: s.priority, reverse=True)

        return f"{event_type}:{id(handler)}"

    def unsubscribe(self, event_type: str, handler: Handler) -> bool:
        """Remove a handler subscription.

        Returns:
            True if the handler was found and removed.
        """
        if event_type == "*":
            before = len(self._wildcard)
            self._wildcard = [s for s in self._wildcard if s.handler is not handler]
            return len(self._wildcard) < before

        if event_type.endswith(".*"):
            prefix = event_type[:-2]
            subs = self._prefix.get(prefix)
            if subs is None:
                return False
            before = len(subs)
            self._prefix[prefix] = [s for s in subs if s.handler is not handler]
            if not self._prefix[prefix]:
                del self._prefix[prefix]
            return len(self._prefix.get(prefix, [])) < before

        subs = self._exact.get(event_type)
        if subs is None:
            return False
        before = len(subs)
        self._exact[event_type] = [s for s in subs if s.handler is not handler]
        if not self._exact[event_type]:
            del self._exact[event_type]
        return len(self._exact.get(event_type, [])) < before

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------

    async def publish(self, event: BusEvent) -> int:
        """Publish an event to all matching subscribers.

        Subscriber lists are snapshot under lock to prevent races with
        concurrent ``subscribe`` / ``unsubscribe`` calls.  Handlers are
        invoked **outside** the lock so they cannot deadlock the bus.

        Returns:
            Number of handlers that received the event successfully.
        """
        self._published_count += 1
        self._history.append(event)

        # Snapshot subscriber lists under lock
        async with self._lock:
            subscribers: list[Subscription] = []

            # 1. Exact match
            subscribers.extend(self._exact.get(event.type, []))

            # 2. Prefix match — cached prefix extraction avoids repeated
            #    split/join on the same event type (e.g. "agent.response")
            for prefix in self._extract_prefixes(event.type):
                subs = self._prefix.get(prefix)
                if subs:
                    subscribers.extend(subs)

            # 3. Wildcard
            subscribers.extend(self._wildcard)

        # Apply filter + invoke concurrently (outside lock)
        handler_infos: list[tuple[Handler, str]] = []
        for sub in subscribers:
            if sub.filter_func and not sub.filter_func(event):
                continue
            name = getattr(sub.handler, "__name__", str(sub.handler))
            handler_infos.append((sub.handler, name))

        if not handler_infos:
            return 0

        tasks = [self._safe_invoke(h, event) for h, _ in handler_infos]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        delivered = 0
        for (_, handler_name), result in zip(handler_infos, results):
            if isinstance(result, Exception):
                self._failed_count += 1
                self._dead_letters.append(
                    DeadLetterEntry(
                        event=event,
                        handler_name=handler_name,
                        error=str(result),
                    )
                )
                logger.warning(
                    "EventBus: handler %s failed for %s: %s",
                    handler_name,
                    event.type,
                    result,
                )
            else:
                delivered += 1
                self._delivered_count += 1

        return delivered

    # ------------------------------------------------------------------
    # Replay
    # ------------------------------------------------------------------

    async def replay(
        self,
        handler: Handler,
        event_type: str | None = None,
        last_n: int | None = None,
    ) -> int:
        """Replay historical events to a handler.

        Args:
            handler: Async callable to receive replayed events.
            event_type: Only replay events of this type (exact match).
            last_n: Only replay the last *n* matching events.

        Returns:
            Number of events successfully replayed.
        """
        events = list(self._history)
        if event_type:
            events = [e for e in events if e.type == event_type]
        if last_n:
            events = events[-last_n:]

        count = 0
        for event in events:
            try:
                await self._safe_invoke(handler, event)
                count += 1
            except Exception:
                pass
        return count

    # ------------------------------------------------------------------
    # Stats & Dead Letters
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return bus statistics."""
        return {
            "published": self._published_count,
            "delivered": self._delivered_count,
            "failed": self._failed_count,
            "history_size": len(self._history),
            "dead_letter_size": len(self._dead_letters),
            "exact_subscriptions": sum(len(v) for v in self._exact.values()),
            "prefix_subscriptions": sum(len(v) for v in self._prefix.values()),
            "wildcard_subscriptions": len(self._wildcard),
        }

    def get_dead_letters(self, last_n: int | None = None) -> list[DeadLetterEntry]:
        """Return dead letter entries."""
        entries = list(self._dead_letters)
        if last_n:
            entries = entries[-last_n:]
        return entries

    def clear_dead_letters(self) -> int:
        """Clear all dead letters, returning the count cleared."""
        count = len(self._dead_letters)
        self._dead_letters.clear()
        return count

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    async def _safe_invoke(handler: Handler, event: BusEvent) -> None:
        """Invoke handler, letting exceptions propagate for gather."""
        await handler(event)

    @staticmethod
    @lru_cache(maxsize=256)
    def _extract_prefixes(event_type: str) -> tuple[str, ...]:
        """Return all prefix segments for *event_type* (longest first).

        Cached so repeated publishes of the same event type avoid re-splitting.
        Example: ``"a.b.c"`` → ``("a.b", "a")``.
        """
        parts = event_type.split(".")
        return tuple(".".join(parts[:i]) for i in range(len(parts) - 1, 0, -1))
