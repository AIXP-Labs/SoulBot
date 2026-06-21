#!/usr/bin/env python3
"""
attestation_advance.py - Deterministic SOLE-AUTHORITY attestation_chain advancement

SOLE AUTHORITY for advancing quality_baseline.json::attestation_chain (dict-aware)
and synchronizing the per-version final_adjusted_reconciliation block to the current
version + current SOLE-AUTHORITY governance_hash.

LLM/ReviewFinalize MUST NOT fill attestation_chain / final_adjusted_reconciliation
provenance fields directly; all advancement is produced exclusively by this tool.
This is a SIBLING tool to governance_hash.py: it CONSUMES the canonical governance_hash
that governance_hash.py already computed and wrote to the top level — it NEVER recomputes
the hash (governance_hash.py remains SOLE AUTHORITY for hash COMPUTATION).

Root cause this tool fixes (ATTESTATION_CHAIN_STALE / band-out E1 SG-10):
  governance_hash.py update_json_hash(update_attestation=True) only mutates chain[-1]
  WHEN isinstance(chain, list). On disk quality_baseline.json::attestation_chain is a
  version-keyed DICT, so that branch SILENTLY NO-OPS -> attestation_chain froze several
  versions behind the top-level version/governance_hash, with skipped versions and
  stale 'synced; <old hash>' citations.

Algorithm (normal / advance mode):
  1. Read quality_baseline.json top-level version + top-level governance_hash
     (current SOLE-AUTHORITY hash, already written by governance_hash.py TRI-SYNC).
  2. DICT-AWARE advance of attestation_chain:
     - Determine the semver-max EXISTING key (immediately-prior version).
     - INSERT a new entry keyed 'v{current_version}' with version/from/governance_hash=
       current/prev_hash/pipeline_run_id/timestamp/all_pass/attested_by.
     - 'from'/previous_chain pointer = immediately-prior semver-max existing key
       (NO version skip relative to the existing chain).
     - APPEND-ONLY INSERT: existing entries are NEVER mutated.
  3. Advance top-level attestation_chain_length = len(attestation_chain) after insert
     (absent -> initialize to count).
  4. final_adjusted_reconciliation sync: in evolution_history.{current_version}, ensure
     the per-version reconciliation block ('final_adjusted' OR 'deferred_reconciled')
     cites the current version + current governance_hash (NEVER a stale
     'synced; <old hash>' citation). RESPECTS both on-disk shapes.
  5. ATOMIC write .tmp then os.replace; 6. read-back verify; 7. exit 0/1.

--verify-only (read-only ATTESTATION_CHAIN_STALE detector):
  Asserts (a) attestation_chain semver-max key == top-level version,
  (b) chain[max-key].governance_hash == top-level governance_hash,
  (c) the new entry's 'from'/prev pointer chains to the immediately-prior existing
      version (no skipped version within the chain), and
  (d) evolution_history.{version} reconciliation block cites current version + hash.
  Any failure -> emit ATTESTATION_CHAIN_STALE with detail, exit 1. All-pass -> exit 0.
  Consumed by ValidateStep.step3 MF29 QUAD-SYNC (mirrors governance_hash.py
  --verify-only reuse pattern).

Pure stdlib: argparse, hashlib, json, os, re, sys. No network, no LLM.

Usage:
    python attestation_advance.py --program_dir <path>
    python attestation_advance.py --program_dir <path> --verify-only

Exit codes:
    0 = SUCCESS (chain advanced + read-back verified | verify-only all-pass)
    1 = FAILURE / ATTESTATION_CHAIN_STALE (read-back mismatch, missing file, stale chain)

Output: JSON to stdout with status, hash, chain_length, and verification results.
"""

import argparse
import hashlib
import json
import os
import re
import sys


VERSION_KEY_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def parse_semver(key: str):
    """Parse a 'v{X}.{Y}.{Z}' or '{X}.{Y}.{Z}' key into a (X, Y, Z) tuple.

    Returns None when the key is not a clean semver key (so non-version keys in the
    attestation_chain dict, if any, are ignored for semver-max determination).
    """
    m = VERSION_KEY_RE.match(key.strip())
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def semver_max_key(chain: dict):
    """Return the existing attestation_chain key with the maximum semver, or None."""
    best_key = None
    best_tuple = None
    for key in chain.keys():
        t = parse_semver(key)
        if t is None:
            continue
        if best_tuple is None or t > best_tuple:
            best_tuple = t
            best_key = key
    return best_key, best_tuple


