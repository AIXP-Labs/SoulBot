#!/usr/bin/env python3
"""email_inbox.py — Check inbox for unread AIBP emails

Usage:
    python email_inbox.py --check-unseen          # Check unread emails (max 5)
    python email_inbox.py --mark-read --uid 123    # Mark as read
    python email_inbox.py --health                 # Health check

Dual backend support:
    - password    -> imap-tools (IMAP protocol)
    - oauth2_gmail -> Gmail API messages().list()

Features:
    - Two-step marking (crash-safe)
    - Processing lock (prevent duplicate processing)
    - Message-ID idempotent dedup (SQLite UNIQUE)
    - Bounce (NDR) detection
    - Content size limit (50KB)
    - pybreaker circuit breaker
    - tenacity retry
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pybreaker
from filelock import FileLock, Timeout as FileLockTimeout
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from _config import load_config, get_logger, AibpConfig, detect_imap_server, detect_smtp_server, parse_aibp_type
from _schemas import (
    EmailSummary, BounceInfo, InboxResult, MarkReadResult,
    HealthResult, HealthCheck, ErrorResult, ErrorCode,
)

log = get_logger("email_inbox")

_TOOLS_DIR = Path(__file__).parent
_DATA_DIR = _TOOLS_DIR.parent / "data"
_DB_PATH = _DATA_DIR / "aibp.db"
_PROCESSING_LOCK = _DATA_DIR / "processing.lock"
_MAX_UNSEEN = 5
_MAX_BODY_SIZE = 50_000  # 50KB
_PROCESSING_TIMEOUT = 300  # 5 minutes


# ---------------------------------------------------------------------------
# Circuit breaker (process-level: counter resets on each subprocess call.
# Within a single process, retry 3x * breaker 5x is still effective.
# Cross-process persistence requires SQLite backend, not needed here.
# IMAP and Gmail API use independent breakers for fault isolation.)
# ---------------------------------------------------------------------------

imap_breaker = pybreaker.CircuitBreaker(
    fail_max=5,
    reset_timeout=60,
    name="imap_circuit",
)

gmail_inbox_breaker = pybreaker.CircuitBreaker(
    fail_max=5,
    reset_timeout=60,
    name="gmail_inbox_circuit",
)


# ---------------------------------------------------------------------------
# SQLite initialization
# ---------------------------------------------------------------------------

def _ensure_db(retention_days: int = 365) -> sqlite3.Connection:
    """Ensure data directory and SQLite database exist

    Args:
        retention_days: GDPR data retention days (from config.aibp_data_retention_days)
    """
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS processed_emails (
            uid TEXT,
            message_id TEXT UNIQUE,
            from_address TEXT,
            processed_at TEXT,
            result TEXT,
            response_message_id TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS processing_queue (
            uid TEXT PRIMARY KEY,
            message_id TEXT,
            from_address TEXT,
            started_at REAL
        )
    """)
    # Clean up expired records (GDPR data retention, days from config)
    conn.execute(
        "DELETE FROM processed_emails WHERE processed_at < datetime('now', ? || ' days')",
        (f"-{retention_days}",),
    )
    conn.commit()
    return conn


def _is_processed(conn: sqlite3.Connection, message_id: str) -> bool:
    """Check if email is already processed (Message-ID idempotent)"""
    row = conn.execute(
        "SELECT 1 FROM processed_emails WHERE message_id = ?",
        (message_id,),
    ).fetchone()
    return row is not None


def _is_in_processing(conn: sqlite3.Connection, uid: str) -> bool:
    """Check if email is in processing queue (prevent duplicate processing)"""
    row = conn.execute(
        "SELECT started_at FROM processing_queue WHERE uid = ?",
        (uid,),
    ).fetchone()
    if row is None:
        return False
    # Timeout release
    if time.time() - row[0] > _PROCESSING_TIMEOUT:
        conn.execute("DELETE FROM processing_queue WHERE uid = ?", (uid,))
        conn.commit()
        return False
    return True


def _add_to_processing(conn: sqlite3.Connection, uid: str, message_id: str, from_address: str = "") -> None:
    """Add to processing queue"""
    conn.execute(
        "INSERT OR REPLACE INTO processing_queue (uid, message_id, from_address, started_at) VALUES (?, ?, ?, ?)",
        (uid, message_id, from_address, time.time()),
    )
    conn.commit()


