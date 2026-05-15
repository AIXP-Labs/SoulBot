"""_config.py — Shared configuration loader for all python_tools

Responsibilities:
- Load config from .env (pydantic-settings auto type validation)
- Provide structlog structured logger (with PII redaction)
- Singleton cache (@lru_cache) to avoid repeated parsing
"""

from __future__ import annotations

import json
import logging
import os
import signal
import stat
import threading
import sys
import warnings
from functools import lru_cache
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import structlog

_TOOLS_DIR = Path(__file__).parent


# ---------------------------------------------------------------------------
# PII redaction structlog processor
# ---------------------------------------------------------------------------

def redact_pii(
    logger: structlog.types.WrappedLogger,
    method_name: str,
    event_dict: structlog.types.EventDict,
) -> structlog.types.EventDict:
    """structlog processor: auto-redact PII (passwords/tokens/body/addresses)"""

    # 1. Never log passwords/tokens
    for key in ("password", "token", "secret", "authorization"):
        if key in event_dict:
            event_dict[key] = "***REDACTED***"

    # 2. Truncate email body (keep first 50 chars)
    if "body" in event_dict:
        body = str(event_dict["body"])
        event_dict["body"] = body[:50] + "..." if len(body) > 50 else body

    # 3. Partially mask email addresses "alice@gmail.com" -> "a***e@gmail.com"
    for addr_key in ("from_address", "to_address", "address"):
        if addr_key in event_dict:
            addr = str(event_dict[addr_key])
            if "@" in addr:
                local, domain = addr.split("@", 1)
                if len(local) > 2:
                    event_dict[addr_key] = f"{local[0]}***{local[-1]}@{domain}"

    return event_dict


# ---------------------------------------------------------------------------
# structlog initialization
# ---------------------------------------------------------------------------

def _configure_structlog() -> None:
    """Configure structlog pipeline: PII redaction -> JSON output to stderr + rotating log file"""
    # Rotating file handler: 10MB x 5 files -> data/aibp.log
    log_dir = _TOOLS_DIR.parent / "data"
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        str(log_dir / "aibp.log"),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter("%(message)s"))

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(logging.Formatter("%(message)s"))

    # Use named logger "aibp" — avoid clearing root logger which affects third-party libraries
    aibp_logger = logging.getLogger("aibp")
    aibp_logger.handlers.clear()
    aibp_logger.setLevel(logging.INFO)
    aibp_logger.addHandler(stderr_handler)
    aibp_logger.addHandler(file_handler)
    aibp_logger.propagate = False  # Don't propagate to root logger

    class _AibpLoggerFactory:
        """Custom factory that always returns the 'aibp' named logger."""
        def __call__(self, *args, **kwargs):
            return aibp_logger

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            redact_pii,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(0),
        context_class=dict,
        logger_factory=_AibpLoggerFactory(),
        cache_logger_on_first_use=True,
    )


_structlog_configured = False


def _ensure_structlog() -> None:
    """Lazy-init structlog (on first get_logger call, avoids overriding global config on import)"""
    global _structlog_configured
    if not _structlog_configured:
        _configure_structlog()
        _structlog_configured = True


# ---------------------------------------------------------------------------
# .env permission check
# ---------------------------------------------------------------------------

def _check_env_permissions() -> None:
    """Check .env file permissions (Unix: 600, not readable by others). Skipped on Windows."""
    env_path = _TOOLS_DIR / ".env"
    if not env_path.exists() or sys.platform == "win32":
        return
    mode = os.stat(env_path).st_mode
    if mode & (stat.S_IRGRP | stat.S_IROTH):
        warnings.warn(
            f".env file permissions too open ({oct(mode)[-3:]}), readable by others. "
            f"Recommended: chmod 600 {env_path}",
            stacklevel=2,
        )


# ---------------------------------------------------------------------------
# Configuration model
# ---------------------------------------------------------------------------

