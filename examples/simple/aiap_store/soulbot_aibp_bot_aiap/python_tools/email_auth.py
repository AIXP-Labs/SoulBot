#!/usr/bin/env python3
"""email_auth.py — Gmail OAuth2 authentication

Usage:
    python email_auth.py --init       # First-time authorization (opens browser)
    python email_auth.py --status     # Check token status
    python email_auth.py --revoke     # Revoke token + delete token.json

Features:
    - PKCE flow (google-auth-oauthlib default support)
    - Minimal scopes: gmail.send + gmail.readonly
    - Auto token refresh (proactive refresh 60 seconds before expiry)
    - credentials.json + token.json management
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from _config import load_config, get_logger, AibpConfig
from _schemas import ErrorResult, ErrorCode

log = get_logger("email_auth")

_TOOLS_DIR = Path(__file__).parent

# Gmail API Scope — minimal permissions
# gmail.send: send emails
# gmail.readonly: read emails (no modification)
_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
]


# ---------------------------------------------------------------------------
# Token management
# ---------------------------------------------------------------------------

def _credentials_path(config: AibpConfig) -> Path:
    """OAuth2 client credentials file path (downloaded from Google Cloud)"""
    return _TOOLS_DIR / config.aibp_oauth2_credentials


def _token_path(config: AibpConfig) -> Path:
    """OAuth2 token file path (auto-generated)"""
    return _TOOLS_DIR / config.aibp_oauth2_token


def _load_token(config: AibpConfig):
    """Load existing token (if it exists and is parseable)"""
    from google.oauth2.credentials import Credentials

    token_file = _token_path(config)
    if not token_file.exists():
        return None

    try:
        creds = Credentials.from_authorized_user_file(str(token_file), _SCOPES)
        return creds
    except (ValueError, KeyError, Exception) as e:
        log.warning("token_load_failed", path=str(token_file), error=str(e))
        return None


def _save_token(config: AibpConfig, creds) -> None:
    """Save token to file (Unix: permission 600, owner read/write only)"""
    token_file = _token_path(config)
    token_file.write_text(creds.to_json(), encoding="utf-8")
    if sys.platform != "win32":
        token_file.chmod(0o600)
    log.info("token_saved", path=str(token_file))


def _make_aware_utc(dt: datetime) -> datetime:
    """Ensure datetime is UTC aware (naive -> attach UTC, aware -> convert to UTC)"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _refresh_if_needed(config: AibpConfig, creds):
    """Proactively refresh if token is expired or expiring soon (within 60 seconds)"""
    from google.auth.transport.requests import Request

    if creds and creds.expired and creds.refresh_token:
        log.info("token_refreshing", reason="expired")
        creds.refresh(Request())
        _save_token(config, creds)
        return creds

    if creds and creds.valid:
        # Check if expiring soon (within 60 seconds)
        if creds.expiry:
            remaining = (_make_aware_utc(creds.expiry) - datetime.now(timezone.utc)).total_seconds()
            if remaining < 60 and creds.refresh_token:
                log.info("token_refreshing", reason="expiring_soon", remaining_seconds=remaining)
                creds.refresh(Request())
                _save_token(config, creds)
        return creds

    return creds


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_gmail_service(config: AibpConfig):
    """Get authenticated Gmail API service object

    Automatically handles:
    1. Load token.json
    2. Refresh expired token (or expiring within 60 seconds)
    3. Token missing or unable to refresh -> prompt user to run --init

    Returns:
        googleapiclient.discovery.Resource — Gmail API service
    """
    from googleapiclient.discovery import build

    creds = _load_token(config)

    if not creds:
        raise RuntimeError(
            "AUTH_OAUTH_EXPIRED: Gmail OAuth2 token does not exist. "
            "Please run: python python_tools/email_auth.py --init"
        )

    if creds.expired or not creds.valid:
        if creds.refresh_token:
            creds = _refresh_if_needed(config, creds)
        else:
            raise RuntimeError(
                "AUTH_OAUTH_EXPIRED: Gmail OAuth2 token has expired with no refresh_token. "
                "Please run: python python_tools/email_auth.py --init"
            )
    else:
        # valid but may be expiring soon (within 60 seconds)
        creds = _refresh_if_needed(config, creds)

    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    log.info("gmail_service_ready")
    return service


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def init_auth(config: AibpConfig) -> dict:
    """First-time OAuth2 authorization (opens browser)"""
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds_file = _credentials_path(config)
    if not creds_file.exists():
        return {
            "status": "error",
            "error_code": ErrorCode.CONFIG_MISSING,
            "error": f"OAuth2 credentials file not found: {creds_file}",
            "suggestion": (
                "1. Go to Google Cloud Console -> APIs & Services -> Credentials\n"
                "2. Create OAuth 2.0 Client ID (Desktop app)\n"
                "3. Download JSON and place in python_tools/credentials.json"
            ),
        }

    flow = InstalledAppFlow.from_client_secrets_file(str(creds_file), _SCOPES)
    creds = flow.run_local_server(port=0)

    _save_token(config, creds)

    return {
        "status": "ok",
        "message": "Gmail OAuth2 authorization successful",
        "token_path": str(_token_path(config)),
        "scopes": _SCOPES,
        "expiry": creds.expiry.isoformat() if creds.expiry else None,
    }