def _mark_processed(conn: sqlite3.Connection, uid: str, message_id: str, from_addr: str) -> None:
    """Mark as processed and remove from processing queue"""
    conn.execute(
        "INSERT OR IGNORE INTO processed_emails (uid, message_id, from_address, processed_at) VALUES (?, ?, ?, ?)",
        (uid, message_id, from_addr, datetime.now(timezone.utc).isoformat()),
    )
    conn.execute("DELETE FROM processing_queue WHERE uid = ?", (uid,))
    conn.commit()


# ---------------------------------------------------------------------------
# Bounce detection
# ---------------------------------------------------------------------------

def _detect_bounce(msg) -> Optional[BounceInfo]:
    """Detect if email is a bounce (NDR)"""
    from_addr = str(getattr(msg, "from_", "")).lower()
    subject = str(getattr(msg, "subject", "")).lower()
    content_type = str(getattr(msg, "content_type", "")).lower()

    is_bounce = (
        "mailer-daemon" in from_addr
        or "postmaster@" in from_addr
        or "multipart/report" in content_type
        or "delivery status notification" in subject
        or "undeliverable" in subject
        or "\u9000\u4fe1" in subject  # Chinese "bounce"
    )

    if not is_bounce:
        return None

    # Try to extract bounce details
    body = str(getattr(msg, "text", "") or "")
    bounce_type = "hard" if any(c in body for c in ("5.1.1", "5.1.0", "User unknown", "does not exist")) else "soft"

    return BounceInfo(
        type=bounce_type,
        original_to="",  # NDR body parsing is complex, left empty
        diagnostic=body[:200] if body else None,
    )


# ---------------------------------------------------------------------------
# password backend — imap-tools
# ---------------------------------------------------------------------------

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, max=30),
    retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
    reraise=True,
)
@imap_breaker
def _fetch_unseen_imap(config: AibpConfig, conn: sqlite3.Connection) -> InboxResult:
    """Fetch unread emails via IMAP"""
    from imap_tools import MailBox, AND

    host, port = detect_imap_server(config)
    password = config.aibp_email_password
    if password is None:
        raise RuntimeError("AUTH_PASSWORD_WRONG: AIBP_EMAIL_PASSWORD not configured")

    emails: list[EmailSummary] = []
    bounces: list[BounceInfo] = []
    remaining = 0

    with MailBox(host, port).login(
        config.aibp_email_address,
        password.get_secret_value(),
    ) as mb:
        unseen = list(mb.fetch(AND(seen=False), limit=_MAX_UNSEEN + 20, mark_seen=False))

        for msg in unseen:
            uid = str(msg.uid)
            message_id = msg.headers.get("message-id", [None])[0] or f"uid-{uid}@{config.aibp_email_address}"

            # Bounce detection
            bounce = _detect_bounce(msg)
            if bounce:
                bounce.original_message_id = message_id
                bounces.append(bounce)
                continue

            # Idempotent dedup
            if _is_processed(conn, message_id):
                continue
            if _is_in_processing(conn, uid):
                continue

            # Body truncation
            body = msg.text or msg.html or ""
            if isinstance(body, bytes):
                try:
                    from charset_normalizer import from_bytes
                    body = str(from_bytes(body).best())
                except Exception:
                    body = body.decode("utf-8", errors="replace")

            truncated = len(body) > _MAX_BODY_SIZE
            full_body = body[:_MAX_BODY_SIZE] if truncated else body
            preview = body[:200]

            subject = msg.subject or ""
            aibp_type = parse_aibp_type(subject)

            email_summary = EmailSummary(
                uid=uid,
                from_address=str(msg.from_),
                subject=subject,
                type=aibp_type,
                message_id=message_id,
                body=full_body,
                body_preview=preview,
                body_truncated=truncated,
                date=msg.date or datetime.now(timezone.utc),
                has_attachments=len(msg.attachments) > 0,
                attachment_count=len(msg.attachments),
            )
            emails.append(email_summary)

            # Add to processing queue
            _add_to_processing(conn, uid, message_id, str(msg.from_))

            if len(emails) >= _MAX_UNSEEN:
                remaining = len(unseen) - len(emails) - len(bounces)
                break

    return InboxResult(data=emails, bounces=bounces, remaining=max(0, remaining))