class AibpConfig(BaseSettings):
    """AIBP Bot configuration (auto-loaded from .env, type-validated)"""

    # --- Email account ---
    aibp_email_address: str

    # --- Credential storage ---
    aibp_credential_store: str = "env"  # env | keyring

    # --- Auth method ---
    aibp_auth_method: str = "password"  # password | oauth2_gmail
    aibp_email_password: Optional[SecretStr] = None
    aibp_oauth2_credentials: str = "credentials.json"
    aibp_oauth2_token: str = "token.json"

    # --- Bot identity ---
    aibp_bot_name: str = "AibpBot"
    aibp_operator: str = ""
    aibp_operator_contact: str = ""

    # --- Mail server (manual for private domains, auto-detect for public) ---
    aibp_imap_host: Optional[str] = None
    aibp_imap_port: int = 993
    aibp_smtp_host: Optional[str] = None
    aibp_smtp_port: int = 465

    # --- Watch mode ---
    aibp_watch_mode: str = "poll"  # poll | idle
    aibp_poll_interval: int = 30
    aibp_idle_timeout: int = 900  # 15 min (most servers disconnect at 20 min)

    # --- Send rate limiting ---
    aibp_rate_limit_hour: int = 20
    aibp_rate_limit_day: int = 100

    # --- Trust and social behavior ---
    aibp_introduce_mode: str = "auto_welcome"  # auto_welcome | require_approval | ignore
    aibp_default_trust: str = "T1"
    aibp_max_auto_trust: str = "T2"

    # --- AI disclosure (EU Art.50) ---
    aibp_ai_disclosure: bool = True
    aibp_language: str = "en"  # en | zh

    # --- Data retention (GDPR) ---
    aibp_data_residency: str = "local"
    aibp_data_retention_days: int = 365
    aibp_insight_retention_days: int = 90

    # --- Protocol version ---
    aibp_version: str = "AIBP V1.0.0"

    model_config = SettingsConfigDict(
        env_file=str(_TOOLS_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("aibp_auth_method")
    @classmethod
    def _validate_auth_method(cls, v: str) -> str:
        allowed = {"password", "oauth2_gmail"}
        if v not in allowed:
            raise ValueError(f"aibp_auth_method must be one of {allowed}, got '{v}'")
        return v

    @field_validator("aibp_watch_mode")
    @classmethod
    def _validate_watch_mode(cls, v: str) -> str:
        allowed = {"poll", "idle"}
        if v not in allowed:
            raise ValueError(f"aibp_watch_mode must be one of {allowed}, got '{v}'")
        return v

    @field_validator("aibp_credential_store")
    @classmethod
    def _validate_credential_store(cls, v: str) -> str:
        allowed = {"env", "keyring"}
        if v not in allowed:
            raise ValueError(f"aibp_credential_store must be one of {allowed}, got '{v}'")
        return v


# ---------------------------------------------------------------------------
# Singleton loader
# ---------------------------------------------------------------------------

@lru_cache
def load_config() -> AibpConfig:
    """Load config (singleton cached, .env parsed once per process lifetime)"""
    _check_env_permissions()
    return AibpConfig()


def get_logger(tool_name: str) -> structlog.BoundLogger:
    """Get a structlog logger bound with tool name"""
    _ensure_structlog()
    return structlog.get_logger().bind(tool=tool_name)


# ---------------------------------------------------------------------------
# Graceful shutdown (cross-platform SIGTERM/SIGINT/SIGBREAK)
# ---------------------------------------------------------------------------

_shutdown_event = threading.Event()


def _handle_shutdown_signal(signum: int, frame) -> None:
    """Signal handler: only sets flag, no I/O (safe for signal context)"""
    _shutdown_event.set()


# Register signal handlers (safe on all platforms)
signal.signal(signal.SIGINT, _handle_shutdown_signal)
signal.signal(signal.SIGTERM, _handle_shutdown_signal)
if sys.platform == "win32":
    try:
        signal.signal(signal.SIGBREAK, _handle_shutdown_signal)  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        pass  # SIGBREAK not available on all Windows versions


def is_shutting_down() -> bool:
    """Check if shutdown was requested. Tools should check this in loops."""
    return _shutdown_event.is_set()


# ---------------------------------------------------------------------------
# Server detection (shared by email_send / email_inbox)
# ---------------------------------------------------------------------------

@lru_cache
def _load_server_fallback() -> dict:
    """Load email_config.json server_fallback mapping (cached, read once per process)"""
    config_path = _TOOLS_DIR / "email_config.json"
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            data = json.load(f).get("server_fallback", {})
            return data
    return {}


def _detect_server(config: AibpConfig, protocol: str) -> tuple[str, int]:
    """Unified mail server detection. protocol: 'imap' | 'smtp'

    Priority: .env manual config -> myl-discovery -> email_config.json fallback
    """
    host = getattr(config, f"aibp_{protocol}_host", None)
    port = getattr(config, f"aibp_{protocol}_port")
    if host:
        return host, port

    domain = config.aibp_email_address.split("@")[1].lower()

    try:
        from myl.discovery import discover
        result = discover(domain)
        server = getattr(result, protocol, None) if result else None
        if server:
            return server.host, server.port
    except Exception:
        pass

    fallback = _load_server_fallback()
    if domain in fallback and protocol in fallback[domain]:
        host_port = fallback[domain][protocol].split(":")
        return host_port[0], int(host_port[1])

    raise RuntimeError(
        f"Cannot detect {protocol.upper()} server for {domain}. "
        f"Set AIBP_{protocol.upper()}_HOST and AIBP_{protocol.upper()}_PORT in .env"
    )


def detect_imap_server(config: AibpConfig) -> tuple[str, int]:
    """Detect IMAP server"""
    return _detect_server(config, "imap")


def detect_smtp_server(config: AibpConfig) -> tuple[str, int]:
    """Detect SMTP server"""
    return _detect_server(config, "smtp")


# ---------------------------------------------------------------------------
# AIBP type parsing (shared)
# ---------------------------------------------------------------------------

_VALID_AIBP_TYPES = frozenset({
    # Basic Social (§11): 22 types
    "INTRODUCE", "DISCOVER", "WELCOME", "CHAT", "UPDATE",
    "CONGRATULATE", "SYMPATHY", "ASK", "SHARE", "RECOMMEND",
    "TEACH", "DISCUSS", "DEBATE", "REQUEST", "OFFER",
    "DELEGATE", "COORDINATE", "DELIVER", "FEEDBACK", "THANK",
    "APOLOGIZE", "VOUCH",
    # Boundary (§11.6): 7 types
    "REVIEW", "DECLINE", "BLOCK", "UNBLOCK", "FAREWELL", "PAUSE", "RESUME",
    # Group Communication (§11.7): 4 types
    "INVITE", "ANNOUNCE", "POLL", "NOMINATE",
    # Group Management (§17-18): 4 types
    "CREATE_GROUP", "MEMBERSHIP_CHANGE", "JOIN_REQUEST", "DISSOLVE_GROUP",
    # Commercial (§13): 9 types
    "PROPOSE", "COUNTER", "ACCEPT", "REJECT", "CONTRACT",
    "INVOICE", "RECEIPT", "DISPUTE", "ARBITRATE",
    # AI-Native (§12): 12 types
    "CAPABILITY_SYNC", "VERSION_UPDATE", "KNOWLEDGE_MERGE", "EXPERIENCE_TRANSFER",
    "NEGOTIATE", "VOTE", "HEARTBEAT", "LOAD_SHARE",
    "WARN", "CLONE_REQUEST", "BENCHMARK", "CALIBRATE",
    # Safety: 1 type
    "REPORT",
    # Web Presence (§28): 5 types
    "WEB_POST", "WEB_COMMENT", "WEB_SHARE", "WEB_BOOKMARK", "WEB_REVIEW",
})


def parse_aibp_type(subject: str) -> str | None:
    """Extract AIBP message type from Subject

    "[AIBP/INTRODUCE] Hello" -> "INTRODUCE"
    "[AIBP/HACKED] ..."     -> None (invalid type)
    "Normal email"           -> None
    """
    if "[AIBP/" not in subject:
        return None
    start = subject.index("[AIBP/") + 6
    end = subject.find("]", start)
    if end < 0:
        return None
    raw_type = subject[start:end].upper()
    return raw_type if raw_type in _VALID_AIBP_TYPES else None
