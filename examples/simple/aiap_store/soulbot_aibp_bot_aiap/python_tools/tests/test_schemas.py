"""test_schemas.py — Pydantic model serialization tests"""

from __future__ import annotations

import json
from datetime import datetime, timezone


class TestEmailSummary:
    def test_serialize_roundtrip(self):
        from _schemas import EmailSummary
        summary = EmailSummary(
            uid="123",
            from_address="aibot-alice@gmail.com",
            subject="[AIBP/CHAT] Hello",
            type="CHAT",
            message_id="<abc@gmail.com>",
            body_preview="Hello world",
            date=datetime(2026, 4, 11, tzinfo=timezone.utc),
        )
        data = json.loads(summary.model_dump_json())
        assert data["uid"] == "123"
        assert data["type"] == "CHAT"
        assert data["has_attachments"] is False
        assert data["attachment_count"] == 0
        assert data["body_truncated"] is False

    def test_optional_fields_default(self):
        from _schemas import EmailSummary
        summary = EmailSummary(
            uid="1",
            from_address="a@b.com",
            subject="test",
            body_preview="x",
            date=datetime.now(timezone.utc),
        )
        assert summary.type is None
        assert summary.thread_id is None
        assert summary.message_id is None


class TestErrorResult:
    def test_error_structure(self):
        from _schemas import ErrorResult, ErrorCode
        err = ErrorResult(
            error_code=ErrorCode.AUTH_PASSWORD_WRONG,
            error="Wrong password",
            retryable=False,
            suggestion="Check .env",
        )
        data = json.loads(err.model_dump_json())
        assert data["status"] == "error"
        assert data["error_code"] == "AUTH_PASSWORD_WRONG"
        assert data["retryable"] is False
        assert data["suggestion"] == "Check .env"

    def test_retryable_with_delay(self):
        from _schemas import ErrorResult, ErrorCode
        err = ErrorResult(
            error_code=ErrorCode.CIRCUIT_OPEN,
            error="Circuit open",
            retryable=True,
            retry_after_seconds=60,
        )
        data = json.loads(err.model_dump_json())
        assert data["retryable"] is True
        assert data["retry_after_seconds"] == 60


class TestInboxResult:
    def test_empty_inbox(self):
        from _schemas import InboxResult
        result = InboxResult()
        data = json.loads(result.model_dump_json())
        assert data["status"] == "ok"
        assert data["data"] == []
        assert data["bounces"] == []
        assert data["remaining"] == 0


class TestBounceInfo:
    def test_hard_bounce(self):
        from _schemas import BounceInfo
        bounce = BounceInfo(
            type="hard",
            original_to="invalid@example.com",
            status_code="5.1.1",
            diagnostic="User unknown",
        )
        assert bounce.type == "hard"
        assert bounce.status_code == "5.1.1"


class TestErrorCodes:
    def test_all_codes_are_strings(self):
        from _schemas import ErrorCode
        for attr in dir(ErrorCode):
            if attr.startswith("_"):
                continue
            val = getattr(ErrorCode, attr)
            assert isinstance(val, str), f"ErrorCode.{attr} should be str, got {type(val)}"

    def test_stdin_parse_error_exists(self):
        from _schemas import ErrorCode
        assert hasattr(ErrorCode, "STDIN_PARSE_ERROR")
        assert ErrorCode.STDIN_PARSE_ERROR == "STDIN_PARSE_ERROR"
