#!/usr/bin/env python3
"""data_erasure.py — GDPR data erasure tool

Usage:
    python data_erasure.py --agent "aibot-alice@gmail.com" --confirm
    python data_erasure.py --agent "aibot-alice@gmail.com" --dry-run

Features:
    - GDPR Art.17 "right to be forgotten" implementation
    - Delete all trust / thread / processed data for a specified agent
    - --dry-run preview mode (no actual deletion)
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from _config import load_config, get_logger
from _schemas import ErrorResult, ErrorCode

log = get_logger("data_erasure")

_TOOLS_DIR = Path(__file__).parent
_DATA_DIR = _TOOLS_DIR.parent / "data"
_DB_PATH = _DATA_DIR / "aibp.db"


# ---------------------------------------------------------------------------
# Business logic
# ---------------------------------------------------------------------------

def erase_agent_data(agent: str, dry_run: bool = False) -> dict:
    """Delete all data for a specified agent

    Args:
        agent: Agent email address
        dry_run: When True, only count without deleting
    """
    if not _DB_PATH.exists():
        return {
            "status": "ok",
            "agent": agent,
            "erased": {"trust_records": 0, "thread_records": 0, "processed_records": 0},
            "message": "Database does not exist, no erasure needed",
        }

    conn = sqlite3.connect(str(_DB_PATH), timeout=5)
    conn.execute("PRAGMA busy_timeout=5000")

    counts = {}

    try:
        # Count records in each table
        # trust table
        trust_count = conn.execute(
            "SELECT COUNT(*) FROM trust WHERE agent_address = ?", (agent,)
        ).fetchone()[0] if _table_exists(conn, "trust") else 0

        # threads table
        thread_count = conn.execute(
            "SELECT COUNT(*) FROM threads WHERE agent_address = ?", (agent,)
        ).fetchone()[0] if _table_exists(conn, "threads") else 0

        # processed_emails table
        processed_count = conn.execute(
            "SELECT COUNT(*) FROM processed_emails WHERE from_address = ?", (agent,)
        ).fetchone()[0] if _table_exists(conn, "processed_emails") else 0

        # processing_queue table
        queue_count = conn.execute(
            "SELECT COUNT(*) FROM processing_queue WHERE from_address = ?", (agent,)
        ).fetchone()[0] if _table_exists(conn, "processing_queue") else 0

        # message_thread_map (linked via threads)
        map_count = 0
        if _table_exists(conn, "message_thread_map") and _table_exists(conn, "threads"):
            thread_ids = conn.execute(
                "SELECT thread_id FROM threads WHERE agent_address = ?", (agent,)
            ).fetchall()
            for (tid,) in thread_ids:
                map_count += conn.execute(
                    "SELECT COUNT(*) FROM message_thread_map WHERE thread_id = ?", (tid,)
                ).fetchone()[0]

        counts = {
            "trust_records": trust_count,
            "thread_records": thread_count,
            "processed_records": processed_count,
            "queue_records": queue_count,
            "thread_map_records": map_count,
        }

        if dry_run:
            return {
                "status": "ok",
                "agent": agent,
                "dry_run": True,
                "would_erase": counts,
                "message": "Dry run mode — no actual deletion",
            }

        # Actual deletion
        # Delete message_thread_map first (depends on threads.thread_id)
        if _table_exists(conn, "message_thread_map") and _table_exists(conn, "threads"):
            thread_ids = conn.execute(
                "SELECT thread_id FROM threads WHERE agent_address = ?", (agent,)
            ).fetchall()
            for (tid,) in thread_ids:
                conn.execute("DELETE FROM message_thread_map WHERE thread_id = ?", (tid,))
        if _table_exists(conn, "trust"):
            conn.execute("DELETE FROM trust WHERE agent_address = ?", (agent,))
        if _table_exists(conn, "threads"):
            conn.execute("DELETE FROM threads WHERE agent_address = ?", (agent,))
        if _table_exists(conn, "processed_emails"):
            conn.execute("DELETE FROM processed_emails WHERE from_address = ?", (agent,))
        if _table_exists(conn, "processing_queue"):
            conn.execute("DELETE FROM processing_queue WHERE from_address = ?", (agent,))

        conn.commit()
        log.info("data_erased", agent=agent, counts=counts)

        return {
            "status": "ok",
            "agent": agent,
            "erased": counts,
            "note": "Addresses in log files require manual review or use --scrub-logs",
        }

    finally:
        conn.close()


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    """Check if table exists"""
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
    ).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="AIBP GDPR data erasure")
    parser.add_argument("--agent", required=True, type=str, help="Agent email address to erase")
    parser.add_argument("--confirm", action="store_true", help="Confirm deletion (required)")
    parser.add_argument("--dry-run", action="store_true", help="Preview mode (no deletion)")
    args = parser.parse_args()

    try:
        if not args.confirm and not args.dry_run:
            error = ErrorResult(
                error_code=ErrorCode.MISSING_ARGUMENT,
                error="--confirm or --dry-run parameter required",
                suggestion="python data_erasure.py --agent <address> --confirm (or --dry-run to preview)",
            )
            print(error.model_dump_json())
            return 2

        result = erase_agent_data(args.agent, dry_run=args.dry_run)
        print(json.dumps(result, ensure_ascii=False))
        return 0

    except Exception as e:
        error = ErrorResult(error_code=ErrorCode.RUNTIME_ERROR, error=str(e))
        print(error.model_dump_json())
        log.error("erasure_error", error=str(e), exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