# ---------------------------------------------------------------------------
# oauth2_gmail backend — Gmail API
# ---------------------------------------------------------------------------

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, max=30),
    retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
    reraise=True,
)
@gmail_inbox_breaker
def _fetch_unseen_gmail_api(config: AibpConfig, conn: sqlite3.Connection) -> InboxResult:
    """Fetch unread emails via Gmail API"""
    import base64
    from email import message_from_bytes
    from email_auth import get_gmail_service

    service = get_gmail_service(config)
    results = service.users().messages().list(
        userId="me",
        q="is:unread",
        maxResults=_MAX_UNSEEN + 10,
    ).execute()

    messages = results.get("messages", [])
    emails: list[EmailSummary] = []
    bounces: list[BounceInfo] = []

    for item in messages:
        if len(emails) >= _MAX_UNSEEN:
            break

        full = service.users().messages().get(
            userId="me",
            id=item["id"],
            format="raw",
        ).execute()

        raw_bytes = base64.urlsafe_b64decode(full["raw"])
        msg = message_from_bytes(raw_bytes)

        uid = item["id"]
        message_id = msg.get("Message-ID") or f"gmail-{uid}@{config.aibp_email_address}"

        if _is_processed(conn, message_id):
            continue
        if _is_in_processing(conn, uid):
            continue

        # Bounce detection (Gmail API backend)
        from_header = msg.get("From", "").lower()
        subject_header = msg.get("Subject", "").lower()
        content_type_header = msg.get("Content-Type", "").lower()
        is_bounce = (
            "mailer-daemon" in from_header
            or "postmaster@" in from_header
            or "multipart/report" in content_type_header
            or "delivery status notification" in subject_header
            or "undeliverable" in subject_header
        )
        if is_bounce:
            diag = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        p = part.get_payload(decode=True)
                        if p:
                            diag = p.decode("utf-8", errors="replace")[:200]
                            break
            else:
                p = msg.get_payload(decode=True)
                if p:
                    diag = p.decode("utf-8", errors="replace")[:200]
            bounce_type = "hard" if any(s in diag for s in ("5.1.1", "5.1.0", "User unknown")) else "soft"
            bounces.append(BounceInfo(
                type=bounce_type,
                original_to="",
                diagnostic=diag or None,
                original_message_id=message_id,
            ))
            continue

        # Body extraction (charset fallback handling)
        body = ""
        has_attachments = False
        attachment_count = 0
        if msg.is_multipart():
            for part in msg.walk():
                disp = part.get("Content-Disposition", "")
                if "attachment" in disp:
                    has_attachments = True
                    attachment_count += 1
                    continue
                if part.get_content_type() == "text/plain" and not body:
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        try:
                            body = payload.decode(charset, errors="replace")
                        except (LookupError, UnicodeDecodeError):
                            try:
                                from charset_normalizer import from_bytes
                                body = str(from_bytes(payload).best())
                            except Exception:
                                body = payload.decode("utf-8", errors="replace")
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                try:
                    body = payload.decode(charset, errors="replace")
                except (LookupError, UnicodeDecodeError):
                    try:
                        from charset_normalizer import from_bytes
                        body = str(from_bytes(payload).best())
                    except Exception:
                        body = payload.decode("utf-8", errors="replace")

        truncated = len(body) > _MAX_BODY_SIZE
        full_body = body[:_MAX_BODY_SIZE] if truncated else body
        preview = body[:200]

        subject = msg.get("Subject", "")
        aibp_type = parse_aibp_type(subject)

        from_addr = msg.get("From", "")
        date_str = msg.get("Date", "")
        try:
            from email.utils import parsedate_to_datetime
            date = parsedate_to_datetime(date_str)
        except Exception:
            date = datetime.now(timezone.utc)

        email_summary = EmailSummary(
            uid=uid,
            from_address=from_addr,
            subject=subject,
            type=aibp_type,
            message_id=message_id,
            body=full_body,
            body_preview=preview,
            body_truncated=truncated,
            date=date,
            has_attachments=has_attachments,
            attachment_count=attachment_count,
        )
        emails.append(email_summary)
        _add_to_processing(conn, uid, message_id, from_addr)

    remaining = results.get("resultSizeEstimate", 0) - len(emails)
    return InboxResult(data=emails, bounces=bounces, remaining=max(0, remaining))


# ---------------------------------------------------------------------------
# Mark as read
# ---------------------------------------------------------------------------

def _mark_read_imap(config: AibpConfig, uid: str) -> None:
    """Mark email as read via IMAP"""
    from imap_tools import MailBox, AND, MailMessageFlags

    host, port = detect_imap_server(config)
    password = config.aibp_email_password
    if password is None:
        raise RuntimeError("AUTH_PASSWORD_WRONG: AIBP_EMAIL_PASSWORD not configured")

    with MailBox(host, port).login(
        config.aibp_email_address,
        password.get_secret_value(),
    ) as mb:
        mb.flag(uid, (MailMessageFlags.SEEN,), True)


