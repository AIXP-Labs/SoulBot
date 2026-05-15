"""Fix 4 — HTML viewer for OTel ReadableSpan JSON lines (``_spans.jsonl``).

Reads a ``_spans.jsonl`` file produced by
:class:`soulbot.observability.otel_setup.FileSpanExporter` and emits a
self-contained HTML report with one row per span, including:

- name / service / duration (ms)
- ``gen_ai.request.model`` / ``gen_ai.provider.name`` / ``acp.provider.name``
- ``gen_ai.server.time_to_first_token`` (TTFT) — streaming only
- TPOT (time-per-output-token) — estimated from TTFT + output tokens
- status code + error message
- grouped under their ``trace_id``

No external deps. Works offline. Output is a single HTML file.

Reference: Doc 12 v2.3 §10 + Doc 11 v3.2 §4.2
"""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any, Iterable


def parse_spans_jsonl(path: Path) -> list[dict]:
    """Parse a JSONL file into a list of span dicts.

    Malformed lines are skipped (logged) so a partial write doesn't break the
    viewer. Returns spans in file order.
    """
    spans: list[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            try:
                spans.append(json.loads(raw))
            except json.JSONDecodeError:
                continue  # skip partial lines
    return spans


def _duration_ms(span: dict) -> float:
    """Compute span duration in milliseconds from start_time/end_time.

    OTel to_json emits these as ISO strings OR as integer ns — handle both.
    Returns 0.0 if parseable fields are missing.
    """
    start = span.get("start_time")
    end = span.get("end_time")
    if start is None or end is None:
        return 0.0
    if isinstance(start, (int, float)) and isinstance(end, (int, float)):
        return (float(end) - float(start)) / 1e6

    # ISO string: "2026-04-14T12:34:56.789000Z"
    try:
        from datetime import datetime

        def _parse(s: str) -> datetime:
            # OTel ISO often ends in "Z"; datetime.fromisoformat accepts it in 3.11+
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            return datetime.fromisoformat(s)

        return (_parse(end) - _parse(start)).total_seconds() * 1000
    except Exception:
        return 0.0


def _estimated_tpot_ms(span: dict, ttft_s: float) -> float | None:
    """Estimate time-per-output-token in ms = (total_ms - ttft_ms) / out_tokens."""
    attrs = span.get("attributes") or {}
    out_tokens = attrs.get("gen_ai.usage.output_tokens")
    if not out_tokens or out_tokens <= 0:
        return None
    total_ms = _duration_ms(span)
    ttft_ms = ttft_s * 1000.0
    remaining = max(total_ms - ttft_ms, 0.0)
    return remaining / out_tokens


def _row_html(span: dict) -> str:
    attrs = span.get("attributes") or {}
    status = (span.get("status") or {}).get("status_code", "")
    err = (span.get("status") or {}).get("description", "") or ""
    ttft = attrs.get("gen_ai.server.time_to_first_token")
    tpot = _estimated_tpot_ms(span, ttft) if ttft is not None else None

    status_class = "ok" if status == "OK" else ("err" if status == "ERROR" else "")

    cells = [
        html.escape(str(span.get("name", ""))),
        f"{_duration_ms(span):.1f}",
        html.escape(str(attrs.get("gen_ai.request.model", ""))),
        html.escape(str(attrs.get("gen_ai.provider.name", ""))),
        html.escape(str(attrs.get("acp.provider.name", ""))),
        f"{ttft:.3f}" if ttft is not None else "-",
        f"{tpot:.1f}" if tpot is not None else "-",
        f'<span class="{status_class}">{html.escape(status)}</span>',
        html.escape(err[:120]),
    ]
    return "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"


_CSS = """
body { font-family: ui-monospace, monospace; margin: 1em; background: #fafafa; }
h1 { font-size: 1.2em; }
details { margin: 0.6em 0; border: 1px solid #ccc; border-radius: 4px; padding: 0.4em 0.8em; background: white; }
summary { cursor: pointer; font-weight: bold; }
table { border-collapse: collapse; width: 100%; margin-top: 0.4em; font-size: 0.85em; }
th, td { border: 1px solid #ddd; padding: 4px 8px; text-align: left; vertical-align: top; }
th { background: #eef; }
.ok { color: #0a7a0a; }
.err { color: #b00; font-weight: bold; }
.meta { color: #666; font-size: 0.85em; }
"""


def render_html(spans: Iterable[dict], *, title: str = "SoulBot _spans.jsonl") -> str:
    """Render an HTML report grouped by trace_id."""
    spans_list = list(spans)
    # Group by trace_id (fallback: "unknown")
    groups: dict[str, list[dict]] = {}
    for s in spans_list:
        tid = ((s.get("context") or {}).get("trace_id") or "unknown")
        groups.setdefault(tid, []).append(s)

    parts: list[str] = [
        "<!doctype html>",
        '<html><head><meta charset="utf-8">',
        f"<title>{html.escape(title)}</title>",
        f"<style>{_CSS}</style>",
        "</head><body>",
        f"<h1>{html.escape(title)}</h1>",
        f'<div class="meta">{len(spans_list)} span(s) across {len(groups)} trace(s)</div>',
    ]

    for tid, group in groups.items():
        parts.append(f"<details open><summary>trace <code>{html.escape(tid)}</code> — {len(group)} span(s)</summary>")
        parts.append(
            "<table><thead><tr>"
            "<th>name</th><th>ms</th><th>model</th><th>provider</th><th>acp</th>"
            "<th>TTFT s</th><th>TPOT ms/tok</th><th>status</th><th>error</th>"
            "</tr></thead><tbody>"
        )
        for s in group:
            parts.append(_row_html(s))
        parts.append("</tbody></table></details>")

    parts.append("</body></html>")
    return "\n".join(parts)


def render_file(input_path: Path, output_path: Path) -> None:
    """Read ``input_path`` spans and write HTML to ``output_path``."""
    spans = parse_spans_jsonl(input_path)
    html_text = render_html(spans, title=input_path.name)
    output_path.write_text(html_text, encoding="utf-8")


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Render _spans.jsonl to HTML")
    parser.add_argument("input", type=Path)
    parser.add_argument("-o", "--output", type=Path, default=Path("pipeline.html"))
    args = parser.parse_args()
    render_file(args.input, args.output)
    print(f"wrote {args.output}")


if __name__ == "__main__":  # pragma: no cover
    _cli()
