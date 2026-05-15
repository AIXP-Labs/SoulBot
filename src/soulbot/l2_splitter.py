"""L2 Splitter — Extract L1 (human text) and L2 (audit JSON) from AI response.

L2 format: AI response ends with ```json\n{...}\n``` containing
"Real Done Flow" and "L0" keys.
"""

from __future__ import annotations

import json
import re
from typing import NamedTuple, Optional


class L2Split(NamedTuple):
    """Result of splitting an AI response into L1 + L2."""
    l1: str          # Human-readable response (everything before L2 block)
    l2_json: str     # Raw L2 JSON string (empty if not found)
    l0: dict         # Extracted L0 dict from L2 (empty dict if not found)


# Match the last ```json ... ``` block in the response
_L2_PATTERN = re.compile(
    r"```json\s*\n(\{.*?\})\s*\n?```\s*$",
    re.DOTALL,
)


def split_l2(text: str) -> L2Split:
    """Split AI response into L1 text and L2 audit JSON.

    Returns L2Split(l1, l2_json, l0).
    If no valid L2 block found, l2_json is empty and l0 is {}.
    """
    if not text:
        return L2Split(l1="", l2_json="", l0={})

    m = _L2_PATTERN.search(text)
    if not m:
        return L2Split(l1=text, l2_json="", l0={})

    raw_json = m.group(1)
    try:
        parsed = json.loads(raw_json)
    except (json.JSONDecodeError, ValueError):
        return L2Split(l1=text, l2_json="", l0={})

    # Verify it looks like an L2 block (has Real Done Flow or L0)
    if not isinstance(parsed, dict):
        return L2Split(l1=text, l2_json="", l0={})

    if "Real Done Flow" not in parsed and "L0" not in parsed:
        return L2Split(l1=text, l2_json="", l0={})

    l1 = text[:m.start()].rstrip()
    l0 = parsed.get("L0", {})
    if not isinstance(l0, dict):
        l0 = {}

    return L2Split(l1=l1, l2_json=raw_json, l0=l0)


def format_l0_summary(l0: dict) -> str:
    """Format L0 dict as a compact one-line summary for Telegram display."""
    if not l0:
        return ""
    parts = []
    for key in ("intent", "confidence", "route", "state", "op"):
        val = l0.get(key)
        if val is not None:
            parts.append(f"{key}:{val}")
    return " | ".join(parts) if parts else json.dumps(l0, ensure_ascii=False)