def _mark_read_gmail_api(config: AibpConfig, uid: str) -> None:
    """Mark email as read via Gmail API"""
    from email_auth import get_gmail_service

    service = get_gmail_service(config)
    service.users().messages().modify(
        userId="me",
        id=uid,
        body={"removeLabelIds": ["UNREAD"]},
    ).execute()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def check_unseen(config: AibpConfig) -> dict:
    """Check unread emails and return structured result (filelock for concurrency)"""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with FileLock(str(_PROCESSING_LOCK), timeout=30):
            conn = _ensure_db(config.aibp_data_retention_days)
            try:
                if config.aibp_auth_method == "oauth2_gmail":
                    result = _fetch_unseen_gmail_api(config, conn)
                else:
                    result = _fetch_unseen_imap(config, conn)
                return json.loads(result.model_dump_json())
            finally:
                conn.close()
    except FileLockTimeout:
        error = ErrorResult(
            error_code=ErrorCode.FILELOCK_TIMEOUT,
            error="Another check-unseen is already running, please retry later",
            retryable=True,
            retry_after_seconds=30,
        )
        return json.loads(error.model_dump_json())


def mark_read(config: AibpConfig, uid: str) -> dict:
    """Mark email as read and record as processed"""
    conn = _ensure_db(config.aibp_data_retention_days)
    try:
        # Get message_id + from_address from processing queue
        row = conn.execute(
            "SELECT message_id, from_address FROM processing_queue WHERE uid = ?", (uid,)
        ).fetchone()
        message_id = row[0] if row else f"uid-{uid}@{config.aibp_email_address}"
        from_addr = row[1] if row else ""

        # Mark as read
        if config.aibp_auth_method == "oauth2_gmail":
            _mark_read_gmail_api(config, uid)
        else:
            _mark_read_imap(config, uid)

        # Record as processed
        _mark_processed(conn, uid, message_id, from_addr)
        log.info("marked_read", uid=uid, message_id=message_id)

        result = MarkReadResult(uid=uid)
        return json.loads(result.model_dump_json())
    finally:
        conn.close()


def health_check(config: AibpConfig) -> dict:
    """Check health status of all components"""
    checks: dict[str, HealthCheck] = {}
    overall_healthy = True

    # Check .env configuration
    try:
        _ = config.aibp_email_address
        checks["config"] = HealthCheck(healthy=True)
    except Exception as e:
        checks["config"] = HealthCheck(healthy=False, error=str(e))
        overall_healthy = False

    # Check SQLite
    try:
        t0 = time.time()
        conn = _ensure_db(config.aibp_data_retention_days)
        conn.execute("SELECT 1")
        conn.close()
        checks["sqlite"] = HealthCheck(healthy=True, latency_ms=round((time.time() - t0) * 1000, 1))
    except Exception as e:
        checks["sqlite"] = HealthCheck(healthy=False, error=str(e))
        overall_healthy = False

    # Check IMAP connection
    if config.aibp_auth_method == "password":
        try:
            from imap_tools import MailBox
            host, port = detect_imap_server(config)
            t0 = time.time()
            password = config.aibp_email_password
            if password is None:
                raise RuntimeError("AIBP_EMAIL_PASSWORD not configured")
            with MailBox(host, port).login(
                config.aibp_email_address,
                password.get_secret_value(),
            ):
                pass
            checks["imap"] = HealthCheck(healthy=True, latency_ms=round((time.time() - t0) * 1000, 1))
        except Exception as e:
            checks["imap"] = HealthCheck(healthy=False, error=str(e))
            overall_healthy = False

    # Check SMTP connection
    if config.aibp_auth_method == "password":
        try:
            import smtplib, ssl
            host, port = detect_smtp_server(config)
            ctx = ssl.create_default_context()
            t0 = time.time()
            password = config.aibp_email_password
            if password is None:
                raise RuntimeError("AIBP_EMAIL_PASSWORD not configured")
            if port == 587:
                with smtplib.SMTP(host, port, timeout=10) as s:
                    s.ehlo()
                    s.starttls(context=ctx)
                    s.login(config.aibp_email_address, password.get_secret_value())
            else:
                with smtplib.SMTP_SSL(host, port, context=ctx, timeout=10) as s:
                    s.login(config.aibp_email_address, password.get_secret_value())
            checks["smtp"] = HealthCheck(healthy=True, latency_ms=round((time.time() - t0) * 1000, 1))
        except Exception as e:
            checks["smtp"] = HealthCheck(healthy=False, error=str(e))
            overall_healthy = False

    result = HealthResult(
        status="healthy" if overall_healthy else "degraded",
        checks=checks,
        timestamp=datetime.now(timezone.utc),
    )
    output = json.loads(result.model_dump_json())
    output["version"] = config.aibp_version
    output["tools_version"] = "0.1.0"
    output["python"] = sys.version.split()[0]
    output["auth_method"] = config.aibp_auth_method
    return output


