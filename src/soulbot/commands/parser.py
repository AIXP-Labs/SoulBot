"""Command parser — extract SOULBOT_CMD directives from LLM output text."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

CMD_PREFIX = "<!--SOULBOT_CMD:"
CMD_SUFFIX = "-->"


@dataclass
class ParsedCommand:
    """A command extracted from LLM output."""

    service: str
    action: str
    params: dict
    raw: str  # original <!--SOULBOT_CMD:...--> text
    # Doc 12 v2.3 §7.1 Fix 8/12: W3C traceparent + tracestate + baggage carrier.
    # Populated by CommandExecutor.execute() from current OTel context; services
    # that persist commands (schedule / message.send) should save this so that
    # the deferred consumer can extract it back into context.
    otel_headers: dict = field(default_factory=dict)


def _find_json_end(text: str, start: int) -> int:
    """Find the closing brace of a JSON object starting at *start*.

    Uses bracket-balancing with string/escape awareness so that
    ``-->`` inside a JSON string value does not fool the parser.

    Returns:
        Index one past the closing ``}``, or ``-1`` if not found.
    """
    depth = 0
    in_string = False
    escape_next = False

    for i in range(start, len(text)):
        ch = text[i]

        if escape_next:
            escape_next = False
            continue

        if ch == "\\" and in_string:
            escape_next = True
            continue

        if ch == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i + 1

    return -1


def parse_commands(text: str) -> tuple[list[ParsedCommand], str]:
    """Extract all ``<!--SOULBOT_CMD:{...}-->`` commands from *text*.

    Returns:
        ``(commands, cleaned_text)`` — the list of parsed commands and
        the original text with all command markers removed.
    """
    commands: list[ParsedCommand] = []
    raws_to_remove: list[str] = []

    pos = 0
    while True:
        idx = text.find(CMD_PREFIX, pos)
        if idx == -1:
            break

        # Skip prefix, find JSON start
        json_start = idx + len(CMD_PREFIX)
        while json_start < len(text) and text[json_start] in (" ", "\t", "\n"):
            json_start += 1

        if json_start >= len(text) or text[json_start] != "{":
            pos = json_start
            continue

        # Find JSON end via bracket balancing
        json_end = _find_json_end(text, json_start)
        if json_end == -1:
            pos = json_start
            continue

        # Verify suffix -->
        rest = text[json_end:].lstrip()
        if not rest.startswith(CMD_SUFFIX):
            pos = json_end
            continue

        suffix_pos = text.index(CMD_SUFFIX, json_end)
        raw = text[idx : suffix_pos + len(CMD_SUFFIX)]

        # Parse JSON
        try:
            data = json.loads(text[json_start:json_end])
        except json.JSONDecodeError:
            pos = json_end
            continue

        service = data.pop("service", None)
        action = data.pop("action", None)
        if not service or not action:
            pos = json_end
            continue

        commands.append(
            ParsedCommand(service=service, action=action, params=data, raw=raw)
        )
        raws_to_remove.append(raw)
        pos = suffix_pos + len(CMD_SUFFIX)

    # Remove successfully parsed command markers
    cleaned = text
    for raw in raws_to_remove:
        cleaned = cleaned.replace(raw, "")

    # Clean up any malformed remnants
    cleaned = re.sub(r"<!--SOULBOT_CMD:.*?-->", "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    return commands, cleaned