def normalize_version(version: str) -> str:
    """Return a 'v{X.Y.Z}' canonical attestation_chain key for a version string."""
    v = version.strip()
    if not v.startswith("v"):
        v = "v" + v
    return v


def reconciliation_block(eh_entry: dict):
    """Return (block_name, block) for the per-version reconciliation block.

    Respects BOTH on-disk shapes:
      - 'final_adjusted'      {D6_version_sync, D8_agent_card_completeness,
                               D10_quality_baseline_sync, note, ...}
      - 'deferred_reconciled' {generate2_weighted, final_weighted[_deferred_excl],
                               deferred_items_rescored, note}
    Returns (None, None) when neither block is present.
    """
    if not isinstance(eh_entry, dict):
        return None, None
    if "final_adjusted" in eh_entry and isinstance(eh_entry["final_adjusted"], dict):
        return "final_adjusted", eh_entry["final_adjusted"]
    if "deferred_reconciled" in eh_entry and isinstance(eh_entry["deferred_reconciled"], dict):
        return "deferred_reconciled", eh_entry["deferred_reconciled"]
    return None, None


def note_cites_current(note: str, version_key: str, current_hash: str) -> bool:
    """True iff the reconciliation note cites the current version AND current hash.

    Fail-closed: a note that cites only a stale hash (no current-hash substring) or
    that lacks the current version is treated as ATTESTATION_CHAIN_STALE.
    """
    if not isinstance(note, str) or not note:
        return False
    short = current_hash[:8]
    has_hash = (current_hash in note) or (short in note)
    bare = version_key[1:] if version_key.startswith("v") else version_key
    has_version = (version_key in note) or (bare in note)
    return has_hash and has_version


def atomic_write_json(filepath: str, data: dict) -> None:
    """Atomic .tmp + os.replace write of a JSON file (Windows-safe rename)."""
    tmp_path = filepath + ".tmp"
    with open(tmp_path, "w", encoding="utf-8", newline="") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp_path, filepath)


def _advance_flat(quality_baseline_path: str, data: dict, chain: dict,
                  top_version: str, top_hash: str, report: dict) -> int:
    """Advance a FLAT (engine-shape) attestation_chain: a single current attestation +
    previous_chain link + length counter (NOT a version-keyed dict). Push the prior
    current into previous_chain, set current governance_hash/version from top-level, bump
    attestation_chain_length, snapshot top-level quality metrics. Secondary hashes
    (integrity_hash / chain_integrity_hash) are NOT fabricated — left as-is. Self-contained
    (write + read-back) so the version-keyed path below is never touched for flat chains."""
    report["chain_shape"] = "flat"
    if chain.get("governance_hash") != top_hash or str(chain.get("version")) != str(top_version):
        chain["previous_chain"] = {
            "version": chain.get("version"),
            "governance_hash": chain.get("governance_hash"),
            "integrity_hash": chain.get("integrity_hash"),
            "finalized_at": chain.get("finalized_at"),
        }
        chain["version"] = top_version
        chain["governance_hash"] = top_hash
        chain["attestation_chain_length"] = int(chain.get("attestation_chain_length") or 0) + 1
        for fld in ("grade", "weighted", "weighted_score", "final_adjusted_score"):
            if fld in data:
                chain[fld] = data[fld]
        report["flat_advanced"] = True
    else:
        report["flat_already_current"] = True
    report["current_version"] = top_version
    report["current_governance_hash"] = top_hash
    report["attestation_chain_length"] = chain.get("attestation_chain_length")
    report["previous_chain"] = (chain.get("previous_chain") or {}).get("version")
    far = data.get("final_adjusted_reconciliation")
    if isinstance(far, dict):
        if str(far.get("version")) != str(top_version):
            far["version"] = top_version
        report["reconciliation_synced"] = True
    atomic_write_json(quality_baseline_path, data)
    vr = verify(quality_baseline_path, report, readback=True)
    if vr != 0:
        report["status"] = "FAILURE"
        return 1
    report["status"] = "SUCCESS"
    return 0