def backup_database() -> dict:
    """Backup SQLite database: data/aibp.db -> data/aibp.db.bak"""
    import shutil
    if not _DB_PATH.exists():
        return {"status": "ok", "message": "No database to backup", "backed_up": False}

    # Disk space check: need at least 2x database size
    db_size = _DB_PATH.stat().st_size
    try:
        free_space = shutil.disk_usage(str(_DATA_DIR)).free
        if free_space < db_size * 2:
            return {
                "status": "error",
                "error_code": ErrorCode.RUNTIME_ERROR,
                "error": f"Insufficient disk space for backup: {free_space // 1024}KB free, need {db_size * 2 // 1024}KB",
            }
    except OSError:
        pass  # disk_usage may fail on some platforms, proceed anyway

    # WAL checkpoint: flush WAL to main file before copying
    try:
        conn = sqlite3.connect(str(_DB_PATH), timeout=5)
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.close()
    except Exception:
        pass  # Best effort — copy even if checkpoint fails

    bak_path = _DB_PATH.with_suffix(".db.bak")
    shutil.copy2(str(_DB_PATH), str(bak_path))

    size_kb = round(bak_path.stat().st_size / 1024, 1)
    log.info("database_backed_up", source=str(_DB_PATH), dest=str(bak_path), size_kb=size_kb)
    return {
        "status": "ok",
        "message": f"Database backed up to {bak_path}",
        "backed_up": True,
        "backup_path": str(bak_path),
        "size_kb": size_kb,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="AIBP inbox tool")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check-unseen", action="store_true", help="Check unread emails")
    group.add_argument("--mark-read", action="store_true", help="Mark email as read")
    group.add_argument("--health", action="store_true", help="Health check")
    group.add_argument("--backup", action="store_true", help="Backup SQLite database")
    group.add_argument("--startup-check", action="store_true", help="Startup self-check (strict: exit 1 if any component unhealthy)")
    parser.add_argument("--uid", type=str, help="Email UID (required for --mark-read)")
    args = parser.parse_args()

    try:
        # --backup does not need .env config
        if args.backup:
            result = backup_database()
            print(json.dumps(result, ensure_ascii=False))
            return 0

        config = load_config()

        if args.startup_check:
            result = health_check(config)
            print(json.dumps(result, ensure_ascii=False))
            if result.get("status") != "healthy":
                log.error("startup_check_failed", checks=result.get("checks", {}))
                return 1
            return 0
        elif args.check_unseen:
            result = check_unseen(config)
        elif args.mark_read:
            if not args.uid:
                error = ErrorResult(
                    error_code=ErrorCode.MISSING_ARGUMENT,
                    error="--mark-read requires --uid parameter",
                )
                print(error.model_dump_json())
                return 2
            result = mark_read(config, args.uid)
        elif args.health:
            result = health_check(config)

        print(json.dumps(result, ensure_ascii=False))
        return 0

    except pybreaker.CircuitBreakerError as cbe:
        backend = "Gmail API" if config.aibp_auth_method == "oauth2_gmail" else "IMAP"
        error = ErrorResult(
            error_code=ErrorCode.CIRCUIT_OPEN,
            error=f"{backend} service temporarily unavailable (circuit open), auto-retry in 60 seconds",
            retryable=True,
            retry_after_seconds=60,
        )
        print(error.model_dump_json())
        log.error("circuit_open", error_code=error.error_code, backend=backend)
        return 1

    except Exception as e:
        error_msg = str(e)
        if "AUTH" in error_msg.upper():
            error_code = ErrorCode.AUTH_PASSWORD_WRONG
            exit_code = 3
        elif "TIMEOUT" in error_msg.upper():
            error_code = ErrorCode.IMAP_CONNECT_TIMEOUT
            exit_code = 1
        elif "CONFIG" in error_msg.upper():
            error_code = ErrorCode.CONFIG_MISSING
            exit_code = 4
        else:
            error_code = ErrorCode.RUNTIME_ERROR
            exit_code = 1

        error = ErrorResult(
            error_code=error_code,
            error=error_msg,
            retryable=error_code in (ErrorCode.IMAP_CONNECT_TIMEOUT,),
        )
        print(error.model_dump_json())
        log.error("inbox_error", error=error_msg, exc_info=True)
        return exit_code


if __name__ == "__main__":
    sys.exit(main())
