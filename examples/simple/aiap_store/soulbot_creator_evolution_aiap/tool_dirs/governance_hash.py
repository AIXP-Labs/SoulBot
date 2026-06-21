#!/usr/bin/env python3
"""
governance_hash.py - Deterministic Governance Hash Compute + TRI-SYNC Write

SOLE AUTHORITY for governance_hash computation and TRI-SYNC writes.
LLM/ReviewFinalize MUST NOT compute or fill governance_hash values directly;
all hash values are produced exclusively by this tool.

Algorithm: canonical v1.0
  1. Enumerate all *.aisop.json files in --program_dir (sorted by filename ASCII).
  2. For each file: parse JSON, apply JCS canonicalization
     (json.dumps(sort_keys=True, separators=(',',':'), ensure_ascii=False)),
     encode as UTF-8 bytes.
  3. Join canonical byte chunks with 0x1E (Record Separator) byte.
  4. Compute sha256(blob).hexdigest() -> 64-char hex string.

TRI-SYNC targets (ATOMIC write + read-back verification):
  - AIAP.md (governance_hash in YAML frontmatter)
  - AIAP_cn.md (if exists, governance_hash in YAML frontmatter)
  - agent_card.json (governance_hash field)
  - quality_baseline.json (top-level governance_hash only; attestation_chain
    advancement is delegated to attestation_advance.py SOLE AUTHORITY — the on-disk
    attestation_chain is a version-keyed DICT, so the list-only update_attestation
    branch below silently no-ops on it and is retained for legacy list-shaped data only)

Pure stdlib: hashlib, json, glob, os, re, sys. No network, no LLM.

Usage:
    python governance_hash.py --program_dir <path>
    python governance_hash.py --program_dir <path> --verify-only

Options:
    --verify-only   Compute hash and verify TRI-SYNC targets without writing.
                    Read-only mode for ValidateStep QUAD-SYNC verification reuse.

Exit codes:
    0 = SUCCESS (hash computed + TRI-SYNC verified)
    1 = FAILURE (read-back mismatch or missing required files)

Output: JSON to stdout with computed hash and verification results.
"""

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path


def enumerate_aisop_files(directory: str) -> list:
    """Enumerate all *.aisop.json files in a directory, sorted by filename ASCII.

    Shared algorithm with snapshot_audit.py enumerate_aisop_files() to ensure
    audit and compute use identical file enumeration.
    """
    aisop_files = []
    for entry in os.listdir(directory):
        if entry.endswith(".aisop.json"):
            aisop_files.append(entry)
    return sorted(aisop_files)


