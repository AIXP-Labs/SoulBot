#!/usr/bin/env python3
"""trust_check.py — T0-T4 trust level management

Usage:
    python trust_check.py --agent "aibot-alice@gmail.com" --required-level T1
    python trust_check.py --agent "aibot-alice@gmail.com" --set-level T2
    python trust_check.py --agent "aibot-alice@gmail.com" --get
    python trust_check.py --list

Trust levels:
    T0 = Unknown (first contact)
    T1 = Introduced (INTRODUCE/WELCOME completed)
    T2 = Active conversation (multiple CHAT interactions)
    T3 = Trusted (operator confirmed)
    T4 = Fully trusted (long-term partner)
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from _config import load_config, get_logger, AibpConfig
from _schemas import ErrorResult, ErrorCode

log = get_logger("trust_check")

_TOOLS_DIR = Path(__file__).parent
_DATA_DIR = _TOOLS_DIR.parent / "data"
_DB_PATH = _DATA_DIR / "aibp.db"

_TRUST_LEVELS = {"T0": 0, "T1": 1, "T2": 2, "T3": 3, "T4": 4}


# ---------------------------------------------------------------------------
# SQLite
# ---------------------------------------------------------------------------

def _ensure_trust_table() -> sqlite3.Connection:
    """Ensure trust table exists"""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), timeout=5)
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trust (
            agent_address TEXT PRIMARY KEY,
            level TEXT NOT NULL DEFAULT 'T0',
            first_seen TEXT NOT NULL,
            last_interaction TEXT NOT NULL,
            interaction_count INTEGER NOT NULL DEFAULT 0,
            consent_status TEXT DEFAULT 'pending',
            notes TEXT DEFAULT ''
        )
    """)
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Business logic
# ---------------------------------------------------------------------------

def check_trust(agent: str, required_level: str) -> dict:
    """Check if agent meets the required trust level"""
    conn = _ensure_trust_table()
    try:
        row = conn.execute(
            "SELECT level, interaction_count, consent_status FROM trust WHERE agent_address = ?",
            (agent,),
        ).fetchone()

        if row is None:
            current = "T0"
            count = 0
            consent = "none"
        else:
            current, count, consent = row[0], row[1], row[2]

        required_val = _TRUST_LEVELS.get(required_level, 0)
        current_val = _TRUST_LEVELS.get(current, 0)

        return {
            "status": "ok",
            "agent": agent,
            "current_level": current,
            "required_level": required_level,
            "allowed": current_val >= required_val,
            "interaction_count": count,
            "consent_status": consent,
        }
    finally:
        conn.close()


def get_trust(agent: str) -> dict:
    """Get full trust info for an agent"""
    conn = _ensure_trust_table()
    try:
        row = conn.execute(
            "SELECT level, first_seen, last_interaction, interaction_count, consent_status, notes FROM trust WHERE agent_address = ?",
            (agent,),
        ).fetchone()

        if row is None:
            return {
                "status": "ok",
                "agent": agent,
                "exists": False,
                "level": "T0",
                "message": "Agent not in trust list",
            }

        return {
            "status": "ok",
            "agent": agent,
            "exists": True,
            "level": row[0],
            "first_seen": row[1],
            "last_interaction": row[2],
            "interaction_count": row[3],
            "consent_status": row[4],
            "notes": row[5],
        }
    finally:
        conn.close()


def set_trust(agent: str, level: str, config: AibpConfig) -> dict:
    """Set agent trust level (with auto trust ceiling check)"""
    if level not in _TRUST_LEVELS:
        return {
            "status": "error",
            "error_code": ErrorCode.RUNTIME_ERROR,
            "error": f"Invalid trust level: {level}, valid values: {list(_TRUST_LEVELS.keys())}",
        }

    # Auto trust ceiling check
    max_auto = _TRUST_LEVELS.get(config.aibp_max_auto_trust, 2)
    level_val = _TRUST_LEVELS[level]
    if level_val > max_auto:
        return {
            "status": "error",
            "error_code": ErrorCode.TRUST_EXCEEDS_MAX_AUTO,
            "error": f"Trust level {level} exceeds auto ceiling {config.aibp_max_auto_trust}, operator confirmation required",
            "suggestion": f"Max auto trust: {config.aibp_max_auto_trust}, higher levels require manual setting",
        }

    now = datetime.now(timezone.utc).isoformat()
    conn = _ensure_trust_table()
    try:
        existing = conn.execute(
            "SELECT level FROM trust WHERE agent_address = ?", (agent,)
        ).fetchone()

        if existing:
            conn.execute(
                "UPDATE trust SET level = ?, last_interaction = ?, interaction_count = interaction_count + 1 WHERE agent_address = ?",
                (level, now, agent),
            )
        else:
            conn.execute(
                "INSERT INTO trust (agent_address, level, first_seen, last_interaction, interaction_count) VALUES (?, ?, ?, ?, 1)",
                (agent, level, now, now),
            )
        conn.commit()

        log.info("trust_updated", agent=agent, level=level)
        return {
            "status": "ok",
            "agent": agent,
            "level": level,
            "previous_level": existing[0] if existing else None,
            "message": f"Trust level {'updated' if existing else 'created'} to {level}",
        }
    finally:
        conn.close()


def list_agents() -> dict:
    """List all known agents"""
    conn = _ensure_trust_table()
    try:
        rows = conn.execute(
            "SELECT agent_address, level, last_interaction, interaction_count FROM trust ORDER BY last_interaction DESC"
        ).fetchall()

        agents = [
            {
                "agent": r[0],
                "level": r[1],
                "last_interaction": r[2],
                "interaction_count": r[3],
            }
            for r in rows
        ]
        return {"status": "ok", "agents": agents, "total": len(agents)}
    finally:
        conn.close()