def check_status(config: AibpConfig) -> dict:
    """Check token status"""
    creds = _load_token(config)

    if creds is None:
        return {
            "status": "error",
            "error_code": ErrorCode.AUTH_OAUTH_EXPIRED,
            "error": "token.json does not exist",
            "suggestion": "Run: python email_auth.py --init",
        }

    if creds.expired:
        if creds.refresh_token:
            return {
                "status": "ok",
                "state": "expired_refreshable",
                "message": "Token expired but can be auto-refreshed",
                "expiry": creds.expiry.isoformat() if creds.expiry else None,
            }
        return {
            "status": "error",
            "error_code": ErrorCode.AUTH_OAUTH_EXPIRED,
            "error": "Token expired with no refresh_token",
            "suggestion": "Run: python email_auth.py --init to re-authorize",
        }

    # Scope check: ensure token has required permissions
    if creds.scopes and not set(_SCOPES).issubset(creds.scopes):
        return {
            "status": "error",
            "error_code": ErrorCode.AUTH_OAUTH_EXPIRED,
            "error": f"Token scope insufficient. Required: {_SCOPES}, actual: {list(creds.scopes)}",
            "suggestion": "Run: python email_auth.py --init to re-authorize (obtain full permissions)",
        }

    remaining = None
    if creds.expiry:
        remaining = int((_make_aware_utc(creds.expiry) - datetime.now(timezone.utc)).total_seconds())

    return {
        "status": "ok",
        "state": "valid",
        "message": "Token valid",
        "expiry": creds.expiry.isoformat() if creds.expiry else None,
        "remaining_seconds": remaining,
        "scopes": list(creds.scopes) if creds.scopes else _SCOPES,
    }


def revoke_auth(config: AibpConfig) -> dict:
    """Revoke token and delete token.json"""
    import urllib.request
    import urllib.parse
    import urllib.error

    creds = _load_token(config)
    token_file = _token_path(config)

    revoked = False
    if creds and creds.token:
        try:
            data = urllib.parse.urlencode({"token": creds.token}).encode("ascii")
            req = urllib.request.Request(
                "https://oauth2.googleapis.com/revoke",
                data=data,
                method="POST",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                revoked = resp.status == 200
            if revoked:
                log.info("token_revoked")
            else:
                log.warning("revoke_failed")
        except urllib.error.HTTPError as e:
            log.warning("revoke_failed", status_code=e.code)
        except Exception as e:
            log.warning("revoke_request_failed", error=str(e))

    # Delete local token file
    deleted = False
    if token_file.exists():
        token_file.unlink()
        deleted = True
        log.info("token_file_deleted", path=str(token_file))

    return {
        "status": "ok",
        "revoked": revoked,
        "file_deleted": deleted,
        "message": "OAuth2 token revoked" if revoked else "Local token deleted (remote revocation may have failed)",
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="AIBP Gmail OAuth2 authentication tool")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--init", action="store_true", help="First-time authorization (opens browser)")
    group.add_argument("--status", action="store_true", help="Check token status")
    group.add_argument("--revoke", action="store_true", help="Revoke token")
    args = parser.parse_args()

    try:
        config = load_config()

        if config.aibp_auth_method != "oauth2_gmail":
            error = ErrorResult(
                error_code=ErrorCode.CONFIG_MISSING,
                error=f"Current auth method is '{config.aibp_auth_method}', not oauth2_gmail",
                suggestion="Set AIBP_AUTH_METHOD=oauth2_gmail in .env",
            )
            print(error.model_dump_json())
            return 4

        if args.init:
            result = init_auth(config)
        elif args.status:
            result = check_status(config)
        elif args.revoke:
            result = revoke_auth(config)

        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("status") == "ok" else 1

    except Exception as e:
        error = ErrorResult(
            error_code=ErrorCode.RUNTIME_ERROR,
            error=str(e),
        )
        print(error.model_dump_json())
        log.error("auth_error", error=str(e), exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