def compute_governance_hash(program_dir: str) -> tuple:
    """Compute governance_hash using canonical v1.0 algorithm.

    Algorithm:
      1. Enumerate *.aisop.json sorted ASCII
      2. JCS canonicalize each: json.dumps(sort_keys=True, separators=(',',':'),
         ensure_ascii=False)
      3. UTF-8 encode each canonical form
      4. Join with 0x1E Record Separator byte
      5. SHA-256 hexdigest

    Args:
        program_dir: Absolute path to the AIAP program directory

    Returns:
        Tuple of (64-char hex string (SHA-256 digest), list of per-file hash dicts)
        Per-file hashes aid debugging hash mismatches in complex multi-module programs.
    """
    aisop_files = enumerate_aisop_files(program_dir)
    if not aisop_files:
        raise ValueError(f"No *.aisop.json files found in {program_dir}")

    canonical_chunks = []
    per_file_hashes = []
    for filename in aisop_files:
        filepath = os.path.join(program_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        # JCS canonicalization
        canonical = json.dumps(
            data, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        chunk = canonical.encode("utf-8")
        canonical_chunks.append(chunk)
        # Per-file SHA-256 for debugging hash mismatches (S4)
        per_file_hashes.append({
            "file": filename,
            "sha256": hashlib.sha256(chunk).hexdigest()
        })

    # Join with 0x1E Record Separator
    blob = b"\x1e".join(canonical_chunks)
    return hashlib.sha256(blob).hexdigest(), per_file_hashes


def update_yaml_frontmatter_hash(filepath: str, new_hash: str) -> bool:
    """Update governance_hash in a YAML frontmatter Markdown file.

    Handles AIAP.md and AIAP_cn.md formats where governance_hash appears
    in the YAML frontmatter block delimited by '---'.

    Returns True if updated successfully, False if governance_hash field not found.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Pattern matches governance_hash field in YAML frontmatter
    # Handles both quoted and unquoted hash values
    # Strictly matches 64 hex chars (SHA-256 digest) for validation (S3)
    pattern = r'(governance_hash:\s*)"?[a-f0-9]{64}"?'
    replacement = rf'\g<1>"{new_hash}"'

    # I3 fail-closed: AIAP.md 历史上在 `summary:` 后带第二个 governance_hash 副本,
    # count=1 把它漏掉(cache/97 line 20 af7c011e 卡 3 轮)。count=0 = 替换所有出现。
    new_content, count = re.subn(pattern, replacement, content, count=0)
    if count == 0:
        # governance_hash field not found; try to add it after governance_mode
        pattern_insert = r'(governance_mode:\s*\S+[^\n]*\n)'
        insert_replacement = rf'\g<1>governance_hash: "{new_hash}"\n'
        new_content, count = re.subn(
            pattern_insert, insert_replacement, content, count=1
        )
        if count == 0:
            return False

    # Atomic write: .tmp then rename
    tmp_path = filepath + ".tmp"
    with open(tmp_path, "w", encoding="utf-8", newline="") as f:
        f.write(new_content)
    os.replace(tmp_path, filepath)
    return True


def update_json_hash(filepath: str, new_hash: str, update_attestation: bool = False) -> bool:
    """Update governance_hash in a JSON file.

    For quality_baseline.json, the legacy LIST-shaped attestation_chain last entry is
    updated if update_attestation=True. NOTE: the on-disk attestation_chain is a
    version-keyed DICT, so this branch silently no-ops on it — attestation_chain
    advancement is delegated to attestation_advance.py (SOLE AUTHORITY). This branch is
    retained only for backward compatibility with legacy list-shaped attestation_chain.

    Returns True if updated successfully.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    data["governance_hash"] = new_hash

    if update_attestation and "attestation_chain" in data:
        chain = data["attestation_chain"]
        if isinstance(chain, list) and len(chain) > 0:
            chain[-1]["governance_hash"] = new_hash

    # Atomic write: .tmp then rename
    tmp_path = filepath + ".tmp"
    with open(tmp_path, "w", encoding="utf-8", newline="") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp_path, filepath)
    return True


def verify_readback(filepath: str, expected_hash: str, is_markdown: bool = False) -> dict:
    """Read back a file and verify the governance_hash matches expected.

    Returns dict with verification result.
    """
    result = {"file": filepath, "status": "PASS", "stored": None}

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        if is_markdown:
            matches = re.findall(r'governance_hash:\s*"?([a-f0-9]{64})"?', content)
            if not matches:
                result["status"] = "FAIL"
                result["error"] = "governance_hash field not found"
                return result
            result["stored"] = matches[0]
            # I3 fail-closed: AIAP.md 所有 governance_hash 副本都必须 = expected;
            # search-first 让 summary 后的 stale 副本静默通过了 3 轮(cache/97)。
            stale = [h for h in matches if h != expected_hash]
            if stale:
                result["status"] = "FAIL"
                result["all_stored"] = matches
                result["error"] = (
                    f"{len(stale)} of {len(matches)} governance_hash copies != expected "
                    f"({expected_hash[:12]}…): " + ", ".join(h[:12] + "…" for h in stale)
                )
                return result
        else:
            data = json.loads(content)
            result["stored"] = data.get("governance_hash")

        if result["stored"] != expected_hash:
            result["status"] = "FAIL"
            result["error"] = f"mismatch: stored={result['stored']}, expected={expected_hash}"
    except Exception as e:
        result["status"] = "FAIL"
        result["error"] = str(e)

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Compute governance_hash (canonical v1.0) and write TRI-SYNC targets"
    )
    parser.add_argument(
        "--program_dir",
        required=True,
        help="Absolute path to the AIAP program directory containing *.aisop.json files",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        default=False,
        help="Compute hash and verify existing TRI-SYNC targets without writing. "
             "Read-only mode for ValidateStep QUAD-SYNC verification reuse.",
    )

    args = parser.parse_args()
    program_dir = os.path.abspath(args.program_dir)
    verify_only = args.verify_only

    report = {
        "status": "SUCCESS",
        "algorithm": "canonical_v1.0",
        "program_dir": program_dir,
        "mode": "verify_only" if verify_only else "compute_and_write",
        "hash": None,
        "files_hashed": [],
        "per_file_hashes": [],
        "tri_sync_targets": [],
        "verification": [],
    }

    # Step 1: Compute hash
    try:
        aisop_files = enumerate_aisop_files(program_dir)
        report["files_hashed"] = aisop_files
        governance_hash, per_file_hashes = compute_governance_hash(program_dir)
        report["hash"] = governance_hash
        report["per_file_hashes"] = per_file_hashes
    except Exception as e:
        report["status"] = "FAILURE"
        report["error"] = f"Hash computation failed: {e}"
        print(json.dumps(report, indent=2, ensure_ascii=False))
        sys.exit(1)

    # Step 2: TRI-SYNC write (or verify-only)
    targets_written = []
    targets_failed = []

    # Define TRI-SYNC target files
    tri_sync_targets = [
        ("AIAP.md", True),
        ("AIAP_cn.md", True),
        ("agent_card.json", False),
        ("quality_baseline.json", False),
    ]

    if verify_only:
        # --verify-only: compute hash and verify existing targets, no writes
        verification_results = []
        all_pass = True
        for target_name, is_md in tri_sync_targets:
            filepath = os.path.join(program_dir, target_name)
            if not os.path.isfile(filepath):
                if target_name == "AIAP_cn.md":
                    continue  # optional target
                continue
            vr = verify_readback(filepath, governance_hash, is_markdown=is_md)
            verification_results.append(vr)
            if vr["status"] != "PASS":
                all_pass = False

        report["verification"] = verification_results
        if not all_pass:
            report["status"] = "FAILURE"

        print(json.dumps(report, indent=2, ensure_ascii=False))
        sys.exit(0 if report["status"] == "SUCCESS" else 1)

    # Normal mode: write + verify
    # Target 1: AIAP.md
    aiap_md = os.path.join(program_dir, "AIAP.md")
    if os.path.isfile(aiap_md):
        if update_yaml_frontmatter_hash(aiap_md, governance_hash):
            targets_written.append("AIAP.md")
        else:
            targets_failed.append({"file": "AIAP.md", "reason": "field not found/insertable"})

    # Target 2: AIAP_cn.md (conditional)
    aiap_cn = os.path.join(program_dir, "AIAP_cn.md")
    if os.path.isfile(aiap_cn):
        if update_yaml_frontmatter_hash(aiap_cn, governance_hash):
            targets_written.append("AIAP_cn.md")
        else:
            targets_failed.append({"file": "AIAP_cn.md", "reason": "field not found/insertable"})

    # Target 3: agent_card.json
    agent_card = os.path.join(program_dir, "agent_card.json")
    if os.path.isfile(agent_card):
        if update_json_hash(agent_card, governance_hash):
            targets_written.append("agent_card.json")
        else:
            targets_failed.append({"file": "agent_card.json", "reason": "update failed"})

    # Target 4: quality_baseline.json (top-level + attestation_chain last entry)
    quality_baseline = os.path.join(program_dir, "quality_baseline.json")
    if os.path.isfile(quality_baseline):
        if update_json_hash(quality_baseline, governance_hash, update_attestation=True):
            targets_written.append("quality_baseline.json")
        else:
            targets_failed.append({"file": "quality_baseline.json", "reason": "update failed"})

    report["tri_sync_targets"] = targets_written

    # Step 3: Read-back verification for ALL written targets
    verification_results = []
    all_pass = True

    for target in targets_written:
        filepath = os.path.join(program_dir, target)
        is_md = target.endswith(".md")
        vr = verify_readback(filepath, governance_hash, is_markdown=is_md)
        verification_results.append(vr)
        if vr["status"] != "PASS":
            all_pass = False

    report["verification"] = verification_results

    if targets_failed:
        report["tri_sync_failures"] = targets_failed
        report["status"] = "FAILURE"
        all_pass = False

    if not all_pass:
        report["status"] = "FAILURE"

    print(json.dumps(report, indent=2, ensure_ascii=False))
    sys.exit(0 if report["status"] == "SUCCESS" else 1)


if __name__ == "__main__":
    main()
