#!/usr/bin/env python3
"""aibp_parser.py — Parse AIBP format emails

Usage:
    echo '{"raw_email_json": ...}' | python aibp_parser.py --stdin

Features:
    - Subject [AIBP/{TYPE}] prefix parsing
    - X-AIBP-* custom header extraction
    - mail-parser-reply reply chain extraction (optional dependency)
    - Prompt injection filtering (first layer of three-layer defense)
    - source tagging (external_email)
    - charset-normalizer encoding fallback
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Optional

from _config import get_logger, parse_aibp_type
from _schemas import ErrorResult, ErrorCode

log = get_logger("aibp_parser")

# Prompt injection known attack patterns
_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions?", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(prior|previous|above)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(a\s+)?(my\s+)?(new\s+)?\w+\s+(assistant|agent|ai|bot|helper|model)", re.IGNORECASE),
    re.compile(r"system\s*:\s*", re.IGNORECASE),
    re.compile(r"<\|im_start\|>", re.IGNORECASE),
    re.compile(r"\[INST\]", re.IGNORECASE),
    re.compile(r"```\s*(system|assistant)", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Business logic
# ---------------------------------------------------------------------------

def parse_aibp_email(email_data: dict) -> dict:
    """Parse AIBP email and return structured result

    Args:
        email_data: dict containing from, subject, body, headers fields
                    (from email_inbox.py output or raw email JSON)
    """
    subject = email_data.get("subject", "")
    body = email_data.get("body", "") or email_data.get("body_preview", "")
    from_address = email_data.get("from_address", "") or email_data.get("from", "")
    headers = email_data.get("headers", {})

    # 1. AIBP message type (extracted from Subject)
    aibp_type = parse_aibp_type(subject)

    # 2. X-AIBP-* custom header extraction
    aibp_headers = {}
    for key, value in headers.items():
        k = key.lower()
        if k.startswith("x-aibp-"):
            aibp_headers[k] = value if isinstance(value, str) else value[0] if value else ""

    # If no X-AIBP-* headers found, try extracting from email_data top-level fields
    if not aibp_headers:
        for key in ("x-aibp-version", "x-aibp-ai-generated", "x-aibp-bot-name", "x-aibp-operator"):
            if key in email_data:
                aibp_headers[key] = email_data[key]

    aibp_version = aibp_headers.get("x-aibp-version")
    ai_generated = aibp_headers.get("x-aibp-ai-generated", "").lower() == "true"
    bot_name = aibp_headers.get("x-aibp-bot-name")
    operator = aibp_headers.get("x-aibp-operator")

    # 3. Thread info (header values may be str or list[str])
    def _header_str(key: str) -> str:
        val = headers.get(key, "")
        if isinstance(val, list):
            return val[0] if val else ""
        return val or ""

    message_id = email_data.get("message_id") or _header_str("message-id")
    in_reply_to = _header_str("in-reply-to")
    references = _header_str("references")
    thread_id = email_data.get("thread_id")

    # 4. Reply chain extraction (optional dependency mail-parser-reply)
    latest_reply = body
    try:
        from mail_parser_reply import EmailReplyParser
        reply = EmailReplyParser.parse_reply(body)
        if reply and reply.strip():
            latest_reply = reply.strip()
    except ImportError:
        pass  # mail-parser-reply not installed, use full body
    except Exception:
        pass

    # 5. Prompt injection filter (search + replace on sanitized_body)
    injection_detected = False
    sanitized_body = body
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(sanitized_body):
            injection_detected = True
            sanitized_body = pattern.sub("[FILTERED]", sanitized_body)
            log.warning("prompt_injection_detected", pattern=pattern.pattern, from_address=from_address)

    # 6. Body encoding handling
    if isinstance(sanitized_body, bytes):
        try:
            from charset_normalizer import from_bytes
            sanitized_body = str(from_bytes(sanitized_body).best())
        except Exception:
            sanitized_body = sanitized_body.decode("utf-8", errors="replace")

    # 7. AIBP protocol compliance check
    axiom_0 = aibp_headers.get("x-aibp-axiom-0", "")
    has_axiom_0 = bool(axiom_0)
    has_closing_seal = "Human Sovereignty and Wellbeing" in (sanitized_body or "")

    protocol_warnings = []
    if aibp_type and not has_axiom_0:
        protocol_warnings.append("Missing X-AIBP-Axiom-0 header (§9.2 violation)")
    if aibp_type and not has_closing_seal:
        protocol_warnings.append("Missing closing seal in body (§2.3)")

    return {
        "status": "ok",
        "source": "external_email",
        "sanitized": True,  # Always True: all emails pass through the security filter pipeline
        "type": aibp_type,
        "from_address": from_address,
        "subject": subject,
        "body": sanitized_body,
        "body_latest_reply": latest_reply if latest_reply != sanitized_body else None,
        "message_id": message_id,
        "in_reply_to": in_reply_to or None,
        "references": references or None,
        "thread_id": thread_id,
        "aibp_headers": {
            "version": aibp_version,
            "ai_generated": ai_generated,
            "bot_name": bot_name,
            "operator": operator,
            "axiom_0": axiom_0 or None,
        },
        "is_aibp": aibp_type is not None or bool(aibp_version),
        "has_closing_seal": has_closing_seal,
        "protocol_warnings": protocol_warnings,
        "injection_detected": injection_detected,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="AIBP email parser tool")
    parser.add_argument("--stdin", action="store_true", help="Read email JSON from stdin")
    args = parser.parse_args()

    try:
        if not args.stdin:
            error = ErrorResult(
                error_code=ErrorCode.MISSING_ARGUMENT,
                error="Must use --stdin to pass email JSON via stdin",
            )
            print(error.model_dump_json())
            return 2

        raw = sys.stdin.read(1_000_000)
        if len(raw) >= 1_000_000:
            error = ErrorResult(
                error_code=ErrorCode.CONTENT_TOO_LARGE,
                error="Input JSON exceeds 1MB limit",
            )
            print(error.model_dump_json())
            return 2

        try:
            email_data = json.loads(raw)
        except json.JSONDecodeError as e:
            error = ErrorResult(
                error_code=ErrorCode.STDIN_PARSE_ERROR,
                error=f"stdin JSON parse failed: {e}",
            )
            print(error.model_dump_json())
            return 2

        result = parse_aibp_email(email_data)
        print(json.dumps(result, ensure_ascii=False))
        return 0

    except Exception as e:
        error = ErrorResult(error_code=ErrorCode.RUNTIME_ERROR, error=str(e))
        print(error.model_dump_json())
        log.error("parser_error", error=str(e), exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
