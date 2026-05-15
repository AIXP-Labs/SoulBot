#!/usr/bin/env python3
"""thread_manager.py — Email thread/conversation management

Usage:
    python thread_manager.py --create --agent "aibot-alice@gmail.com" --subject "Hello"
    python thread_manager.py --get --thread-id "abc123"
    python thread_manager.py --add-message --thread-id "abc123" --message-id "<msg@ex.com>"
    python thread_manager.py --list --agent "aibot-alice@gmail.com"

Features:
    - Thread-ID management (UUID)
    - RFC 5322 Message-ID chain maintenance (In-Reply-To / References construction)
    - GDPR consent_record field
    - Thread query by agent
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from _config import load_config, get_logger
from _schemas import ErrorResult, ErrorCode

log = get_logger("thread_manager")

_TOOLS_DIR = Path(__file__).parent
_DATA_DIR = _TOOLS_DIR.parent / "data"
_DB_PATH = _DATA_DIR / "aibp.db"


# ---------------------------------------------------------------------------
# SQLite
# ---------------------------------------------------------------------------

def _ensure_thread_table() -> sqlite3.Connection:
    """Ensure thread table exists"""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), timeout=5)
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS threads (
            thread_id TEXT PRIMARY KEY,
            agent_address TEXT NOT NULL,
            subject TEXT NOT NULL,
            message_id_chain TEXT NOT NULL DEFAULT '[]',
            message_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            consent_status TEXT DEFAULT 'pending',
            status TEXT DEFAULT 'active'
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_threads_agent ON threads(agent_address)")
    # Reverse index: Message-ID -> thread_id (avoid full table scan in find_thread_by_message_id)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS message_thread_map (
            message_id TEXT PRIMARY KEY,
            thread_id TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


# thread_id format validation: UUID or thread_ + 8-32 alphanumeric
_THREAD_ID_PATTERN = re.compile(r"^[a-f0-9\-]{36}$|^thread_[a-zA-Z0-9]{8,32}$")


def _validate_thread_id(thread_id: str) -> bool:
    """Validate thread_id format, prevent path traversal"""
    if not thread_id:
        return False
    # Reject IDs containing path separators
    if "/" in thread_id or "\\" in thread_id or ".." in thread_id:
        return False
    # Check format (UUID or thread_ prefix)
    return bool(_THREAD_ID_PATTERN.match(thread_id))


# ---------------------------------------------------------------------------
# Business logic
# ---------------------------------------------------------------------------

def create_thread(agent: str, subject: str, first_message_id: str = "") -> dict:
    """Create a new thread"""
    thread_id = "thread_" + uuid.uuid4().hex[:12]  # Protocol §10.1: thread_ + 8-32 alphanumeric
    now = datetime.now(timezone.utc).isoformat()
    chain = [first_message_id] if first_message_id else []

    conn = _ensure_thread_table()
    try:
        conn.execute(
            """INSERT INTO threads
               (thread_id, agent_address, subject, message_id_chain, message_count, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (thread_id, agent, subject, json.dumps(chain), len(chain), now, now),
        )
        # Reverse index
        if first_message_id:
            conn.execute(
                "INSERT OR IGNORE INTO message_thread_map (message_id, thread_id) VALUES (?, ?)",
                (first_message_id, thread_id),
            )
        conn.commit()
        log.info("thread_created", thread_id=thread_id, agent=agent)

        return {
            "status": "ok",
            "thread_id": thread_id,
            "agent": agent,
            "subject": subject,
            "message_id_chain": chain,
        }
    finally:
        conn.close()


