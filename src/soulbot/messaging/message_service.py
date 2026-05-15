"""AgentMessageService — async agent-to-agent message dispatch (Doc 08).

Mirrors scheduler/schedule_service.py in shape:
  - Persistent SQLite store (sqlite_store.py)
  - Runner invocation via shared runner_factory (cli.py)
  - EventBus publish for sent/delivered/failed (bus/events.py)

Adds (vs schedule):
  - parent_id / depth chain with three-layer loop guard (§4.7)
  - Per-sender rate limiter, default 10 msg/s (§4.8)
  - Tracked background dispatch tasks with cancel + close support (§4.4.1)
  - Persistent callback messages (NOT EventBus subscriptions) (§4.6)
  - 100KB payload size cap (§4.12)
  - 30-day retention via cleanup() (§4.11)
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator, Callable, TypedDict

from .message_entry import (
    ERR_DEPTH_EXCEEDED,
    ERR_LOOP_DETECTED,
    ERR_PAYLOAD_TOO_LARGE,
    ERR_RATE_LIMITED,
    ERR_RECEIVER_UNKNOWN,
    ERR_SELF_LOOP,
    ERR_SERVICE_CLOSED,
    REPLY_MODE_CALLBACK,
    REPLY_MODE_NONE,
    STATUS_CANCELLED,
    STATUS_DELIVERED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_PROCESSING,
    AgentMessageEntry,
)
from .sqlite_store import SqliteMessageStore

logger = logging.getLogger(__name__)


# Type aliases for clarity
RunnerFactory = Callable[[str, str, dict], AsyncIterator[Any]]
KnownAgentCheck = Callable[[str], bool]


# F4 audit fix (v1.9): TypedDict return types for the public service API.
# These are documentation-grade (Python doesn't enforce TypedDict at runtime
# but mypy / pyright do). Keep keys in sync with _entry_to_dict() output.
class SendResult(TypedDict):
    message_id: str
    status: str  # one of STATUS_PENDING (immediately after send)
    depth: int


class CancelResult(TypedDict, total=False):
    entry_id: str
    status: str
    error: str  # only present if entry not found


class ListResult(TypedDict):
    entries: list[dict[str, Any]]
    count: int


class _RateLimiter:
    """Per-sender sliding-window limiter: max N messages per second.

    THREAD-SAFETY CONTRACT (Doc 08 §4.8):
      ``allow()`` is a synchronous function with NO await inside.
      Caller MUST invoke it from the synchronous prelude of send()
      (before any await). Because asyncio is single-threaded and there
      is no yield point in allow(), concurrent send() coroutines cannot
      interleave inside this method.
      DO NOT add await inside allow() — it would break atomicity.

    A1 audit fix (v1.7): bounded by ``max_senders`` with simple LRU
    eviction. Without this, a malicious or buggy LLM could synthesize
    distinct ``from_agent`` strings and grow the bucket dict unbounded.
    Eviction targets the sender whose most-recent timestamp is oldest
    (i.e. least recently active).
    """

    DEFAULT_MAX_SENDERS = 1000

    def __init__(
        self,
        max_per_second: int = 10,
        max_senders: int = DEFAULT_MAX_SENDERS,
    ) -> None:
        self._max = max_per_second
        self._max_senders = max_senders
        self._buckets: dict[str, list[float]] = {}

    def allow(self, sender: str) -> bool:
        now = time.time()
        bucket = self._buckets.get(sender)
        if bucket is None:
            # Cap dict growth: evict LRU sender if at capacity.
            if len(self._buckets) >= self._max_senders:
                # Find the sender whose last activity is oldest.
                lru_sender = min(
                    self._buckets,
                    key=lambda s: self._buckets[s][-1] if self._buckets[s] else 0.0,
                )
                self._buckets.pop(lru_sender, None)
            bucket = []
            self._buckets[sender] = bucket
        # Drop entries older than 1 second (no await; safe under asyncio)
        bucket[:] = [t for t in bucket if now - t < 1.0]
        if len(bucket) >= self._max:
            return False
        bucket.append(now)
        return True


class AgentMessageService:
    """Service for sending async messages between agents in this instance.

    EVENT INTERFACE CONTRACT (E1 audit fix, v1.7):
        ``runner_factory`` is expected to yield event objects with this
        duck-typed shape (matching ``soulbot.events.Event``):
          - ``event.is_final_response()`` → bool, callable
          - ``event.content`` → object with attribute ``parts`` (iterable)
          - each ``part`` has attribute ``text`` (str | None)
        Only events where ``is_final_response()`` returns True contribute
        to ``msg.result``. If the runner module changes this shape, the
        ``_dispatch`` method's text extraction must be updated.

    NAMING CONVENTION (D1 audit fix, v1.7):
        The same concept is referred to by three names depending on layer:
          - Service method args: ``id`` (Pythonic, short)
          - Return values:        ``message_id`` (explicit, unambiguous)
          - HTTP path params:     ``entry_id`` (consistent with /schedule)
        These are SYNONYMS; do not introduce a fourth.

    TASK LIFECYCLE (W5 audit fix, v1.10):
        ``self._tasks: dict[str, asyncio.Task]`` tracks in-flight dispatch
        tasks. Entries are removed by ``add_done_callback`` when each task
        completes. Edge case: if the event loop is forcefully torn down
        (e.g. ``asyncio.run()`` exits with pending tasks), the done_callback
        does not fire and the dict entry is "leaked". This is harmless
        because the task object becomes garbage-collectable along with the
        service instance. To shut down gracefully always call ``await
        service.close()`` first.
    """

    # All byte/count limits (D2 audit fix — single class-attr surface).
    # Each can be overridden via env var (C1.1 audit fix, v1.8) — see __init__.
    MAX_AISOP_BYTES: int = 100 * 1024     # 100 KB max payload per message (§4.12)
    RETENTION_DAYS: int = 30              # cleanup() retention horizon (§4.11)
    RESULT_MAX_CHARS: int = 2000          # truncate result before persisting
    ERROR_MAX_CHARS: int = 1000           # truncate error before persisting
    RESTORE_BATCH_SIZE: int = 100         # max tasks spawned per batch (A2 fix)
    RESTORE_BATCH_DELAY: float = 0.005    # 5ms gap between batches
    RESTORE_LIST_LIMIT: int = 10000       # max entries fetched in one restore
    SAVE_RETRY_ATTEMPTS: int = 3          # SQLite lock retry count (B1 fix)
    SAVE_RETRY_BASE_DELAY: float = 0.05   # base delay before exponential backoff
    DEFAULT_CLOSE_TIMEOUT: float = 5.0    # graceful shutdown wait (B2.1)
    MAX_DEPTH_INT: int = 2 ** 31 - 1      # G1.1: SQLite INTEGER overflow guard

    @classmethod
    def _env_int(cls, name: str, default: int) -> int:
        """Read int env var, fall back to default. C1.1 audit fix."""
        import os
        try:
            return int(os.environ.get(f"SOULBOT_MESSAGE_{name}", default))
        except (TypeError, ValueError):
            return default

    @classmethod
    def _env_float(cls, name: str, default: float) -> float:
        import os
        try:
            return float(os.environ.get(f"SOULBOT_MESSAGE_{name}", default))
        except (TypeError, ValueError):
            return default

    def __init__(
        self,
        bus: Any | None = None,
        runner_factory: RunnerFactory | None = None,
        store: SqliteMessageStore | None = None,
        is_known_agent: KnownAgentCheck | None = None,
        max_depth: int = 5,
        rate_limit_per_second: int = 10,
    ) -> None:
        """Construct an AgentMessageService.

        IMPORTANT: ``runner_factory`` is captured by reference; once stored,
        do NOT swap it out from under a running service or pending dispatch
        tasks may invoke a stale callable. To rotate the factory, construct
        a fresh service after calling close() on the previous one. (Doc 08
        §13.2 / G3 audit fix.)
        """
        self._bus = bus
        self._runner_factory = runner_factory
        self._store = store
        self._is_known_agent = is_known_agent
        self._max_depth = max_depth
        # C1.1 audit fix (v1.8): instance-level overrides from env vars.
        # Class attrs remain as defaults; instance attrs win lookup.
        self.MAX_AISOP_BYTES = self._env_int("MAX_AISOP_BYTES", self.MAX_AISOP_BYTES)
        self.RETENTION_DAYS = self._env_int("RETENTION_DAYS", self.RETENTION_DAYS)
        self.DEFAULT_CLOSE_TIMEOUT = self._env_float(
            "CLOSE_TIMEOUT", self.DEFAULT_CLOSE_TIMEOUT,
        )
        self._rate_limiter = _RateLimiter(rate_limit_per_second)
        self._tasks: dict[str, asyncio.Task] = {}
        self._closed: bool = False
        self._restore_done: bool = False  # B1 audit fix: idempotent restore

    def __repr__(self) -> str:  # F3 audit fix (v1.9)
        return (
            f"AgentMessageService("
            f"store={'yes' if self._store else 'no'}, "
            f"in_flight={len(self._tasks)}, "
            f"closed={self._closed}, "
            f"restore_done={self._restore_done})"
        )

    # ------------------------------------------------------------------
    # Public API — invoked via SOULBOT_CMD service="message"
    # ------------------------------------------------------------------

    async def send(
        self,
        to_agent: str,
        aisop: list,
        from_agent: str = "",
        reply_mode: str = REPLY_MODE_NONE,
        parent_id: str | None = None,
        depth: int | None = None,
        message_id: str | None = None,
        timeout: float | None = None,  # noqa: ARG002 - extracted by CommandExecutor
        **_kwargs: Any,
    ) -> SendResult:
        """Send an async message to another agent.

        Returns immediately with {"message_id", "status": "pending", "depth"}.
        Actual delivery runs as a tracked background task.

        Raises ValueError with one of the codes in message_entry.py:
          self_loop / depth_exceeded / loop_detected / rate_limited /
          receiver_unknown / payload_too_large / service_closed
        """
        # --- Synchronous validation prelude (NO await before _RateLimiter.allow) ---
        if self._closed:
            raise ValueError(f"{ERR_SERVICE_CLOSED}: service is shutting down")

        # F2 audit fix (v1.9): strip whitespace before validation.
        # `from_agent="   "` would otherwise pass the truthiness check below.
        from_agent = (from_agent or "").strip()
        to_agent = (to_agent or "").strip()
        if not from_agent:
            # from_agent should be auto-injected by CommandExecutor; defensive default
            raise ValueError(f"{ERR_RECEIVER_UNKNOWN}: from_agent is empty")
        if not to_agent:
            raise ValueError(f"{ERR_RECEIVER_UNKNOWN}: to_agent is empty")

        if to_agent == from_agent:
            raise ValueError(f"{ERR_SELF_LOOP}: from == to == {from_agent}")

        # depth defaults to 0 for root, parent.depth+1 for callbacks
        effective_depth = depth if depth is not None else 0
        # N1 audit fix: reject negative depth — direct API callers (not LLM)
        # could otherwise inject depth=-1 to bypass the depth limit.
        if effective_depth < 0:
            raise ValueError(
                f"{ERR_DEPTH_EXCEEDED}: depth must be >= 0, got {effective_depth}"
            )
        # G1.1 audit fix (v1.8): SQLite INTEGER is 64-bit signed; reject
        # absurdly large depths well before they reach the DB.
        if effective_depth > self.MAX_DEPTH_INT:
            raise ValueError(
                f"{ERR_DEPTH_EXCEEDED}: depth {effective_depth} exceeds INTEGER limit"
            )
        if effective_depth > self._max_depth:
            raise ValueError(
                f"{ERR_DEPTH_EXCEEDED}: depth {effective_depth} > max {self._max_depth}"
            )

        # N7 audit fix: minimal AISOP structure check.
        # Full schema validation lives in the runner; here we just catch the
        # obvious shape errors so they fail loudly at the dispatch boundary
        # instead of producing confusing runner errors later.
        if not isinstance(aisop, list):
            raise ValueError(
                f"{ERR_PAYLOAD_TOO_LARGE}: aisop must be a list, got {type(aisop).__name__}"
            )
        if aisop and not all(
            isinstance(part, dict) and "role" in part for part in aisop
        ):
            raise ValueError(
                f"{ERR_PAYLOAD_TOO_LARGE}: aisop entries must be dicts with a 'role' field"
            )

        # N3 audit fix: validate parent_id exists if provided.
        # Direct API callers could otherwise create orphan child messages
        # that break chain traversal (_trace_senders / UI parent links).
        if parent_id and self._store and not self._store.get_entry(parent_id):
            raise ValueError(
                f"{ERR_RECEIVER_UNKNOWN}: parent_id '{parent_id}' not found"
            )

        if not self._rate_limiter.allow(from_agent):
            raise ValueError(
                f"{ERR_RATE_LIMITED}: {from_agent} exceeded "
                f"{self._rate_limiter._max}/s"
            )

        # Payload size check
        try:
            payload_size = len(json.dumps(aisop, ensure_ascii=False).encode("utf-8"))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{ERR_PAYLOAD_TOO_LARGE}: aisop not serializable: {exc}")
        if payload_size > self.MAX_AISOP_BYTES:
            raise ValueError(
                f"{ERR_PAYLOAD_TOO_LARGE}: aisop is {payload_size} bytes, "
                f"max {self.MAX_AISOP_BYTES}"
            )

        # Receiver existence
        if self._is_known_agent and not self._is_known_agent(to_agent):
            raise ValueError(f"{ERR_RECEIVER_UNKNOWN}: agent '{to_agent}' not registered")

        # NOTE: Layer 3 (chain-based loop detection) was removed after testing
        # showed it false-positives on the basic callback pattern (A→B then B→A).
        # The depth limit (max 5) is sufficient: any real loop pattern like
        # A→B→A→B→A→B hits depth_exceeded at step 6. Self-loop is still blocked
        # by Layer 1 above. _trace_senders() is kept as a diagnostic utility.

        # --- Construct entry ---
        entry = AgentMessageEntry(
            id=message_id or _generate_msg_id(),
            from_agent=from_agent,
            to_agent=to_agent,
            aisop=aisop,
            status=STATUS_PENDING,
            reply_mode=reply_mode if reply_mode in (REPLY_MODE_NONE, REPLY_MODE_CALLBACK) else REPLY_MODE_NONE,
            parent_id=parent_id,
            depth=effective_depth,
            created_at=_utc_now_iso(),
        )
        # B2 audit fix: persist BEFORE spawning the dispatch task, and
        # fail-fast if the DB write fails. Otherwise a disk-full or lock
        # error would leave a phantom in-memory task with no DB record.
        if self._store:
            await self._safe_save(entry)
        self._emit("agent.message.sent", {
            "message_id": entry.id,
            "from_agent": entry.from_agent,
            "to_agent": entry.to_agent,
            "parent_id": entry.parent_id,
            "depth": entry.depth,
            "reply_mode": entry.reply_mode,
        })

        # --- Spawn tracked background dispatch task ---
        task = asyncio.create_task(self._dispatch(entry))
        self._tasks[entry.id] = task
        task.add_done_callback(lambda _t: self._tasks.pop(entry.id, None))

        return {
            "message_id": entry.id,
            "status": entry.status,
            "depth": entry.depth,
        }

    def list(
        self,
        status: str | None = None,
        from_agent: str | None = None,
        to_agent: str | None = None,
        parent_id: str | None = None,
        limit: int = 100,
        **_kwargs: Any,
    ) -> ListResult:
        """List messages, sorted by created_at DESC. Returns {entries, count}."""
        if not self._store:
            return {"entries": [], "count": 0}
        entries = self._store.list_entries(
            status=status,
            from_agent=from_agent,
            to_agent=to_agent,
            parent_id=parent_id,
            limit=limit,
        )
        return {
            "entries": [_entry_to_dict(e) for e in entries],
            "count": len(entries),
        }

    def get(self, id: str, **_kwargs: Any) -> dict:
        """Get a single message entry as dict."""
        if not self._store:
            return {}
        entry = self._store.get_entry(id)
        if not entry:
            return {}
        return _entry_to_dict(entry)

    async def cancel(self, id: str, **_kwargs: Any) -> CancelResult:
        """Best-effort cancel a pending or in-flight message.

        Behavior (B2 audit fix — deterministic completion):
        - If status is already terminal (delivered/failed/cancelled), returns
          current status (idempotent).
        - If task exists in _tasks (in-flight), task.cancel() is called and
          the call **awaits** the task's CancelledError-handler + finally
          block so the returned status reflects what's actually in the DB.
        - If no in-flight task (e.g. server crashed before dispatch started),
          marks cancelled directly in the store.

        Returns the status from the DB after the operation completes.
        """
        if not self._store:
            return {"entry_id": id, "status": "unknown", "error": "no store"}

        entry = self._store.get_entry(id)
        if not entry:
            return {"entry_id": id, "status": "unknown", "error": "not found"}

        if entry.status in (STATUS_DELIVERED, STATUS_FAILED, STATUS_CANCELLED):
            return {"entry_id": id, "status": entry.status}

        task = self._tasks.get(id)
        if task and not task.done():
            task.cancel()
            # Wait for _dispatch's CancelledError handler + finally block to
            # persist status='cancelled' to the store before we return.
            #
            # R1 audit fix (v1.5.1): only swallow CancelledError. Real
            # exceptions in _dispatch (e.g. bug in _emit) MUST propagate so
            # they get logged/raised rather than silently lost. _dispatch's
            # own try/except/finally handles its known failure modes; any
            # exception escaping that is genuinely unexpected.
            try:
                await task
            except asyncio.CancelledError:
                pass  # expected; _dispatch finally already persisted status
            except Exception as exc:
                logger.error(
                    "Unexpected error from cancelled dispatch %s: %s",
                    id, exc, exc_info=True,
                )
                # do not re-raise — caller asked to cancel, status is in DB
        elif not task:
            # No in-flight task; mark cancelled directly
            entry.status = STATUS_CANCELLED
            entry.delivered_at = _utc_now_iso()
            self._store.update_entry(entry)

        # Re-read from store to return the actual final status
        final = self._store.get_entry(id)
        return {
            "entry_id": id,
            "status": final.status if final else STATUS_CANCELLED,
        }

    async def restore(self) -> int:
        """Re-spawn dispatch tasks for status='pending' entries on restart.

        status='processing' entries are treated as crashed and marked failed.
        Returns count of entries re-spawned.

        IDEMPOTENT (B1 audit fix): If called twice (e.g. FastAPI startup hook
        firing more than once during dev hot-reload), the second call is a
        no-op. To force re-restore (e.g. after manual DB edits), reset
        ``_restore_done = False`` first.

        MULTI-PROCESS LOCK (B1.1 audit fix, v1.8): uses an advisory SQLite
        lock row so only one process actually runs the respawn even when
        the service is started under multiple uvicorn workers. Other
        processes return 0 immediately. Stale locks (>10 min) are reclaimed.

        ASYNC (R1.1 audit fix, v1.8): now async because _safe_update awaits
        on retry backoff. Callers must use ``await message_service.restore()``.
        """
        if not self._store:
            return 0
        if self._restore_done:
            logger.debug("restore() already ran; skipping (idempotent guard)")
            return 0

        # C audit fix (v1.9): only mark _restore_done AFTER lock acquired.
        # Previously the flag was set before the lock check, which meant a
        # process that lost the lock race would mark itself "done" and never
        # retry — even after reset_restore_guard() and after the lock holder
        # released. Keeping the order "acquire then mark" lets non-winning
        # processes retry on the next call.
        if not self._store.try_acquire_restore_lock():
            logger.info(
                "restore(): another process holds the restore lock; skipping"
            )
            return 0
        self._restore_done = True

        # Mark crashed processing entries as failed
        crashed = self._store.list_entries(
            status=STATUS_PROCESSING, limit=self.RESTORE_LIST_LIMIT,
        )
        for entry in crashed:
            entry.status = STATUS_FAILED
            entry.error = "shutdown_or_crash"
            entry.delivered_at = _utc_now_iso()
            await self._safe_update(entry)
        if crashed:
            logger.warning(
                "Marked %d processing message(s) as failed (crash recovery)",
                len(crashed),
            )

        # Re-spawn pending entries
        pending = self._store.list_entries(
            status=STATUS_PENDING, limit=self.RESTORE_LIST_LIMIT,
        )
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning("restore() called outside event loop; skipping respawn")
            return 0

        # A2 audit fix: spawn in batches with a tiny yield between them so
        # we don't flood the event loop with thousands of simultaneous
        # create_task() calls. The yield (asyncio.sleep) lets other tasks
        # (e.g. server startup, runner init) make progress.
        if pending and len(pending) > self.RESTORE_BATCH_SIZE:
            logger.info(
                "Restoring %d pending message(s) in batches of %d",
                len(pending), self.RESTORE_BATCH_SIZE,
            )
            loop.create_task(self._spawn_restore_batches(pending))
        else:
            for entry in pending:
                self._spawn_dispatch(entry)
            if pending:
                logger.info("Restored %d pending message dispatch(es)", len(pending))
        return len(pending)

    async def _spawn_restore_batches(
        self, pending: list[AgentMessageEntry],
    ) -> None:
        """Spawn restore tasks in size-bounded batches with yields between."""
        for start in range(0, len(pending), self.RESTORE_BATCH_SIZE):
            for entry in pending[start:start + self.RESTORE_BATCH_SIZE]:
                self._spawn_dispatch(entry)
            await asyncio.sleep(self.RESTORE_BATCH_DELAY)
        logger.info("Finished restoring %d pending message(s)", len(pending))

    def _spawn_dispatch(self, entry: AgentMessageEntry) -> None:
        """Create + track a dispatch task for a single entry.

        A2.1 audit fix (v1.8): use ``get_running_loop()`` rather than the
        deprecated ``get_event_loop()`` (deprecated in Python 3.12+).
        """
        loop = asyncio.get_running_loop()
        task = loop.create_task(self._dispatch(entry))
        self._tasks[entry.id] = task
        task.add_done_callback(
            lambda _t, eid=entry.id: self._tasks.pop(eid, None)
        )

    def reset_restore_guard(self) -> None:
        """Allow restore() to run again on the next call.

        N2 audit fix (v1.5.1): operations / tests sometimes need to force a
        re-restore after manual DB edits or resetting test state. Without this
        the only way was to construct a new service instance.
        """
        self._restore_done = False

    def cleanup(self) -> int:
        """Delete terminal-status messages older than RETENTION_DAYS days.

        Pending / processing entries are NEVER deleted (audit safety).
        Returns count deleted. Intended to be invoked by cron daily.

        B audit fix (v1.9): synchronous because it has no awaits inside.
        Cron framework accepts both sync and async callables. If you need
        to invoke this from an async context, no `await` is needed.
        """
        if not self._store:
            return 0
        cutoff_dt = datetime.now(timezone.utc) - timedelta(days=self.RETENTION_DAYS)
        cutoff_iso = cutoff_dt.isoformat()
        deleted = self._store.delete_terminal_before(cutoff_iso)
        if deleted:
            logger.info(
                "Cleaned up %d agent_message entries older than %s",
                deleted, cutoff_iso,
            )
        return deleted

    async def close(self, timeout: float = 5.0) -> None:
        """Graceful shutdown: block new send(), await/cancel in-flight tasks.

        A audit fix (v1.9): release the multi-process restore lock so a
        subsequent restart in the same process (or another worker) can
        reclaim it immediately rather than waiting for the 10-min stale
        timer. Best-effort — failure to release is logged but not raised
        because the stale-lock reclaim path will recover anyway.
        """
        self._closed = True
        if self._tasks:
            tasks = list(self._tasks.values())
            try:
                await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                for t in tasks:
                    if not t.done():
                        t.cancel()
                # let CancelledError handlers in _dispatch run
                await asyncio.gather(*tasks, return_exceptions=True)
                logger.warning("close(): %d task(s) cancelled after %ss timeout",
                               sum(1 for t in tasks if t.cancelled()), timeout)
        # Release multi-process restore lock if we hold it
        if self._store and self._restore_done:
            try:
                self._store.release_restore_lock()
            except Exception as exc:
                logger.warning("Failed to release restore lock during close: %s", exc)

    # ------------------------------------------------------------------
    # Internal — dispatch + callback
    # ------------------------------------------------------------------

    async def _dispatch(self, entry: AgentMessageEntry) -> None:
        """Background task: feed AISOP to runner_factory, persist result, fire event.

        See class docstring "EVENT INTERFACE CONTRACT" for the expected
        shape of the events that ``runner_factory`` yields.
        """
        # Mark processing
        entry.status = STATUS_PROCESSING
        if self._store:
            await self._safe_update(entry)

        result_text = ""
        try:
            if not self._runner_factory:
                raise RuntimeError("no runner_factory configured")

            message = json.dumps(entry.aisop, ensure_ascii=False)
            context = {
                "type": "message",
                "entry_id": entry.id,
                "from_agent": entry.from_agent,
                "to_agent": entry.to_agent,
                "origin_channel": "internal",
                "origin_user": "",
                "parent_id": entry.parent_id,
                "depth": entry.depth,
                "reply_mode": entry.reply_mode,
            }

            # A3 audit fix: stream-truncate during accumulation rather than
            # joining a possibly-huge buffer first. We only need the first
            # RESULT_MAX_CHARS chars; once we have them, ignore the tail.
            saw_final_response = False
            async for event in self._runner_factory(entry.to_agent, message, context):
                if not (
                    hasattr(event, "is_final_response")
                    and event.is_final_response()
                    and getattr(event, "content", None)
                ):
                    continue
                saw_final_response = True
                if len(result_text) >= self.RESULT_MAX_CHARS:
                    continue  # already at cap; skip further accumulation
                parts = getattr(event.content, "parts", []) or []
                for p in parts:
                    txt = getattr(p, "text", None)
                    if not txt:
                        continue
                    if result_text:
                        result_text += " "
                    remaining = self.RESULT_MAX_CHARS - len(result_text)
                    result_text += txt[:remaining]
                    if len(result_text) >= self.RESULT_MAX_CHARS:
                        break

            # B3 audit fix: empty result + no final response = receiver was
            # silent (e.g. unknown agent → runner_factory yielded nothing).
            # That is a delivery failure, not a successful empty delivery.
            if not saw_final_response and not result_text:
                raise RuntimeError(
                    f"no response from receiver '{entry.to_agent}' "
                    "(agent may be unregistered or runner produced no events)"
                )

            entry.status = STATUS_DELIVERED
            entry.result = result_text or None
            entry.error = None

        except asyncio.CancelledError:
            entry.status = STATUS_CANCELLED
            entry.error = "cancelled"
            logger.info("Message %s dispatch cancelled", entry.id)
            raise  # propagate so the task is marked cancelled at the asyncio level

        except Exception as exc:
            entry.status = STATUS_FAILED
            entry.error = str(exc)[:self.ERROR_MAX_CHARS]
            logger.error("Message %s dispatch failed: %s", entry.id, exc)

        finally:
            entry.delivered_at = _utc_now_iso()
            if self._store:
                await self._safe_update(entry)

            event_type = (
                "agent.message.delivered"
                if entry.status == STATUS_DELIVERED
                else "agent.message.failed"
            )
            self._emit(event_type, {
                "message_id": entry.id,
                "parent_id": entry.parent_id,
                "from_agent": entry.from_agent,
                "to_agent": entry.to_agent,
                "status": entry.status,
                "result": entry.result,
                "error": entry.error,
            })

            # Persistent callback (Doc 08 §4.6): only on non-cancelled
            # so cancel() doesn't trigger a callback storm.
            if (
                entry.reply_mode == REPLY_MODE_CALLBACK
                and entry.status in (STATUS_DELIVERED, STATUS_FAILED)
                and not self._closed
            ):
                try:
                    callback_aisop = self._build_callback_aisop(entry)
                    # B3 audit fix: defensive size guard in case future
                    # _build_callback_aisop changes inflate the payload.
                    # In practice this is well below 100KB (~2KB typical).
                    cb_size = len(json.dumps(callback_aisop, ensure_ascii=False).encode("utf-8"))
                    if cb_size > self.MAX_AISOP_BYTES:
                        logger.warning(
                            "Callback for %s skipped: callback aisop %d bytes > limit %d",
                            entry.id, cb_size, self.MAX_AISOP_BYTES,
                        )
                    else:
                        await self.send(
                            to_agent=entry.from_agent,
                            from_agent=entry.to_agent,
                            aisop=callback_aisop,
                            reply_mode=REPLY_MODE_NONE,  # callback never triggers another callback
                            parent_id=entry.id,
                            depth=entry.depth + 1,
                        )
                except ValueError as exc:
                    # depth_exceeded / loop_detected / etc. — log but don't fail the parent
                    logger.warning("Callback for %s rejected: %s", entry.id, exc)

    def _trace_senders(self, parent_id: str | None) -> set[str]:
        """Walk up parent chain via SQL store, collect from_agent only.

        NOTE: This was originally Doc 08 §4.7 Layer 3 loop detection, but the
        check was removed because it false-positives on legitimate callback
        patterns (A→B then B→A naturally puts A in the sender set). Kept as a
        diagnostic / observability utility — callers can use this to inspect
        the lineage of a chain without enforcing a policy.
        """
        senders: set[str] = set()
        if not self._store:
            return senders
        cur = parent_id
        steps = 0
        max_steps = self._max_depth + 2  # safety cap
        while cur and steps < max_steps:
            entry = self._store.get_entry(cur)
            if not entry:
                break
            senders.add(entry.from_agent)
            cur = entry.parent_id
            steps += 1
        return senders

    def _build_callback_aisop(self, msg: AgentMessageEntry) -> list:
        """Construct an AISOP payload that informs the original sender of completion."""
        return [
            {
                "role": "system",
                "content": {
                    "protocol": "AISOP V1.0.0",
                    "id": f"msg_callback.{msg.id}",
                    "describe": f"callback for {msg.id} from {msg.to_agent}",
                    "tools": [],
                    "system_prompt": "Process the callback result.",
                },
            },
            {
                "role": "user",
                "content": {
                    "instruction": "Execute aisop.main",
                    "aisop": {
                        "main": "graph TD; receive[receive callback] --> process[process result]; process --> endNode((End))",
                    },
                    "functions": {
                        "receive": {
                            "step1": f"You sent message {msg.id} to {msg.to_agent}.",
                            "step2": "Their response is in `result` (or `error` if it failed).",
                        },
                        "process": {
                            "step1": "Decide what to do with the result.",
                            "constraints": (
                                f"Result text: {(msg.result or msg.error or '(empty)')[:1000]}"
                            ),
                        },
                    },
                },
            },
        ]

    def _emit(self, event_type: str, data: dict) -> None:
        """Fire-and-forget event publish (mirrors schedule_service._emit).

        B4 audit fix (v1.7): catches Exception broadly so that bus errors
        (e.g. a dead-letter queue push, a buggy subscriber raising during
        the snapshot) cannot crash the dispatch path.
        """
        if not self._bus:
            return
        from ..bus.events import BusEvent

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._bus.publish(BusEvent(
                type=event_type,
                data=data,
                source="agent_message_service",
            )))
        except RuntimeError:
            pass  # no running loop (e.g. service used outside event loop)
        except Exception as exc:
            logger.warning("event-bus publish failed for %s: %s", event_type, exc)

    # ------------------------------------------------------------------
    # SQLite write helpers with retry (B1 audit fix, v1.7)
    # ------------------------------------------------------------------

    async def _safe_save(self, entry: AgentMessageEntry) -> None:
        """``store.save_entry`` with retry on transient SQLite lock errors.

        R1.1 audit fix (v1.8): now async, uses ``await asyncio.sleep`` for
        backoff so we don't block the event loop for ~350ms on contention.

        Re-raises after exhausting attempts so the caller can fail loudly
        (e.g. the disk-full case is non-recoverable; B2 fix relies on this).
        """
        await self._retry_db_write_async(
            self._store.save_entry, entry, label="save",
        )

    async def _safe_update(self, entry: AgentMessageEntry) -> None:
        """``store.update_entry`` with retry on transient SQLite lock errors.

        On final failure inside ``_dispatch.finally``, log and continue —
        we cannot raise from finally without losing the original exception.
        """
        try:
            await self._retry_db_write_async(
                self._store.update_entry, entry, label="update",
            )
        except Exception as exc:
            logger.error(
                "Failed to persist message %s status=%s after retries: %s",
                entry.id, entry.status, exc,
            )

    async def _retry_db_write_async(
        self, fn, entry: AgentMessageEntry, *, label: str,
    ) -> None:
        last_exc: Exception | None = None
        for attempt in range(self.SAVE_RETRY_ATTEMPTS):
            try:
                fn(entry)
                return
            except sqlite3.OperationalError as exc:
                # "database is locked" / "database table is locked" are
                # the canonical transient errors that benefit from retry.
                msg = str(exc).lower()
                if "locked" not in msg and "busy" not in msg:
                    raise  # different operational error — fail loudly
                last_exc = exc
                delay = self.SAVE_RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    "SQLite %s locked (attempt %d/%d); awaiting %.3fs",
                    label, attempt + 1, self.SAVE_RETRY_ATTEMPTS, delay,
                )
                await asyncio.sleep(delay)
        # Exhausted retries
        if last_exc:
            raise last_exc


# ---------------------------------------------------------------------------
# Module helpers
# ---------------------------------------------------------------------------

def _generate_msg_id() -> str:
    """Generate a short unique message id (8 hex chars from uuid4)."""
    return f"msg_{uuid.uuid4().hex[:8]}"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _entry_to_dict(entry: AgentMessageEntry) -> dict:
    return {
        "id": entry.id,
        "from_agent": entry.from_agent,
        "to_agent": entry.to_agent,
        "aisop": entry.aisop,
        "status": entry.status,
        "reply_mode": entry.reply_mode,
        "parent_id": entry.parent_id,
        "depth": entry.depth,
        "created_at": entry.created_at,
        "delivered_at": entry.delivered_at,
        "result": entry.result,
        "error": entry.error,
    }