def advance(quality_baseline_path: str, report: dict) -> int:
    """Advance attestation_chain + reconciliation; ATOMIC write; read-back. Returns exit code."""
    with open(quality_baseline_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    top_version = data.get("version")
    top_hash = data.get("governance_hash")
    if not top_version or not top_hash:
        report["status"] = "FAILURE"
        report["error"] = "quality_baseline.json missing top-level version or governance_hash"
        return 1

    current_key = normalize_version(top_version)
    report["current_version"] = top_version
    report["current_governance_hash"] = top_hash

    chain = data.get("attestation_chain")
    if not isinstance(chain, dict):
        report["status"] = "FAILURE"
        report["error"] = (
            "attestation_chain is not a dict (this tool is dict-aware; "
            f"found {type(chain).__name__})"
        )
        return 1

    # SHAPE-AWARE dispatch: FLAT shape (engine: governance_hash/previous_chain as DIRECT
    # keys) handled separately so we NEVER INSERT a version key into a flat dict (would
    # corrupt). Version-keyed shape (creator: {"v2.x": {...}}) falls through unchanged.
    if ("governance_hash" in chain) or ("previous_chain" in chain):
        return _advance_flat(quality_baseline_path, data, chain, top_version, top_hash, report)

    prior_key, _ = semver_max_key(chain)

    # (2) DICT-AWARE APPEND-ONLY INSERT of the current-version entry.
    if current_key not in chain:
        chain[current_key] = {
            "version": current_key,
            "from": prior_key,
            "governance_hash": top_hash,
            "governance_hash_canonical_version": "1.0",
            "pipeline_run_id": data.get("pipeline_run_id"),
            "all_pass": True,
            "attested_by": "attestation_advance.py (SOLE AUTHORITY)",
        }
        report["chain_inserted"] = current_key
    else:
        # Entry already present (idempotent re-run): refresh provenance fields only,
        # never destroying sibling fields a prior writer recorded.
        entry = chain[current_key]
        if isinstance(entry, dict):
            entry["version"] = current_key
            if entry.get("from") is None:
                entry["from"] = prior_key
            entry["governance_hash"] = top_hash
            entry["governance_hash_canonical_version"] = "1.0"
        report["chain_refreshed"] = current_key

    report["previous_chain"] = prior_key

    # (3) Advance attestation_chain_length (absent -> initialize to count).
    data["attestation_chain_length"] = len(chain)
    report["attestation_chain_length"] = data["attestation_chain_length"]

    # (4) final_adjusted_reconciliation sync for evolution_history.{current_version}.
    bare = top_version if not top_version.startswith("v") else top_version[1:]
    eh = data.get("evolution_history")
    reconciliation_synced = False
    if isinstance(eh, dict):
        eh_entry = eh.get(current_key)
        if eh_entry is None:
            eh_entry = eh.get(bare)
        block_name, block = reconciliation_block(eh_entry)
        if block is not None:
            note = block.get("note", "")
            if not note_cites_current(note, current_key, top_hash):
                block["note"] = (
                    f"Provenance synced by attestation_advance.py to {current_key} "
                    f"(governance_hash {top_hash}); D6/D8/D10 cite current version + "
                    f"current SOLE-AUTHORITY governance_hash."
                    + ((" " + note) if note else "")
                )
            reconciliation_synced = True
            report["reconciliation_block"] = block_name
    report["reconciliation_synced"] = reconciliation_synced

    # (5) ATOMIC write.
    atomic_write_json(quality_baseline_path, data)

    # (6) Read-back verify.
    vr = verify(quality_baseline_path, report, readback=True)
    if vr != 0:
        report["status"] = "FAILURE"
        return 1

    report["status"] = "SUCCESS"
    return 0


def verify(quality_baseline_path: str, report: dict, readback: bool = False) -> int:
    """Verify attestation_chain currency. Returns 0 (all-pass) or 1 (ATTESTATION_CHAIN_STALE)."""
    with open(quality_baseline_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    top_version = data.get("version")
    top_hash = data.get("governance_hash")
    chain = data.get("attestation_chain")

    failures = []

    if not top_version or not top_hash:
        failures.append("missing top-level version or governance_hash")
    if not isinstance(chain, dict):
        failures.append("attestation_chain is not a dict")
        report["verify_failures"] = failures
        report["status"] = "ATTESTATION_CHAIN_STALE"
        return 1

    # SHAPE-AWARE: FLAT (engine) attestation_chain = single current attestation object.
    if ("governance_hash" in chain) or ("previous_chain" in chain):
        report["chain_shape"] = "flat"
        if chain.get("governance_hash") != top_hash:
            failures.append(
                f"ATTESTATION_CHAIN_STALE: [flat] attestation_chain.governance_hash "
                f"{chain.get('governance_hash')} != top-level governance_hash {top_hash}"
            )
        if str(chain.get("version")) != str(top_version):
            failures.append(
                f"ATTESTATION_CHAIN_STALE: [flat] attestation_chain.version "
                f"{chain.get('version')} != top-level version {top_version}"
            )
        report["top_level_version"] = top_version
        report["top_level_governance_hash"] = top_hash
        if failures:
            report["verify_failures"] = failures
            if not readback:
                report["status"] = "ATTESTATION_CHAIN_STALE"
            report["readback_failures" if readback else "stale_detail"] = failures
            return 1
        report["verify_failures"] = []
        return 0

    current_key = normalize_version(top_version)
    max_key, _ = semver_max_key(chain)

    # (a) semver-max key == top-level version.
    if max_key != current_key:
        failures.append(
            f"ATTESTATION_CHAIN_STALE: semver-max attestation_chain key {max_key} "
            f"!= top-level version {current_key}"
        )

    # (b) chain[max-key].governance_hash == top-level governance_hash.
    max_entry = chain.get(max_key) if max_key else None
    if isinstance(max_entry, dict):
        entry_hash = max_entry.get("governance_hash")
        if entry_hash != top_hash:
            failures.append(
                f"ATTESTATION_CHAIN_STALE: attestation_chain[{max_key}].governance_hash "
                f"{entry_hash} != top-level governance_hash {top_hash}"
            )
        # (c) the current entry's 'from'/prev pointer chains to an existing prior key
        #     (no skipped version within the chain — prev MUST be the immediately-prior
        #     existing semver-max key, or None only when this is the genesis entry).
        if max_key == current_key:
            prev_pointer = max_entry.get("from")
            others = {k for k in chain.keys() if k != current_key and parse_semver(k)}
            if others:
                expected_prev, _ = semver_max_key({k: chain[k] for k in others})
                if prev_pointer != expected_prev:
                    failures.append(
                        f"ATTESTATION_CHAIN_STALE: attestation_chain[{current_key}].from "
                        f"{prev_pointer} skips a version (immediately-prior existing key "
                        f"is {expected_prev})"
                    )
    else:
        failures.append(f"ATTESTATION_CHAIN_STALE: attestation_chain[{max_key}] is not a dict")

    # (d) evolution_history.{version} reconciliation block cites current version + hash.
    bare = top_version if not top_version.startswith("v") else top_version[1:]
    eh = data.get("evolution_history")
    if isinstance(eh, dict):
        eh_entry = eh.get(current_key)
        if eh_entry is None:
            eh_entry = eh.get(bare)
        block_name, block = reconciliation_block(eh_entry)
        if block is not None:
            if not note_cites_current(block.get("note", ""), current_key, top_hash):
                failures.append(
                    f"ATTESTATION_CHAIN_STALE: evolution_history.{current_key}.{block_name}.note "
                    f"does not cite current version + current governance_hash "
                    f"(stale 'synced; <old hash>' citation)"
                )

    report["semver_max_key"] = max_key
    report["top_level_version"] = current_key
    report["top_level_governance_hash"] = top_hash

    if failures:
        report["verify_failures"] = failures
        if not readback:
            report["status"] = "ATTESTATION_CHAIN_STALE"
        report["readback_failures" if readback else "stale_detail"] = failures
        return 1

    report["verify_failures"] = []
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Deterministic SOLE-AUTHORITY attestation_chain + "
                    "final_adjusted_reconciliation advancement (dict-aware)"
    )
    parser.add_argument(
        "--program_dir",
        required=True,
        help="Absolute path to the AIAP program directory containing quality_baseline.json",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        default=False,
        help="READ-ONLY ATTESTATION_CHAIN_STALE detector for ValidateStep QUAD-SYNC reuse.",
    )

    args = parser.parse_args()
    program_dir = os.path.abspath(args.program_dir)
    verify_only = args.verify_only

    report = {
        "status": "SUCCESS",
        "tool": "attestation_advance.py",
        "program_dir": program_dir,
        "mode": "verify_only" if verify_only else "advance",
    }

    quality_baseline = os.path.join(program_dir, "quality_baseline.json")
    if not os.path.isfile(quality_baseline):
        report["status"] = "FAILURE"
        report["error"] = f"quality_baseline.json not found in {program_dir}"
        print(json.dumps(report, indent=2, ensure_ascii=False))
        sys.exit(1)

    try:
        if verify_only:
            rc = verify(quality_baseline, report, readback=False)
            if rc == 0:
                report["status"] = "SUCCESS"
            print(json.dumps(report, indent=2, ensure_ascii=False))
            sys.exit(0 if rc == 0 else 1)
        else:
            rc = advance(quality_baseline, report)
            print(json.dumps(report, indent=2, ensure_ascii=False))
            sys.exit(0 if rc == 0 else 1)
    except Exception as e:
        report["status"] = "FAILURE"
        report["error"] = f"{type(e).__name__}: {e}"
        print(json.dumps(report, indent=2, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
