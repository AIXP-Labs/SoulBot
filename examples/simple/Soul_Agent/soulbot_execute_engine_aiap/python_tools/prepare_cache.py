#!/usr/bin/env python3
"""prepare_cache.py — Cache lifecycle management (creation + cleanup).

Dual-use module:
  - Library: from prepare_cache import prepare_execution_context, cleanup_cache
             Used by agent.py (fast path, in-process Python call, ~5ms)
  - CLI:     python prepare_cache.py --stdin < '{"user_message":"..."}'
             Used by AISOP Engine Router fallback (Bash subprocess, ~300ms)

Library functions:
  - prepare_execution_context(user_message, engine_aiap_dir, cache_num)
      Per-request: append turn + create cache dir + write _index.json.
  - cleanup_cache(engine_aiap_dir, cache_num)
      Startup housekeeping: remove stale cache dirs + trim conversation_context.
      Typically called once by Agent framework at process startup.

Both produce identical cache structure:
  - {engine_aiap_dir}/.execution_cache/conversation_context.json
  - {engine_aiap_dir}/.execution_cache/{turn_id}/_index.json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shutil
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_CACHE_NUM_DEFAULT = 100
# engine_version is read at runtime from main.aisop.json (single source of
# truth — see _resolve_engine_version). This fallback applies ONLY when that
# file is missing/unparseable, so cache creation never hard-fails on lookup.
# Deliberately NOT a version number: a stale hardcoded version silently
# mislabels every _index.json (the root cause of the 5.6.0 drift).
_ENGINE_VERSION_FALLBACK = "unknown"
_CACHE_SCHEMA_VERSION = "1.0"


def _strip_non_natural_language(text: str) -> str:
    """Strip non-natural-language tokens that pollute language detection.

    Removes the following token categories (v5.21.0 B1 fix):
      - File paths: segments containing \\ or / (including drive letters D:\\)
      - snake_case identifiers: words matching [a-z]+(_[a-z0-9]+){2,}
        (e.g. soulbot_creator_evolution_aiap, _detect_user_language)
      - URLs: http:// or https:// followed by non-whitespace
      - Version numbers: patterns like v1.2.3 or 5.20.0
      - Hex hashes: standalone hex strings of 8+ chars (e.g. a306ca0f)

    Returns the remaining text with non-NL tokens replaced by spaces.
    """
    if not text:
        return text

    # Order matters: URLs before paths (URLs contain /)
    # 1. URLs (http:// or https://)
    result = re.sub(r'https?://\S+', ' ', text)
    # 2. File paths: sequences containing \ or / with path-like structure
    #    Matches drive-letter paths (D:\...) and Unix paths (/foo/bar)
    result = re.sub(r'[A-Za-z]:\\[^\s,;，；。、\u3000]*', ' ', result)
    result = re.sub(r'(?<!\w)/(?:[^\s/,;，；。、\u3000]+/)+[^\s,;，；。、\u3000]*', ' ', result)
    # 3. snake_case identifiers (3+ segments: word_word_word)
    result = re.sub(r'\b[a-zA-Z][a-zA-Z0-9]*(?:_[a-zA-Z0-9]+){2,}\b', ' ', result)
    # 4. Version numbers (v1.2.3 or bare 5.20.0)
    result = re.sub(r'\bv?\d+\.\d+\.\d+\b', ' ', result)
    # 5. Hex hashes (standalone 8+ hex chars that contain at least one digit,
    #    not preceded/followed by word chars). The digit requirement prevents
    #    false positives on legitimate alphabetic words that happen to be
    #    hex-valid (e.g. 'abcdefgh'). Q1 quality fix from Research2.
    result = re.sub(r'\b(?=[0-9a-fA-F]{8,}\b)(?=\S*\d)[0-9a-fA-F]{8,}\b', ' ', result)

    return result


def _strip_english_technical_terms(text: str) -> str:
    """Strip English technical terms/identifiers that are NOT natural language.

    v5.23.0 B1: Additional stripping beyond _strip_non_natural_language.
    Removes common English technical terms embedded in CJK-dominant text that
    inflate the ASCII letter count and cause false 'en' detection.

    Strips:
      - camelCase identifiers (e.g. getUserData, EvolveStep, ReviewFinalize)
      - ALL_CAPS identifiers of 3+ chars (e.g. LEVEL_B, WAITING_USER, PASS)
      - Short technical tokens <= 4 ascii-only chars surrounded by CJK/punct
        (e.g. 'en', 'zh', 'py', 'md', 'json')
      - Quoted strings (both single and double quotes)
      - Parenthesized English fragments like (LEVEL_B) or (prepare_cache.py)
    """
    if not text:
        return text
    # camelCase: 2+ segments starting with uppercase after lowercase
    result = re.sub(r'\b[a-z]+(?:[A-Z][a-z0-9]*)+\b', ' ', text)
    # ALL_CAPS with optional underscores (3+ chars, e.g. LEVEL_B, WAITING_USER)
    result = re.sub(r'\b[A-Z][A-Z0-9_]{2,}\b', ' ', result)
    # Quoted strings (single or double)
    result = re.sub(r"'[^']{1,80}'", ' ', result)
    result = re.sub(r'"[^"]{1,80}"', ' ', result)
    # Parenthesized technical fragments (ASCII-only content in parens)
    result = re.sub(r'\([A-Za-z0-9_./ ,;:-]{2,60}\)', ' ', result)
    return result


def _detect_user_language(user_message: str) -> str:
    """Lightweight heuristic language detection from user message text.

    v5.23.0 B1: CJK body presence heuristic (replaces ASCII-vs-CJK ratio).
    After stripping paths/snake_case/URLs/version numbers/hex hashes AND
    English technical terms, if remaining natural language contains sufficient
    CJK ideographic body content, classify as 'zh' (or ja/ko as applicable).
    This fixes the root cause where Chinese instructions mixed with English
    technical terms (e.g. 'LEVEL_B', 'prepare_cache.py', 'WAITING_USER')
    were incorrectly detected as English because the ASCII letter count from
    technical terms dominated the CJK ideograph count.

    v5.21.0 B1: Strips non-natural-language tokens (file paths, snake_case
    identifiers, URLs, version numbers, hex hashes) before counting.

    Detection algorithm (v5.23.0):
      1. Strip non-NL tokens (_strip_non_natural_language).
      2. Strip English technical terms (_strip_english_technical_terms).
      3. Count CJK ideographs in the cleaned text.
      4. If CJK ideograph count >= 5 (absolute threshold for "sufficient
         CJK body content"), classify as CJK language regardless of ASCII
         count. The absolute threshold replaces the ratio-based check that
         was vulnerable to technical term inflation.
      5. Japanese (ja): Hiragana/Katakana > 10% of significant chars.
      6. Korean (ko): Hangul > 10% of significant chars.
      7. Chinese (zh): CJK ideographs present with absolute count >= 5.
         CJK detection covers BMP + Extension A-G + Compatibility Ideographs
         (Q2 quality fix: comprehensive rare CJK character support).
      8. Fallback to ratio: if CJK count < 5 but CJK ratio > 30%, still zh.
      9. Default: "en".

    No external library required — pure stdlib.
    """
    if not user_message:
        return "en"

    # v5.21.0 B1: Strip non-natural-language tokens before character counting
    cleaned = _strip_non_natural_language(user_message)
    # v5.23.0 B1: Additionally strip English technical terms
    cleaned = _strip_english_technical_terms(cleaned)

    cjk_count = 0
    ja_count = 0
    ko_count = 0
    ascii_letter_count = 0
    for ch in cleaned:
        cp = ord(ch)
        if (0x3040 <= cp <= 0x309F) or (0x30A0 <= cp <= 0x30FF):
            # Hiragana or Katakana — uniquely Japanese
            ja_count += 1
        elif 0xAC00 <= cp <= 0xD7AF:
            # Hangul Syllables — uniquely Korean
            ko_count += 1
        elif (0x4E00 <= cp <= 0x9FFF) or (0x3400 <= cp <= 0x4DBF) or (0x20000 <= cp <= 0x2A6DF) or (0x2A700 <= cp <= 0x2B73F) or (0x2B740 <= cp <= 0x2B81F) or (0x2B820 <= cp <= 0x2CEAF) or (0x2CEB0 <= cp <= 0x2EBEF) or (0x30000 <= cp <= 0x3134F) or (0xF900 <= cp <= 0xFAFF):
            # CJK Unified Ideographs (shared by zh/ja/ko)
            # Includes: BMP (U+4E00-9FFF), Ext A (U+3400-4DBF),
            # Ext B (U+20000-2A6DF), Ext C (U+2A700-2B73F),
            # Ext D (U+2B740-2B81F), Ext E (U+2B820-2CEAF),
            # Ext F (U+2CEB0-2EBEF), Ext G (U+30000-3134F),
            # CJK Compatibility Ideographs (U+F900-FAFF).
            # Q2 quality fix from Research2: comprehensive rare CJK coverage.
            cjk_count += 1
        elif ch.isascii() and ch.isalpha():
            ascii_letter_count += 1

    total = cjk_count + ja_count + ko_count + ascii_letter_count
    if total == 0:
        return "en"

    # Japanese: Hiragana/Katakana > 10% is a strong ja signal
    if ja_count / total > 0.10:
        return "ja"
    # Korean: Hangul > 10% is a strong ko signal
    if ko_count / total > 0.10:
        return "ko"
    # v5.23.0 B1: CJK body presence — if enough CJK ideographs exist in
    # the cleaned text (after stripping all technical tokens), the user's
    # natural language intent is CJK regardless of remaining ASCII ratio.
    # Absolute threshold >= 5 CJK chars = sufficient ideographic body.
    if cjk_count >= 5:
        return "zh"
    # Fallback: ratio-based check for edge cases with very short messages
    if total > 0 and cjk_count / total > 0.30:
        return "zh"
    return "en"


# housekeeping thresholds
_TMP_FILE_MAX_AGE_S = 300         # orphan .tmp older than 5 min → delete
_IN_PROGRESS_MAX_AGE_S = 6 * 3600  # in_progress turn older than 6h → mark abandoned

# Cache dir naming: turn_id (digits) + optional suffix letter (a-z for collision)
_CACHE_DIR_RE = re.compile(r'^(\d+)([a-z]?)$')


# ---------------------------------------------------------------------------
# Library API
# ---------------------------------------------------------------------------

def prepare_execution_context(
    user_message: str,
    engine_aiap_dir: Path | str | None = None,
    cache_num: int | None = None,
) -> Optional[dict]:
    """Pre-create cache dir + conversation_context turn before AI starts.

    Runs cleanup_cache first (trim stale state), then creates new turn + cache.
    Equivalent to original agent.py sequence: cleanup() then prepare().

    Args:
        user_message: User's original request.
        engine_aiap_dir: Engine AIAP directory. Defaults to this file's grandparent
            (i.e., soulbot_execute_engine_aiap/).
        cache_num: Max turns to keep in conversation_context. Defaults to env
            CACHE_NUM or 100.

    Returns:
        {turn_id, cache_dir, cache_name, trace_id} on success, None on failure.
    """
    try:
        # Resolve engine_aiap_dir
        if engine_aiap_dir is None:
            engine_aiap_dir = Path(__file__).resolve().parent.parent
        else:
            engine_aiap_dir = Path(engine_aiap_dir).resolve()

        if cache_num is None:
            cache_num = max(1, int(os.getenv("CACHE_NUM", str(_CACHE_NUM_DEFAULT))))

        # Pre-cleanup: trim stale cache dirs + conversation_context turns
        # (non-fatal — prepare continues even if cleanup fails)
        try:
            cleanup_cache(engine_aiap_dir=engine_aiap_dir, cache_num=cache_num)
        except Exception as e:
            logger.warning("cleanup_cache during prepare failed (non-fatal): %s", e)

        cache_root = engine_aiap_dir / ".execution_cache"
        cache_root.mkdir(parents=True, exist_ok=True)

        # 1. Load or init conversation_context
        ctx_file = cache_root / "conversation_context.json"
        ctx = _load_or_init_ctx(ctx_file)

        # 1b. Finalize any prior turns left in 'in_progress' by syncing
        # ai_response + status from their {turn_id}/_index.json.
        _finalize_pending_turns(cache_root, ctx)

        # 1c. REUSE existing in_progress turn (continuation case).
        # If the most recent turn is still in_progress, this user message is a
        # continuation (e.g. responding to a WAITING_USER gate, or a Sub Agent
        # dispatch within the same logical user intent). Reusing the same turn
        # avoids creating empty phantom turns. If the user message is non-empty
        # and the existing turn has no user_message yet, backfill it.
        turns = ctx.get("turns", [])
        if turns and turns[-1].get("status") == "in_progress":
            existing = turns[-1]
            existing_turn_id = existing.get("turn_id")
            if isinstance(existing_turn_id, int):
                existing_dir = _find_cache_dir_for_turn(cache_root, existing_turn_id)
                if existing_dir is not None:
                    if user_message and not existing.get("user_message"):
                        existing["user_message"] = user_message
                        _atomic_write_json(ctx_file, ctx)
                    trace_id = _read_trace_id(existing_dir)
                    return {
                        "turn_id": existing_turn_id,
                        "cache_dir": str(existing_dir),
                        "cache_name": existing_dir.name,
                        "trace_id": trace_id or str(uuid.uuid4()),
                    }
            # If no cache_dir exists for the in_progress turn (corrupted state),
            # fall through to new-turn path defensively.

        # 2. Compute next turn_id
        turn_id = _next_turn_id(turns)

        # 3. Append turn
        new_turn = {
            "turn_id": turn_id,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "turn_type": "user_intent",
            "status": "in_progress",
            "user_message": user_message,
        }
        ctx.setdefault("turns", []).append(new_turn)

        # 4. Trim to max turns
        if len(ctx["turns"]) > cache_num:
            ctx["turns"] = ctx["turns"][-cache_num:]

        # 5. Atomic write conversation_context
        _atomic_write_json(ctx_file, ctx)

        # 6. Create cache dir with suffix collision resolution
        cache_name, cache_dir = _create_cache_dir(cache_root, turn_id)

        # 7. Generate trace_id + detect user language + write _index.json
        trace_id = str(uuid.uuid4())
        user_language = _detect_user_language(user_message)
        index_data = {
            "engine_version": _resolve_engine_version(engine_aiap_dir),
            "user_message": user_message,
            # initial_user_message is write-once: captures the original user
            # message at cache creation time.  Subsequent updates to _index.json
            # (e.g. by execute.step3) MUST NOT overwrite this field.
            "initial_user_message": user_message,
            "status": "in_progress",
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "cache_schema_version": _CACHE_SCHEMA_VERSION,
            "trace_id": trace_id,
            "user_language": user_language,
        }
        _atomic_write_json(cache_dir / "_index.json", index_data)

        # 7b. Persist user_language into conversation_context.json (top-level)
        ctx["user_language"] = user_language
        _atomic_write_json(ctx_file, ctx)

        return {
            "turn_id": turn_id,
            "cache_dir": str(cache_dir),
            "cache_name": cache_name,
            "trace_id": trace_id,
        }

    except Exception as e:
        logger.warning("prepare_execution_context failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# Cleanup API (startup housekeeping)
# ---------------------------------------------------------------------------

def cleanup_cache(
    engine_aiap_dir: Path | str | None = None,
    cache_num: int | None = None,
) -> dict:
    """Cleanup stale cache dirs + trim conversation_context turns.

    Idempotent — safe to call multiple times. Typically called once at
    process startup by Agent framework.

    Deletion strategy:
        - Only numbered cache dirs (e.g. "1", "42", "42a") are subject to deletion.
        - Non-numbered dirs (e.g. "e3e8aac8" legacy hex IDs) are preserved.
        - Keeps the latest `cache_num` numbered dirs, sorted by (int, suffix).

    Args:
        engine_aiap_dir: Engine AIAP directory. Defaults to this file's grandparent.
        cache_num: Max cache dirs + max conversation_context turns to keep.
            Defaults to env CACHE_NUM or 100.

    Returns:
        {deleted_dirs, kept_dirs, trimmed_turns, cache_num}
    """
    if engine_aiap_dir is None:
        engine_aiap_dir = Path(__file__).resolve().parent.parent
    else:
        engine_aiap_dir = Path(engine_aiap_dir).resolve()

    if cache_num is None:
        cache_num = max(1, int(os.getenv("CACHE_NUM", str(_CACHE_NUM_DEFAULT))))

    cache_root = engine_aiap_dir / ".execution_cache"
    cache_root.mkdir(parents=True, exist_ok=True)

    # 1. Scan for numbered cache dirs
    numbered: list[tuple[tuple[int, str], Path]] = []
    for d in cache_root.iterdir():
        if not d.is_dir():
            continue
        m = _CACHE_DIR_RE.match(d.name)
        if m:
            numbered.append(((int(m.group(1)), m.group(2)), d))

    numbered.sort(key=lambda x: x[0])

    deleted_count = 0
    kept_count = len(numbered)

    # 2. Delete excess dirs (keep latest cache_num)
    if len(numbered) > cache_num:
        to_delete = numbered[:len(numbered) - cache_num]
        kept_count = cache_num
        for _key, path in to_delete:
            try:
                shutil.rmtree(path)
                deleted_count += 1
            except OSError as e:
                logger.warning("Failed to delete cache %s: %s", path.name, e)

    # 3. Trim conversation_context.json turns +  abandoned TTL
    trimmed_turns = 0
    abandoned_turns = 0
    ctx_file = cache_root / "conversation_context.json"
    if ctx_file.is_file():
        try:
            ctx = _load_or_init_ctx(ctx_file)
            turns_list = ctx.get("turns")
            if isinstance(turns_list, list):
                # mark long-stuck in_progress turns as abandoned.
                now = datetime.now()
                for turn in turns_list:
                    if turn.get("status") != "in_progress":
                        continue
                    ts = turn.get("timestamp")
                    if not ts:
                        continue
                    try:
                        turn_dt = datetime.fromisoformat(ts)
                    except (ValueError, TypeError):
                        continue
                    age_s = (now - turn_dt).total_seconds()
                    if age_s > _IN_PROGRESS_MAX_AGE_S:
                        turn["status"] = "abandoned"
                        abandoned_turns += 1
                # Existing CACHE_NUM trim
                original_count = len(turns_list)
                if original_count > cache_num:
                    ctx["turns"] = turns_list[-cache_num:]
                    trimmed_turns = original_count - len(ctx["turns"])
                if trimmed_turns > 0 or abandoned_turns > 0:
                    _atomic_write_json(ctx_file, ctx)
        except Exception as e:
            logger.warning("Failed to trim conversation_context: %s", e)

    # 4. sweep orphan .tmp files older than _TMP_FILE_MAX_AGE_S.
    # .tmp files are atomic-write intermediates that should be renamed to .json
    # almost immediately. If they persist, the writer was interrupted (truncation,
    # crash, or Sub Agent timeout). Deleting them prevents disk accumulation and
    # signals "no real data here" to subsequent readers.
    tmp_deleted = 0
    try:
        now_ts = time.time()
        for tmp_path in cache_root.rglob("*.tmp"):
            try:
                if not tmp_path.is_file():
                    continue
                age_s = now_ts - tmp_path.stat().st_mtime
                if age_s > _TMP_FILE_MAX_AGE_S:
                    tmp_path.unlink()
                    tmp_deleted += 1
            except OSError as e:
                logger.debug("Failed to delete orphan tmp %s: %s", tmp_path, e)
    except Exception as e:
        logger.warning("orphan .tmp sweep failed: %s", e)

    # 4b. sweep AI staging files: _tmp_*.json files left by AI when it stages
    # JSON before calling agent_write_node_cache.py. Inline-mode Main Agent
    # tends to do this (observed). agent_write_node_cache.py removes its own
    # node's _tmp_<node>.json post-write, but a fallback path or interrupted
    # call may leave these around. Same TTL as orphan .tmp.
    staging_deleted = 0
    try:
        now_ts = time.time()
        for stg_path in cache_root.rglob("_tmp_*.json"):
            try:
                if not stg_path.is_file():
                    continue
                age_s = now_ts - stg_path.stat().st_mtime
                if age_s > _TMP_FILE_MAX_AGE_S:
                    stg_path.unlink()
                    staging_deleted += 1
            except OSError as e:
                logger.debug("Failed to delete staging file %s: %s", stg_path, e)
    except Exception as e:
        logger.warning("AI staging file sweep failed: %s", e)
    tmp_deleted += staging_deleted

    # 4c. NOTE on 'nul' files: AI on Windows occasionally creates literal
    # files named 'nul' when running '... > nul' (Windows reserved device
    # name treated as filename by git-bash). Python pathlib + os.listdir
    # cannot SEE or DELETE these via stdlib (Win32 reserved-name filtering).
    # Prevention is via AISOP BASH PORTABILITY note ('use >/dev/null').
    # Manual cleanup from git-bash: find . -name nul -type f -delete

    if deleted_count > 0 or trimmed_turns > 0 or abandoned_turns > 0 or tmp_deleted > 0:
        logger.info(
            "cleanup_cache: deleted %d dirs, trimmed %d turns, "
            "abandoned %d stuck turns, swept %d orphan .tmp (kept %d dirs, cache_num=%d)",
            deleted_count, trimmed_turns, abandoned_turns, tmp_deleted, kept_count, cache_num,
        )

    return {
        "deleted_dirs": deleted_count,
        "kept_dirs": kept_count,
        "trimmed_turns": trimmed_turns,
        "abandoned_turns": abandoned_turns,
        "tmp_deleted": tmp_deleted,
        "cache_num": cache_num,
    }


def _find_cache_dir_for_turn(cache_root: Path, turn_id: int) -> Optional[Path]:
    """Return the cache directory for *turn_id*, preferring exact match.

    used by ``prepare_execution_context`` to reuse an
    existing in_progress turn's cache_dir instead of creating a new phantom
    turn when the user response is a continuation (e.g. answering a
    WAITING_USER gate).
    """
    # Exact match first ("66"), then suffixed variants ("66a", "66b"...)
    candidates: list[tuple[str, Path]] = []
    for child in cache_root.iterdir():
        if not child.is_dir():
            continue
        m = _CACHE_DIR_RE.match(child.name)
        if m and int(m.group(1)) == turn_id:
            candidates.append((m.group(2), child))
    if not candidates:
        return None
    # Sort by suffix (empty first, then a/b/c)
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


def _read_trace_id(cache_dir: Path) -> Optional[str]:
    """Read ``trace_id`` from ``{cache_dir}/_index.json``. Return None on failure."""
    idx = cache_dir / "_index.json"
    if not idx.is_file():
        return None
    try:
        with open(idx, encoding="utf-8-sig") as f:
            data = json.load(f)
        tid = data.get("trace_id")
        return tid if isinstance(tid, str) and tid else None
    except (OSError, json.JSONDecodeError):
        return None


def _resolve_engine_version(engine_aiap_dir: Path) -> str:
    """Read the engine version from ``{engine_aiap_dir}/main.aisop.json``.

    main.aisop.json is a list whose first element is the system node; the
    engine version lives at ``[0].content.version`` (single source of truth).
    Falls back to ``_ENGINE_VERSION_FALLBACK`` if the file is missing or
    unparseable, so cache creation never hard-fails on a version lookup.
    """
    try:
        main_file = Path(engine_aiap_dir) / "main.aisop.json"
        with open(main_file, encoding="utf-8-sig") as f:
            data = json.load(f)
        if isinstance(data, list) and data:
            ver = data[0].get("content", {}).get("version")
            if isinstance(ver, str) and ver:
                return ver
    except (OSError, json.JSONDecodeError, AttributeError, TypeError) as e:
        logger.warning("engine version lookup failed, using fallback: %s", e)
    return _ENGINE_VERSION_FALLBACK


# ---------------------------------------------------------------------------
# Helpers (private)
# ---------------------------------------------------------------------------

def _load_or_init_ctx(ctx_file: Path) -> dict:
    """Load conversation_context.json, backup on corruption, init if missing."""
    if not ctx_file.is_file():
        return {"max_turns": 100, "ttl_hours": 24, "turns": []}

    try:
        with open(ctx_file, encoding="utf-8-sig") as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError):
        bak = ctx_file.with_suffix(".json.bak")
        ctx_file.replace(bak)
        logger.warning("conversation_context.json corrupted, backed up to %s", bak)
        return {"max_turns": 100, "ttl_hours": 24, "turns": []}


def _next_turn_id(turns: list) -> int:
    """Compute next turn_id as max existing + 1."""
    max_id = 0
    for t in turns:
        tid = t.get("turn_id", 0)
        if isinstance(tid, int) and tid > max_id:
            max_id = tid
    return max_id + 1


def _finalize_pending_turns(cache_root: Path, ctx: dict) -> None:
    """Lazy reconciliation: sync ai_response + status from each turn's
    _index.json back to conversation_context.json turn entry.

    For every turn still marked ``status == 'in_progress'`` in the context,
    look up its ``{turn_id}/_index.json`` (handling suffixed cache names
    like ``5a``, ``5b``). If the per-turn _index reports ``completed``,
    copy ``ai_response`` and update ``status`` on the context turn entry.
    Missing cache dirs (already trimmed by cache_num cap) are skipped
    silently — those turns stay ``in_progress`` permanently, which is
    acceptable since the cache window is bounded.
    """
    for turn in ctx.get("turns", []):
        if turn.get("status") != "in_progress":
            continue
        turn_id = turn.get("turn_id")
        if turn_id is None:
            continue
        candidates = sorted(
            (c for c in cache_root.iterdir()
             if c.is_dir() and c.name.startswith(str(turn_id))),
            key=lambda p: p.name,
            reverse=True,
        )
        for cand in candidates:
            idx = cand / "_index.json"
            if not idx.exists():
                continue
            try:
                data = json.loads(idx.read_text(encoding="utf-8"))
            except Exception:
                continue
            if data.get("status") == "completed":
                turn["status"] = "completed"
                if "ai_response" in data:
                    turn["ai_response"] = data["ai_response"]
                break


def _create_cache_dir(cache_root: Path, turn_id: int) -> tuple[str, Path]:
    """Create cache dir, resolve naming collision with suffix a/b/c..."""
    cache_name = str(turn_id)
    cache_dir = cache_root / cache_name
    if cache_dir.exists():
        for suffix in "abcdefghijklmnopqrstuvwxyz":
            cache_name = f"{turn_id}{suffix}"
            cache_dir = cache_root / cache_name
            if not cache_dir.exists():
                break
        else:
            raise RuntimeError(f"Cache dir collision exhausted for turn_id={turn_id}")
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_name, cache_dir


def _atomic_write_json(path: Path, data: dict) -> None:
    """Atomic write: .tmp then rename."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pre-create execution context (cache + conversation turn)",
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read JSON params from stdin (mutually exclusive with --payload-file)",
    )
    parser.add_argument(
        "--payload-file",
        type=str,
        default=None,
        help=(
            "Read JSON params from a file path (safer transport for AISOP Engine "
            "Router Bash fallback — avoids shell-echo injection of user_message). "
            "Mutually exclusive with --stdin."
        ),
    )
    parser.add_argument(
        "--engine-dir",
        type=str,
        default=None,
        help="Engine AIAP directory override (optional, auto-detected by default)",
    )
    args = parser.parse_args()

    if args.stdin and args.payload_file:
        print(json.dumps({
            "status": "error",
            "error": "--stdin and --payload-file are mutually exclusive.",
        }))
        return 2

    if not args.stdin and not args.payload_file:
        print(json.dumps({
            "status": "error",
            "error": "one of --stdin or --payload-file is required.",
        }))
        return 2

    try:
        if args.payload_file:
            # SAFE TRANSPORT (I15): read JSON payload from file, not shell-echo.
            # SIZE GUARD: cap at 1MB to match --stdin behavior.
            payload_path = Path(args.payload_file)
            if not payload_path.is_file():
                print(json.dumps({
                    "status": "error",
                    "error": f"--payload-file not found: {args.payload_file}",
                }))
                return 2
            if payload_path.stat().st_size > 1_000_000:
                print(json.dumps({
                    "status": "error",
                    "error": "--payload-file exceeds 1MB limit.",
                }))
                return 2
            with open(payload_path, encoding="utf-8-sig") as f:
                raw = f.read()
        else:
            raw = sys.stdin.read(1_000_000)
        params = json.loads(raw) if raw else {}
    except json.JSONDecodeError as e:
        print(json.dumps({
            "status": "error",
            "error": f"JSON parse failed: {e}",
        }))
        return 2
    except OSError as e:
        print(json.dumps({
            "status": "error",
            "error": f"payload file read failed: {e}",
        }))
        return 2

    user_message = params.get("user_message", "")
    engine_dir = params.get("engine_aiap_dir") or args.engine_dir

    result = prepare_execution_context(user_message, engine_aiap_dir=engine_dir)
    if result is None:
        print(json.dumps({
            "status": "error",
            "error": "preparation failed (see logs)",
        }))
        return 1

    result["status"] = "ok"
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
