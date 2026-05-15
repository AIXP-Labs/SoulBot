#!/usr/bin/env python3
"""email_send.py — Send AIBP email

Usage:
    echo '{"to":"aibot-alice@gmail.com","subject":"Hello","body":"..."}' | python email_send.py --stdin

Dual backend:
    - password    -> stdlib smtplib (SMTP)
    - oauth2_gmail -> Gmail API messages().send()

Features:
    - myl-discovery server auto-detection + fallback mapping
    - tenacity retry (transient failures)
    - pybreaker circuit breaker (persistent failures)
    - SQLite persistent rate limiting (global + per-recipient)
    - structlog structured logging (stderr)
    - JSON structured output (stdout)
"""

from __future__ import annotations

import argparse
import json
import smtplib
import sqlite3
import ssl
import sys
import time
from email.message import EmailMessage
from email.utils import make_msgid, formataddr, formatdate
from pathlib import Path
from typing import Optional

import pybreaker
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from _config import load_config, get_logger, AibpConfig, detect_smtp_server
from _schemas import SendResult, ErrorResult, ErrorCode

log = get_logger("email_send")


# ---------------------------------------------------------------------------
# Circuit breakers (process-level: reset on each subprocess call. Effective within single process.)
# SMTP and Gmail API use separate breakers for fault domain isolation.
# ---------------------------------------------------------------------------

smtp_breaker = pybreaker.CircuitBreaker(
    fail_max=5,
    reset_timeout=60,
    name="smtp_circuit",
)

gmail_send_breaker = pybreaker.CircuitBreaker(
    fail_max=5,
    reset_timeout=60,
    name="gmail_send_circuit",
)




# ---------------------------------------------------------------------------
# Rate limiting (SQLite persistent, cross-process effective)
# ---------------------------------------------------------------------------

_DATA_DIR = Path(__file__).parent.parent / "data"


def _ensure_send_log_table(conn: sqlite3.Connection) -> None:
    """Ensure send_log table exists"""
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS send_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient TEXT NOT NULL DEFAULT '',
            sent_at REAL NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_send_log_at ON send_log(sent_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_send_log_rcpt ON send_log(recipient, sent_at)")


def _check_rate_limit(config: AibpConfig, to: str = "") -> None:
    """Check rate limit (read-only, does not write send_log). Call _record_send() after successful send.

    Two-layer rate limiting:
    - Global: aibp_rate_limit_hour / aibp_rate_limit_day
    - Per-recipient: max 10/hour (anti-spam)
    """
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    db_path = _DATA_DIR / "aibp.db"
    conn = sqlite3.connect(str(db_path), timeout=5)
    try:
        _ensure_send_log_table(conn)
        now = time.time()
        conn.execute("DELETE FROM send_log WHERE sent_at < ?", (now - 86400,))
        conn.commit()

        # Global hourly limit
        hour_count = conn.execute(
            "SELECT COUNT(*) FROM send_log WHERE sent_at > ?", (now - 3600,)
        ).fetchone()[0]
        if hour_count >= config.aibp_rate_limit_hour:
            raise RuntimeError("SMTP_RATE_LIMITED: Hourly send limit reached")

        # Global daily limit
        day_count = conn.execute(
            "SELECT COUNT(*) FROM send_log WHERE sent_at > ?", (now - 86400,)
        ).fetchone()[0]
        if day_count >= config.aibp_rate_limit_day:
            raise RuntimeError("SMTP_RATE_LIMITED: Daily send limit reached")

        # Per-recipient hourly limit (max 10/hour, anti-spam)
        if to:
            rcpt_count = conn.execute(
                "SELECT COUNT(*) FROM send_log WHERE recipient = ? AND sent_at > ?",
                (to.lower(), now - 3600),
            ).fetchone()[0]
            if rcpt_count >= 10:
                raise RuntimeError(f"SMTP_RATE_LIMITED: Per-recipient limit reached for {to} (max 10/hour)")
    finally:
        conn.close()


def _record_send(to: str = "") -> None:
    """Record successful send to send_log (only called on success path)"""
    db_path = _DATA_DIR / "aibp.db"
    conn = sqlite3.connect(str(db_path), timeout=5)
    try:
        _ensure_send_log_table(conn)
        conn.execute("INSERT INTO send_log (recipient, sent_at) VALUES (?, ?)", (to.lower(), time.time()))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# password backend — smtplib
# ---------------------------------------------------------------------------

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, max=30),
    retry=retry_if_exception_type((ConnectionError, TimeoutError, smtplib.SMTPServerDisconnected)),
    reraise=True,
)
@smtp_breaker
def _send_smtp(config: AibpConfig, msg: EmailMessage) -> str:
    """Send email via SMTP, return Message-ID"""
    host, port = detect_smtp_server(config)
    password = config.aibp_email_password
    if password is None:
        raise RuntimeError("AUTH_PASSWORD_WRONG: AIBP_EMAIL_PASSWORD not configured")

    ctx = ssl.create_default_context()

    if port == 587:
        # STARTTLS
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.ehlo()
            server.starttls(context=ctx)
            server.ehlo()
            server.login(config.aibp_email_address, password.get_secret_value())
            server.send_message(msg)
    else:
        # SSL (465, 994, etc.)
        with smtplib.SMTP_SSL(host, port, context=ctx, timeout=10) as server:
            server.login(config.aibp_email_address, password.get_secret_value())
            server.send_message(msg)

    return msg["Message-ID"]


