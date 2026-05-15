"""Fix 6 — tail ``_spans.jsonl`` and surface alertable spans.

An "alertable" span is one the operator should look at RIGHT NOW:
- ``status.status_code == "ERROR"``
- ``attributes["gen_ai.operation.name"]`` ∈ {"guardrail_abort", "resume"}
- any ``events[*].name`` in the critical set
  (``security.injection.suspected`` / ``acp.auth.error_detected`` /
   ``pipeline.guardrail.abort``)

This module exposes:
- :func:`redact_secrets` — regex-strip bot tokens / OpenAI-style keys before logging
- :func:`is_alertable_span` — pure predicate over a parsed span dict
- :func:`tail_file` — generator that yields new lines appended to a file
  (polling-based; no platform-specific inotify)
- :func:`run_tailer` — glue: tail + parse + filter + dispatch callback

Never sends Telegram itself — the dispatch callback is injected so tests
can assert what would have been sent without touching the network, and so
deployment wiring stays in one place.

Reference: Doc 12 v2.3 §10 + Doc 11 v3.2 §5.2
"""
from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Callable, Iterable, Iterator

logger = logging.getLogger(__name__)


# --- Redaction ------------------------------------------------------------

_TELEGRAM_TOKEN_RE = re.compile(r"bot\d+:[A-Za-z0-9_-]{20,}")
_OPENAI_STYLE_KEY_RE = re.compile(r"sk-[A-Za-z0-9_-]{20,}")
_ANTHROPIC_KEY_RE = re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}")
_BEARER_RE = re.compile(r"[Bb]earer\s+[A-Za-z0-9._-]{20,}")


def redact_secrets(text: str) -> str:
    """Strip common secrets from a log string.

    Covers Telegram bot tokens, OpenAI ``sk-*`` keys, Anthropic ``sk-ant-*``
    keys, and generic ``Bearer <...>`` authorization headers.
    """
    text = _ANTHROPIC_KEY_RE.sub("sk-ant-***", text)
    text = _OPENAI_STYLE_KEY_RE.sub("sk-***", text)
    text = _TELEGRAM_TOKEN_RE.sub("bot***:***", text)
    text = _BEARER_RE.sub("Bearer ***", text)
    return text


# --- Alert predicate ------------------------------------------------------

CRITICAL_OPERATION_NAMES = frozenset({"guardrail_abort", "resume"})
CRITICAL_EVENT_NAMES = frozenset(
    {
        "security.injection.suspected",
        "acp.auth.error_detected",
        "pipeline.guardrail.abort",
        "security.rule_of_two.triple",
    }
)


def is_alertable_span(span: dict) -> bool:
    """Return True if this span should trigger an operator alert."""
    status_code = (span.get("status") or {}).get("status_code")
    if status_code == "ERROR":
        return True

    attrs = span.get("attributes") or {}
    if attrs.get("gen_ai.operation.name") in CRITICAL_OPERATION_NAMES:
        return True
    if attrs.get("acp.auth.error_detected") is True:
        return True

    for ev in span.get("events") or []:
        if ev.get("name") in CRITICAL_EVENT_NAMES:
            return True

    return False


def format_alert(span: dict) -> str:
    """One-line alert-friendly summary of a span. Already redacted."""
    attrs = span.get("attributes") or {}
    name = span.get("name", "?")
    model = attrs.get("gen_ai.request.model", "")
    status = (span.get("status") or {}).get("status_code", "")
    desc = (span.get("status") or {}).get("description", "") or ""
    critical_events = [
        e.get("name")
        for e in (span.get("events") or [])
        if e.get("name") in CRITICAL_EVENT_NAMES
    ]
    parts = [f"[{status}] {name}"]
    if model:
        parts.append(f"model={model}")
    if critical_events:
        parts.append("events=" + ",".join(critical_events))
    if desc:
        parts.append(f"err={desc[:120]}")
    return redact_secrets(" | ".join(parts))


# --- Tailing --------------------------------------------------------------

def tail_file(
    path: Path,
    *,
    poll_interval_s: float = 0.5,
    from_start: bool = False,
    stop_predicate: Callable[[], bool] | None = None,
) -> Iterator[str]:
    """Yield appended lines from ``path`` forever (until stop_predicate).

    - If ``from_start``: emits all existing lines first, then tails.
    - Otherwise: starts at EOF and only emits new content.
    - If the file is rotated (inode change / size shrinks), re-opens.
    """
    path = Path(path)
    # Wait for file to appear
    while not path.exists():
        if stop_predicate and stop_predicate():
            return
        time.sleep(poll_interval_s)

    f = open(path, "r", encoding="utf-8")
    try:
        if not from_start:
            f.seek(0, 2)  # seek to EOF

        buffer = ""
        while True:
            if stop_predicate and stop_predicate():
                return

            chunk = f.read()
            if chunk:
                buffer += chunk
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line:
                        yield line
                continue

            # No new data — check for rotation
            try:
                if path.stat().st_size < f.tell():
                    # File truncated / rotated; reopen
                    f.close()
                    f = open(path, "r", encoding="utf-8")
                    buffer = ""
            except FileNotFoundError:
                f.close()
                while not path.exists():
                    if stop_predicate and stop_predicate():
                        return
                    time.sleep(poll_interval_s)
                f = open(path, "r", encoding="utf-8")
                buffer = ""

            time.sleep(poll_interval_s)
    finally:
        f.close()


def scan_lines(
    lines: Iterable[str],
    *,
    on_alert: Callable[[dict, str], None],
) -> int:
    """Parse each line as a span JSON; invoke ``on_alert`` if alertable.

    Returns the number of alerts fired. Malformed lines are skipped.
    ``on_alert`` receives ``(span_dict, formatted_message)``.
    """
    count = 0
    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            span = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if is_alertable_span(span):
            on_alert(span, format_alert(span))
            count += 1
    return count


def run_tailer(
    path: Path,
    *,
    on_alert: Callable[[dict, str], None],
    from_start: bool = False,
    poll_interval_s: float = 0.5,
    stop_predicate: Callable[[], bool] | None = None,
) -> int:
    """Tail ``path`` and dispatch alerts via ``on_alert``.

    Blocks forever unless ``stop_predicate`` returns True. Returns the
    total alert count when it exits.
    """
    lines = tail_file(
        path,
        poll_interval_s=poll_interval_s,
        from_start=from_start,
        stop_predicate=stop_predicate,
    )
    return scan_lines(lines, on_alert=on_alert)