def get_thread(thread_id: str) -> dict:
    """Get thread details"""
    if not _validate_thread_id(thread_id):
        return {"status": "error", "error_code": ErrorCode.RUNTIME_ERROR, "error": f"Invalid thread_id format: {thread_id}"}
    conn = _ensure_thread_table()
    try:
        row = conn.execute(
            "SELECT thread_id, agent_address, subject, message_id_chain, message_count, created_at, updated_at, consent_status, status FROM threads WHERE thread_id = ?",
            (thread_id,),
        ).fetchone()

        if not row:
            return {
                "status": "error",
                "error_code": ErrorCode.RUNTIME_ERROR,
                "error": f"Thread not found: {thread_id}",
            }

        chain = json.loads(row[3])
        # RFC recommends max 10-20 Message-IDs in References, take last 20
        refs_chain = chain[-20:] if len(chain) > 20 else chain

        # Auto-detect DORMANT: no messages for 7+ days (AIBP S10.2)
        thread_status = row[8]
        if thread_status == "active":
            try:
                updated = datetime.fromisoformat(row[6].replace("+00:00", "+00:00"))
                if datetime.now(timezone.utc) - updated >= timedelta(days=7):
                    thread_status = "dormant"
            except Exception:
                pass

        return {
            "status": "ok",
            "thread_id": row[0],
            "agent": row[1],
            "subject": row[2],
            "message_id_chain": chain,
            "message_count": row[4],
            "created_at": row[5],
            "updated_at": row[6],
            "consent_status": row[7],
            "thread_status": thread_status,
            # RFC 5322 thread headers (for aibp_builder / email_send)
            "in_reply_to": chain[-1] if chain else None,
            "references": " ".join(refs_chain) if refs_chain else None,
        }
    finally:
        conn.close()


def add_message(thread_id: str, message_id: str) -> dict:
    """Add Message-ID to thread (update chain)"""
    if not _validate_thread_id(thread_id):
        return {"status": "error", "error_code": ErrorCode.RUNTIME_ERROR, "error": f"Invalid thread_id format: {thread_id}"}
    conn = _ensure_thread_table()
    try:
        row = conn.execute(
            "SELECT message_id_chain, message_count, status FROM threads WHERE thread_id = ?",
            (thread_id,),
        ).fetchone()

        if not row:
            return {
                "status": "error",
                "error_code": ErrorCode.RUNTIME_ERROR,
                "error": f"Thread not found: {thread_id}",
            }

        chain = json.loads(row[0])
        if message_id not in chain:
            chain.append(message_id)

        now = datetime.now(timezone.utc).isoformat()
        # REOPEN dormant/closed threads on new message (AIBP S10.2)
        current_status = row[2]
        new_status = "active" if current_status in ("dormant", "closed") else current_status
        conn.execute(
            "UPDATE threads SET message_id_chain = ?, message_count = ?, updated_at = ?, status = ? WHERE thread_id = ?",
            (json.dumps(chain), len(chain), now, new_status, thread_id),
        )
        # Reverse index
        conn.execute(
            "INSERT OR IGNORE INTO message_thread_map (message_id, thread_id) VALUES (?, ?)",
            (message_id, thread_id),
        )
        conn.commit()

        return {
            "status": "ok",
            "thread_id": thread_id,
            "message_id": message_id,
            "chain_length": len(chain),
            "in_reply_to": chain[-2] if len(chain) >= 2 else None,
            "references": " ".join(chain[:-1]) if len(chain) >= 2 else None,
        }
    finally:
        conn.close()


def list_threads(agent: str) -> dict:
    """List all threads for an agent"""
    conn = _ensure_thread_table()
    try:
        rows = conn.execute(
            "SELECT thread_id, subject, message_count, updated_at, status FROM threads WHERE agent_address = ? ORDER BY updated_at DESC",
            (agent,),
        ).fetchall()

        threads = [
            {
                "thread_id": r[0],
                "subject": r[1],
                "message_count": r[2],
                "updated_at": r[3],
                "status": r[4],
            }
            for r in rows
        ]
        return {"status": "ok", "agent": agent, "threads": threads, "total": len(threads)}
    finally:
        conn.close()