# ---------------------------------------------------------------------------
# oauth2_gmail backend — Gmail API
# ---------------------------------------------------------------------------

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, max=30),
    retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
    reraise=True,
)
@gmail_send_breaker
def _send_gmail_api(config: AibpConfig, msg: EmailMessage) -> str:
    """Send email via Gmail API, return Message-ID"""
    import base64
    from email_auth import get_gmail_service

    service = get_gmail_service(config)
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
    result = service.users().messages().send(
        userId="me",
        body={"raw": raw},
    ).execute()

    log.info("gmail_api_sent", gmail_id=result.get("id"))
    return msg["Message-ID"]


# ---------------------------------------------------------------------------
# Email construction
# ---------------------------------------------------------------------------

def _build_message(
    config: AibpConfig,
    to: str,
    subject: str,
    body: str,
    in_reply_to: Optional[str] = None,
    references: Optional[str] = None,
) -> EmailMessage:
    """Build EmailMessage with AIBP headers + threading headers (traditional mode)"""
    msg = EmailMessage()

    # SECURITY: sanitize Subject — strip CR/LF/NULL to prevent SMTP header injection
    safe_subject = subject.replace("\r", "").replace("\n", "").replace("\0", "")

    # Basic headers
    msg["From"] = formataddr((config.aibp_bot_name, config.aibp_email_address))
    msg["To"] = to
    msg["Subject"] = safe_subject
    msg["Date"] = formatdate(localtime=True)
    sender_domain = config.aibp_email_address.split("@")[1]
    msg["Message-ID"] = make_msgid(domain=sender_domain)

    # RFC 5322 threading headers
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = references

    # AIBP custom headers
    msg["X-AIBP-Version"] = config.aibp_version
    msg["X-AIBP-Axiom-0"] = "Human Sovereignty and Wellbeing"  # §9.2 MANDATORY
    msg["X-AIBP-AI-Generated"] = "true"
    msg["X-AIBP-Bot-Name"] = config.aibp_bot_name
    if config.aibp_operator:
        msg["X-AIBP-Operator"] = config.aibp_operator

    # L1 body is passed as-is (AI is responsible for including
    # greeting, sign-off, AI disclosure, and closing seal)
    msg.set_content(body)
    return msg


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def send_email(
    config: AibpConfig,
    to: str,
    subject: Optional[str] = None,
    body: Optional[str] = None,
    in_reply_to: Optional[str] = None,
    references: Optional[str] = None,
    raw_email: Optional[str] = None,
) -> dict:
    """Send email (auto-select backend), return structured result.

    Two modes:
    - raw_email mode: send pre-built MIME from aibp_builder (skip _build_message)
    - traditional mode: build internally ({to, subject, body} required)
    """
    # Validate recipient address
    from email_validator import validate_email, EmailNotValidError
    try:
        validate_email(to, check_deliverability=False)
    except EmailNotValidError as e:
        raise RuntimeError(f"EMAIL_INVALID_FORMAT: {to} — {e}")

    _check_rate_limit(config, to)

    if raw_email:
        # raw_email mode: parse pre-built MIME message
        from email import message_from_string
        msg = message_from_string(raw_email)
    else:
        # Traditional mode: build internally
        if not subject or not body:
            raise RuntimeError("MISSING_ARGUMENT: Traditional mode requires subject and body")
        msg = _build_message(config, to, subject, body, in_reply_to, references)

    if config.aibp_auth_method == "oauth2_gmail":
        message_id = _send_gmail_api(config, msg)
    else:
        message_id = _send_smtp(config, msg)

    _record_send(to)  # Record quota only after successful send
    log.info("email_sent", to=to, message_id=message_id)
    result = SendResult(message_id=message_id)
    return json.loads(result.model_dump_json())


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="AIBP email sender")
    parser.add_argument("--stdin", action="store_true", help="Read JSON params from stdin")
    args = parser.parse_args()

    try:
        config = load_config()

        if not args.stdin:
            error = ErrorResult(
                error_code=ErrorCode.MISSING_ARGUMENT,
                error="--stdin required. Pipe JSON via stdin.",
                suggestion="echo '{\"to\":\"...\",\"subject\":\"...\",\"body\":\"...\"}' | python email_send.py --stdin",
            )
            print(error.model_dump_json())
            return 2

        raw = sys.stdin.read(1_000_000)  # 1MB limit
        if len(raw) >= 1_000_000:
            error = ErrorResult(
                error_code=ErrorCode.CONTENT_TOO_LARGE,
                error="Input JSON exceeds 1MB limit",
            )
            print(error.model_dump_json())
            return 2
        try:
            params = json.loads(raw)
        except json.JSONDecodeError as e:
            error = ErrorResult(
                error_code=ErrorCode.STDIN_PARSE_ERROR,
                error=f"stdin JSON parse failed: {e}",
                suggestion="Ensure stdin input is valid JSON",
            )
            print(error.model_dump_json())
            return 2

        # raw_email mode (pre-built MIME from aibp_builder) vs traditional mode (to+subject+body)
        if "raw_email" in params:
            if "to" not in params:
                error = ErrorResult(
                    error_code=ErrorCode.MISSING_ARGUMENT,
                    error="raw_email mode requires 'to' parameter",
                )
                print(error.model_dump_json())
                return 2
            result = send_email(
                config=config,
                to=params["to"],
                raw_email=params["raw_email"],
            )
        else:
            required = {"to", "subject", "body"}
            missing = required - params.keys()
            if missing:
                error = ErrorResult(
                    error_code=ErrorCode.MISSING_ARGUMENT,
                    error=f"Missing required params: {', '.join(sorted(missing))}",
                )
                print(error.model_dump_json())
                return 2
            result = send_email(
                config=config,
                to=params["to"],
                subject=params["subject"],
                body=params["body"],
                in_reply_to=params.get("in_reply_to"),
                references=params.get("references"),
            )
        print(json.dumps(result, ensure_ascii=False))
        return 0

    except pybreaker.CircuitBreakerError:
        backend = "Gmail API" if config.aibp_auth_method == "oauth2_gmail" else "SMTP"
        error = ErrorResult(
            error_code=ErrorCode.CIRCUIT_OPEN,
            error=f"{backend} service unavailable (circuit open), auto-retry in 60s",
            retryable=True,
            retry_after_seconds=60,
        )
        print(error.model_dump_json())
        log.error("circuit_open", error_code=error.error_code, backend=backend)
        return 1

    except smtplib.SMTPAuthenticationError:
        error = ErrorResult(
            error_code=ErrorCode.AUTH_PASSWORD_WRONG,
            error="SMTP authentication failed: wrong password/authorization code",
            suggestion="Check AIBP_EMAIL_PASSWORD in .env (QQ/163 require authorization code, not login password)",
        )
        print(error.model_dump_json())
        log.error("auth_failed", error_code=error.error_code)
        return 3

    except smtplib.SMTPRecipientsRefused as e:
        error = ErrorResult(
            error_code=ErrorCode.SMTP_RECIPIENT_REJECTED,
            error=f"Recipient rejected: {e}",
        )
        print(error.model_dump_json())
        log.error("recipient_rejected", error_code=error.error_code)
        return 1

    except Exception as e:
        error_code = ErrorCode.RUNTIME_ERROR
        exit_code = 1
        if "RATE_LIMITED" in str(e):
            error_code = ErrorCode.SMTP_RATE_LIMITED
        elif "CONFIG" in str(e):
            error_code = ErrorCode.CONFIG_MISSING
            exit_code = 4

        error = ErrorResult(
            error_code=error_code,
            error=str(e),
            retryable=error_code in (ErrorCode.SMTP_RATE_LIMITED, ErrorCode.SMTP_CONNECT_TIMEOUT),
        )
        print(error.model_dump_json())
        log.error("send_error", error=str(e), exc_info=True)
        return exit_code


if __name__ == "__main__":
    sys.exit(main())
