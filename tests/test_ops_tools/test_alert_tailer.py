"""Fix 6 — alert tailer: redact, predicate, tail loop."""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from tools.alert_tailer import (
    CRITICAL_EVENT_NAMES,
    CRITICAL_OPERATION_NAMES,
    format_alert,
    is_alertable_span,
    redact_secrets,
    run_tailer,
    scan_lines,
    tail_file,
)


# --- Redaction ------------------------------------------------------------

class TestRedact:
    def test_telegram_bot_token(self):
        msg = "visiting https://api.telegram.org/bot123456:AAABBBCCCDDDEEEFFFGGGHHH-XYZ/send"
        out = redact_secrets(msg)
        assert "bot123456" not in out
        assert "bot***:***" in out

    def test_openai_style_key(self):
        msg = "Authorization: sk-proj-ABCDEFGHIJKLMNOPQRSTUVWXYZ0123"
        out = redact_secrets(msg)
        assert "ABCDEFGHIJKLMN" not in out
        assert "sk-***" in out

    def test_anthropic_key(self):
        msg = "x-api-key: sk-ant-api03-XXXXXXXXXXXXXXXXXXXXXX"
        out = redact_secrets(msg)
        assert "api03-XXXX" not in out
        assert "sk-ant-***" in out

    def test_bearer_token(self):
        msg = "Bearer eyJabcdefghijklmnopqrstuvwxyz0123456"
        out = redact_secrets(msg)
        assert "eyJabcdefgh" not in out
        assert "Bearer ***" in out

    def test_clean_message_unchanged(self):
        assert redact_secrets("hello world") == "hello world"


# --- Predicate ------------------------------------------------------------

def _span(
    *, status: str = "OK", op: str | None = None, events: list | None = None,
    auth_err: bool = False,
) -> dict:
    attrs: dict = {}
    if op is not None:
        attrs["gen_ai.operation.name"] = op
    if auth_err:
        attrs["acp.auth.error_detected"] = True
    return {
        "name": "test",
        "status": {"status_code": status, "description": ""},
        "attributes": attrs,
        "events": events or [],
    }


class TestIsAlertable:
    def test_error_status_alertable(self):
        assert is_alertable_span(_span(status="ERROR")) is True

    def test_ok_status_not_alertable(self):
        assert is_alertable_span(_span(status="OK")) is False

    def test_guardrail_abort_alertable(self):
        assert is_alertable_span(_span(op="guardrail_abort")) is True

    def test_resume_alertable(self):
        assert is_alertable_span(_span(op="resume")) is True

    def test_auth_error_alertable(self):
        assert is_alertable_span(_span(auth_err=True)) is True

    def test_critical_event_alertable(self):
        span = _span(events=[{"name": "security.injection.suspected"}])
        assert is_alertable_span(span) is True

    def test_non_critical_event_not_alertable(self):
        span = _span(events=[{"name": "acp.retry"}])
        assert is_alertable_span(span) is False

    def test_all_critical_event_names_trigger(self):
        for name in CRITICAL_EVENT_NAMES:
            assert is_alertable_span(_span(events=[{"name": name}])) is True, name

    def test_all_critical_operation_names_trigger(self):
        for op in CRITICAL_OPERATION_NAMES:
            assert is_alertable_span(_span(op=op)) is True, op


class TestFormatAlert:
    def test_redacts_secret_in_description(self):
        span = {
            "name": "http_call",
            "status": {
                "status_code": "ERROR",
                "description": "failed with sk-ant-api03-XXXXXXXXXXXXXXXXXXXXXX",
            },
            "attributes": {},
            "events": [],
        }
        msg = format_alert(span)
        assert "sk-ant-***" in msg
        assert "api03-XXXX" not in msg

    def test_includes_status_and_name(self):
        span = _span(status="ERROR")
        span["name"] = "invoke_agent"
        msg = format_alert(span)
        assert "ERROR" in msg and "invoke_agent" in msg


# --- scan_lines / run_tailer ---------------------------------------------

def test_scan_lines_fires_callback(tmp_path):
    alerts: list[tuple[dict, str]] = []
    lines = [
        json.dumps(_span(status="ERROR")),
        json.dumps(_span(status="OK")),
        "not-json",
        "",
        json.dumps(_span(op="guardrail_abort")),
    ]
    count = scan_lines(lines, on_alert=lambda span, msg: alerts.append((span, msg)))
    assert count == 2
    assert len(alerts) == 2


def test_run_tailer_from_start(tmp_path):
    p = tmp_path / "_spans.jsonl"
    p.write_text(
        json.dumps(_span(status="ERROR")) + "\n"
        + json.dumps(_span(status="OK")) + "\n",
        encoding="utf-8",
    )

    collected: list[str] = []
    # Stop after one poll cycle
    stop = {"done": False}

    def stop_pred():
        return stop["done"]

    alerts: list = []

    def _worker():
        run_tailer(
            p,
            on_alert=lambda span, msg: alerts.append(msg),
            from_start=True,
            poll_interval_s=0.05,
            stop_predicate=stop_pred,
        )
        collected.append("done")

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    # Give the tailer time to process the 2 existing lines
    time.sleep(0.25)
    stop["done"] = True
    t.join(timeout=2)

    assert len(alerts) == 1  # only the ERROR row
