"""_schemas.py — Shared Pydantic output models for all python_tools

All tool stdout JSON output must conform to these model definitions,
ensuring AI consumers receive structured, predictable output.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Email summary
# ---------------------------------------------------------------------------

class EmailSummary(BaseModel):
    """Single email summary (email_inbox.py output)"""
    uid: str
    from_address: str
    subject: str
    type: Optional[str] = None          # AIBP message type (after parsing)
    thread_id: Optional[str] = None
    message_id: Optional[str] = None    # RFC 5322 Message-ID
    body: Optional[str] = None          # Full body (50KB truncated, for aibp_parser)
    body_preview: str                   # First 200 chars (for display)
    body_truncated: bool = False
    date: datetime
    has_attachments: bool = False
    attachment_count: int = 0


# ---------------------------------------------------------------------------
# Bounce info
# ---------------------------------------------------------------------------

class BounceInfo(BaseModel):
    """Bounce (NDR) info"""
    type: str                           # "hard" | "soft"
    original_to: str
    status_code: Optional[str] = None   # SMTP status code e.g. "5.1.1"
    diagnostic: Optional[str] = None
    original_message_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Tool output models
# ---------------------------------------------------------------------------

class InboxResult(BaseModel):
    """email_inbox.py --check-unseen output"""
    status: str = "ok"
    data: list[EmailSummary] = []
    bounces: list[BounceInfo] = []
    remaining: int = 0


class SendResult(BaseModel):
    """email_send.py output"""
    status: str = "ok"
    message_id: str                     # Sent email Message-ID


class ValidateResult(BaseModel):
    """email_validate.py output"""
    status: str = "ok"
    address: str
    valid: bool
    is_aibp: bool = False               # Whether follows aibot- prefix
    mx_records: list[str] = []
    suggestion: Optional[str] = None    # Spelling suggestion


class MarkReadResult(BaseModel):
    """email_inbox.py --mark-read output"""
    status: str = "ok"
    uid: str


class HealthCheck(BaseModel):
    """Single health check result"""
    healthy: bool
    latency_ms: Optional[float] = None
    error: Optional[str] = None


class HealthResult(BaseModel):
    """email_inbox.py --health output"""
    status: str = "healthy"
    checks: dict[str, HealthCheck] = {}
    timestamp: datetime


# ---------------------------------------------------------------------------
# Error model
# ---------------------------------------------------------------------------

class ErrorResult(BaseModel):
    """Error output for all tools"""
    status: str = "error"
    error_code: str
    error: str
    retryable: bool = False
    suggestion: Optional[str] = None
    retry_after_seconds: Optional[int] = None


# ---------------------------------------------------------------------------
# Error code constants
# ---------------------------------------------------------------------------

class ErrorCode:
    """Complete error code list (by category)"""

    # --- Auth ---
    AUTH_PASSWORD_WRONG     = "AUTH_PASSWORD_WRONG"
    AUTH_OAUTH_EXPIRED      = "AUTH_OAUTH_EXPIRED"
    AUTH_OAUTH_REVOKED      = "AUTH_OAUTH_REVOKED"
    AUTH_KEYRING_NOT_FOUND  = "AUTH_KEYRING_NOT_FOUND"

    # --- Connection ---
    IMAP_CONNECT_TIMEOUT    = "IMAP_CONNECT_TIMEOUT"
    IMAP_CONNECT_REFUSED    = "IMAP_CONNECT_REFUSED"
    SMTP_CONNECT_TIMEOUT    = "SMTP_CONNECT_TIMEOUT"
    SMTP_CONNECT_REFUSED    = "SMTP_CONNECT_REFUSED"
    DNS_RESOLVE_FAILED      = "DNS_RESOLVE_FAILED"

    # --- Send ---
    SMTP_RATE_LIMITED       = "SMTP_RATE_LIMITED"
    SMTP_RECIPIENT_REJECTED = "SMTP_RECIPIENT_REJECTED"
    SMTP_MESSAGE_TOO_LARGE  = "SMTP_MESSAGE_TOO_LARGE"

    # --- Parse ---
    AIBP_HEADER_MISSING     = "AIBP_HEADER_MISSING"
    AIBP_TYPE_UNKNOWN       = "AIBP_TYPE_UNKNOWN"
    AIBP_BODY_DECODE_FAILED = "AIBP_BODY_DECODE_FAILED"
    EMAIL_INVALID_FORMAT    = "EMAIL_INVALID_FORMAT"

    # --- Storage ---
    SQLITE_LOCKED           = "SQLITE_LOCKED"
    SQLITE_CORRUPT          = "SQLITE_CORRUPT"
    FILELOCK_TIMEOUT        = "FILELOCK_TIMEOUT"

    # --- System ---
    CONFIG_MISSING          = "CONFIG_MISSING"
    CONFIG_INSECURE         = "CONFIG_INSECURE"
    CIRCUIT_OPEN            = "CIRCUIT_OPEN"
    TIMEOUT                 = "TIMEOUT"
    CONTENT_TOO_LARGE       = "CONTENT_TOO_LARGE"
    MISSING_ARGUMENT        = "MISSING_ARGUMENT"
    STDIN_PARSE_ERROR       = "STDIN_PARSE_ERROR"
    RUNTIME_ERROR           = "RUNTIME_ERROR"

    # --- Body validation ---
    BODY_VALIDATION_FAILED    = "BODY_VALIDATION_FAILED"
    BODY_VALIDATION_EXHAUSTED = "BODY_VALIDATION_EXHAUSTED"

    # --- Trust ---
    TRUST_EXCEEDS_MAX_AUTO  = "TRUST_EXCEEDS_MAX_AUTO"

    # --- Bounce ---
    BOUNCE_HARD             = "BOUNCE_HARD"
    BOUNCE_SOFT             = "BOUNCE_SOFT"
