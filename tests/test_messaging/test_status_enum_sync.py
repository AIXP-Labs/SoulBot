"""Cross-language consistency: Python status constants vs TypeScript enum.

N4 audit fix (v1.5.1): status values are declared in two places —
  - Python: src/soulbot/messaging/message_entry.py
  - TypeScript: frontend/src/types/messageStatus.ts

This test parses the TypeScript file and verifies every value matches
the Python constant, so adding a status to one side and forgetting the
other is caught immediately by the test suite.
"""

import re
from pathlib import Path

import pytest

from soulbot.messaging.message_entry import (
    REPLY_MODE_CALLBACK,
    REPLY_MODE_NONE,
    STATUS_CANCELLED,
    STATUS_DELIVERED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_PROCESSING,
)


_TS_FILE = Path(__file__).resolve().parents[2] / "frontend" / "src" / "types" / "messageStatus.ts"


@pytest.fixture(scope="module")
def ts_source() -> str:
    if not _TS_FILE.is_file():
        pytest.skip(f"messageStatus.ts not found at {_TS_FILE}")
    return _TS_FILE.read_text(encoding="utf-8")


def _extract_const_values(ts: str, const_name: str) -> dict[str, str]:
    """Parse `export const NAME = { KEY: 'value', ... } as const`."""
    pattern = rf"export const {const_name} = \{{([^}}]+)\}}"
    m = re.search(pattern, ts)
    if not m:
        return {}
    body = m.group(1)
    out: dict[str, str] = {}
    for line in body.splitlines():
        kv = re.match(r"\s*(\w+):\s*'([^']*)'", line)
        if kv:
            out[kv.group(1)] = kv.group(2)
    return out


class TestStatusEnumSync:
    def test_all_python_statuses_present_in_ts(self, ts_source):
        ts_status = _extract_const_values(ts_source, "MESSAGE_STATUS")
        py_statuses = {
            STATUS_PENDING, STATUS_PROCESSING, STATUS_DELIVERED,
            STATUS_FAILED, STATUS_CANCELLED,
        }
        ts_values = set(ts_status.values())
        missing = py_statuses - ts_values
        assert not missing, (
            f"Python statuses missing from TS messageStatus.ts: {missing}. "
            f"Update frontend/src/types/messageStatus.ts to match."
        )

    def test_all_ts_statuses_present_in_python(self, ts_source):
        ts_status = _extract_const_values(ts_source, "MESSAGE_STATUS")
        py_statuses = {
            STATUS_PENDING, STATUS_PROCESSING, STATUS_DELIVERED,
            STATUS_FAILED, STATUS_CANCELLED,
        }
        ts_values = set(ts_status.values())
        extra = ts_values - py_statuses
        assert not extra, (
            f"TS statuses not declared in Python message_entry.py: {extra}. "
            f"Update src/soulbot/messaging/message_entry.py to match."
        )

    def test_reply_modes_match(self, ts_source):
        ts_modes = _extract_const_values(ts_source, "MESSAGE_REPLY_MODE")
        py_modes = {REPLY_MODE_NONE, REPLY_MODE_CALLBACK}
        ts_values = set(ts_modes.values())
        assert ts_values == py_modes, (
            f"reply_mode mismatch: Python={py_modes} TS={ts_values}"
        )