def close_thread(thread_id: str) -> dict:
    """Close thread (called after FAREWELL)"""
    if not _validate_thread_id(thread_id):
        return {"status": "error", "error_code": ErrorCode.RUNTIME_ERROR, "error": f"Invalid thread_id format: {thread_id}"}
    conn = _ensure_thread_table()
    try:
        row = conn.execute("SELECT status FROM threads WHERE thread_id = ?", (thread_id,)).fetchone()
        if not row:
            return {"status": "error", "error_code": ErrorCode.RUNTIME_ERROR, "error": f"Thread not found: {thread_id}"}

        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE threads SET status = 'closed', updated_at = ? WHERE thread_id = ?",
            (now, thread_id),
        )
        conn.commit()
        log.info("thread_closed", thread_id=thread_id)
        return {"status": "ok", "thread_id": thread_id, "thread_status": "closed"}
    finally:
        conn.close()


def find_thread_by_message_id(message_id: str) -> dict:
    """Find thread by Message-ID (using reverse index, O(1) lookup)"""
    conn = _ensure_thread_table()
    try:
        row = conn.execute(
            "SELECT thread_id FROM message_thread_map WHERE message_id = ?",
            (message_id,),
        ).fetchone()

        if row:
            return {"status": "ok", "thread_id": row[0], "found": True}
        return {"status": "ok", "found": False}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="AIBP thread management")
    parser.add_argument("--create", action="store_true", help="Create new thread")
    parser.add_argument("--get", action="store_true", help="Get thread details")
    parser.add_argument("--add-message", action="store_true", help="Add Message-ID to thread")
    parser.add_argument("--close", action="store_true", help="Close thread")
    parser.add_argument("--list", action="store_true", help="List threads for an agent")
    parser.add_argument("--find", action="store_true", help="Find thread by Message-ID")
    parser.add_argument("--agent", type=str)
    parser.add_argument("--thread-id", type=str)
    parser.add_argument("--message-id", type=str)
    parser.add_argument("--subject", type=str, default="")
    args = parser.parse_args()

    try:
        if args.create:
            if not args.agent:
                error = ErrorResult(error_code=ErrorCode.MISSING_ARGUMENT, error="--create requires --agent")
                print(error.model_dump_json())
                return 2
            result = create_thread(args.agent, args.subject, args.message_id or "")
        elif args.get:
            if not args.thread_id:
                error = ErrorResult(error_code=ErrorCode.MISSING_ARGUMENT, error="--get requires --thread-id")
                print(error.model_dump_json())
                return 2
            result = get_thread(args.thread_id)
        elif args.add_message:
            if not args.thread_id or not args.message_id:
                error = ErrorResult(error_code=ErrorCode.MISSING_ARGUMENT, error="--add-message requires --thread-id and --message-id")
                print(error.model_dump_json())
                return 2
            result = add_message(args.thread_id, args.message_id)
        elif args.close:
            if not args.thread_id:
                error = ErrorResult(error_code=ErrorCode.MISSING_ARGUMENT, error="--close requires --thread-id")
                print(error.model_dump_json())
                return 2
            result = close_thread(args.thread_id)
        elif args.list:
            if not args.agent:
                error = ErrorResult(error_code=ErrorCode.MISSING_ARGUMENT, error="--list requires --agent")
                print(error.model_dump_json())
                return 2
            result = list_threads(args.agent)
        elif args.find:
            if not args.message_id:
                error = ErrorResult(error_code=ErrorCode.MISSING_ARGUMENT, error="--find requires --message-id")
                print(error.model_dump_json())
                return 2
            result = find_thread_by_message_id(args.message_id)
        else:
            error = ErrorResult(error_code=ErrorCode.MISSING_ARGUMENT, error="One of --create / --get / --add-message / --close / --list / --find required")
            print(error.model_dump_json())
            return 2

        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("status") == "ok" else 1

    except Exception as e:
        error = ErrorResult(error_code=ErrorCode.RUNTIME_ERROR, error=str(e))
        print(error.model_dump_json())
        log.error("thread_error", error=str(e), exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
