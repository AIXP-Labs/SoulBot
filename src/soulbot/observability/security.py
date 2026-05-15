"""Fix 13 — injection detection + Agents Rule of Two capability flags.

Helpers used by LLM call sites to emit ``security.injection.suspected``
events and by SOULBOT_CMD dispatch to flag ``security.rule_of_two.triple``.

This module only **observes** — it never blocks. Add hard-block gating
later (v4.0+) if threat data justifies it.

Reference: Doc 11 v3.2 §5.6 / Doc 12 v2.3 §8.2
"""
from __future__ import annotations

import re


# Common injection markers (Chinese + English). Extend as novel attacks appear.
INJECTION_PATTERNS = [
    re.compile(r"忽略(之前|上面|以上)的?(指令|命令|提示|instruction)", re.IGNORECASE),
    re.compile(
        r"ignore\s+(all\s+)?(previous|above|prior)\s+(instruction|prompt|rule)",
        re.IGNORECASE,
    ),
    # tag spoofing ("<system>", "</user>", etc.)
    re.compile(r"</?(system|user|assistant|instructions?)>", re.IGNORECASE),
    re.compile(r"forget\s+(all\s+)?(previous|above|prior)", re.IGNORECASE),
    re.compile(r"reveal\s+(your|the)\s+(system|initial)\s+prompt", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+", re.IGNORECASE),  # persona override
]


def scan_for_injection(text: str) -> list[str]:
    """Return list of matched pattern descriptions (for span event payload).

    Each entry is a short preview of the regex source, capped at 80 chars.
    """
    if not text:
        return []
    matches: list[str] = []
    for pat in INJECTION_PATTERNS:
        if pat.search(text):
            matches.append(pat.pattern[:80])
    return matches


class AgentCapabilityFlags:
    """Tri-bool capability markers for Agents Rule of Two.

    If an agent simultaneously has all three (reads untrusted input +
    accesses sensitive data + sends external messages), a human-in-the-loop
    checkpoint is recommended. SoulBot observes only; emits
    ``security.rule_of_two.triple`` span event when the triple lights up.
    """

    __slots__ = (
        "reads_untrusted_input",
        "accesses_sensitive_data",
        "sends_external_messages",
    )

    def __init__(
        self,
        reads_untrusted_input: bool = False,
        accesses_sensitive_data: bool = False,
        sends_external_messages: bool = False,
    ):
        self.reads_untrusted_input = reads_untrusted_input
        self.accesses_sensitive_data = accesses_sensitive_data
        self.sends_external_messages = sends_external_messages

    def hits_rule_of_two(self) -> bool:
        return all(
            [
                self.reads_untrusted_input,
                self.accesses_sensitive_data,
                self.sends_external_messages,
            ]
        )

    def to_dict(self) -> dict:
        return {
            "reads_untrusted_input": self.reads_untrusted_input,
            "accesses_sensitive_data": self.accesses_sensitive_data,
            "sends_external_messages": self.sends_external_messages,
        }