def record_interaction(agent: str) -> dict:
    """Record an interaction (update last_interaction + interaction_count)"""
    now = datetime.now(timezone.utc).isoformat()
    conn = _ensure_trust_table()
    try:
        existing = conn.execute(
            "SELECT level FROM trust WHERE agent_address = ?", (agent,)
        ).fetchone()

        if existing:
            conn.execute(
                "UPDATE trust SET last_interaction = ?, interaction_count = interaction_count + 1 WHERE agent_address = ?",
                (now, agent),
            )
        else:
            conn.execute(
                "INSERT INTO trust (agent_address, level, first_seen, last_interaction, interaction_count) VALUES (?, 'T0', ?, ?, 1)",
                (agent, now, now),
            )
        conn.commit()
        return {"status": "ok", "agent": agent}
    finally:
        conn.close()


def block_agent(agent: str) -> dict:
    """BLOCK message handling — immediately demote to T0 (Doc 04 S9.2 trust demotion trigger)"""
    now = datetime.now(timezone.utc).isoformat()
    conn = _ensure_trust_table()
    try:
        existing = conn.execute(
            "SELECT level FROM trust WHERE agent_address = ?", (agent,)
        ).fetchone()
        previous = existing[0] if existing else "T0"

        if existing:
            conn.execute(
                "UPDATE trust SET level = 'T0', last_interaction = ?, notes = ? WHERE agent_address = ?",
                (now, f"BLOCKED at {now} (was {previous})", agent),
            )
        else:
            conn.execute(
                "INSERT INTO trust (agent_address, level, first_seen, last_interaction, interaction_count, notes) VALUES (?, 'T0', ?, ?, 0, ?)",
                (agent, now, now, f"BLOCKED at {now}"),
            )
        conn.commit()
        log.warning("agent_blocked", agent=agent, previous_level=previous)
        return {
            "status": "ok",
            "agent": agent,
            "level": "T0",
            "previous_level": previous,
            "message": f"Agent demoted to T0 (was {previous})",
        }
    finally:
        conn.close()


def decay_inactive(days: int = 30) -> dict:
    """Trust decay — demote agents with no interaction for N days by one level (AIBP S14)

    T4->T3, T3->T2, T2->T1, T1->T1 (T1 is the lowest active level, no further demotion), T0 unchanged
    """
    conn = _ensure_trust_table()
    try:
        now_str = datetime.now(timezone.utc).isoformat()
        rows = conn.execute(
            """SELECT agent_address, level, last_interaction FROM trust
               WHERE level NOT IN ('T0', 'T1')
               AND last_interaction < datetime('now', ? || ' days')""",
            (f"-{days}",),
        ).fetchall()

        decayed = []
        for agent_addr, current_level, last_interaction in rows:
            current_val = _TRUST_LEVELS.get(current_level, 0)
            new_val = max(1, current_val - 1)  # Minimum demotion to T1
            new_level = f"T{new_val}"
            conn.execute(
                "UPDATE trust SET level = ?, notes = ? WHERE agent_address = ?",
                (new_level, f"Decayed from {current_level} at {now_str} (inactive {days}d)", agent_addr),
            )
            decayed.append({"agent": agent_addr, "from": current_level, "to": new_level})
            log.info("trust_decayed", agent=agent_addr, from_level=current_level, to_level=new_level)

        conn.commit()
        return {"status": "ok", "decayed": decayed, "total": len(decayed)}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="AIBP trust level management")
    parser.add_argument("--agent", type=str, help="Agent email address")
    parser.add_argument("--required-level", type=str, help="Check if agent meets this level")
    parser.add_argument("--set-level", type=str, help="Set trust level")
    parser.add_argument("--get", action="store_true", help="Get trust info")
    parser.add_argument("--record", action="store_true", help="Record an interaction")
    parser.add_argument("--block", action="store_true", help="BLOCK — demote to T0")
    parser.add_argument("--decay", action="store_true", help="Decay inactive agent trust")
    parser.add_argument("--decay-days", type=int, default=30, help="Decay threshold in days (default 30, per AIBP S14)")
    parser.add_argument("--list", action="store_true", help="List all agents")
    args = parser.parse_args()

    try:
        config = load_config()

        if args.list:
            result = list_agents()
        elif args.decay:
            result = decay_inactive(args.decay_days)
        elif not args.agent:
            error = ErrorResult(
                error_code=ErrorCode.MISSING_ARGUMENT,
                error="--agent parameter required",
            )
            print(error.model_dump_json())
            return 2
        elif args.required_level:
            result = check_trust(args.agent, args.required_level)
        elif args.set_level:
            result = set_trust(args.agent, args.set_level, config)
        elif args.get:
            result = get_trust(args.agent)
        elif args.record:
            result = record_interaction(args.agent)
        elif args.block:
            result = block_agent(args.agent)
        else:
            error = ErrorResult(
                error_code=ErrorCode.MISSING_ARGUMENT,
                error="One of --required-level / --set-level / --get / --block / --decay / --list required",
            )
            print(error.model_dump_json())
            return 2

        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("status") == "ok" else 1

    except Exception as e:
        error = ErrorResult(error_code=ErrorCode.RUNTIME_ERROR, error=str(e))
        print(error.model_dump_json())
        log.error("trust_error", error=str(e), exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
