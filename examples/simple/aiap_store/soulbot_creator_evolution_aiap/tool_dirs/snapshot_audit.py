#!/usr/bin/env python3
"""
snapshot_audit.py - Version Snapshot Integrity Auditor

READ-ONLY tool that verifies the completeness and integrity of a version
snapshot directory against the source AIAP directory. Never writes or
modifies any file.

Usage:
    python snapshot_audit.py --snapshot_dir <path> --version <semver> --aiap_dir <path>

Exit codes:
    0 = PASS (all checks passed)
    1 = FAIL (one or more checks failed)

Output: JSON report to stdout with audit results.
"""

import argparse
import datetime
import hashlib
import json
import os
import sys
from pathlib import Path


# Hard-coded snapshot manifest - source of truth for expected files
# Matches SNAPSHOT_MANIFEST in review.aisop.json Finalize.step2
SNAPSHOT_MANIFEST_FIXED = [
    "AIAP.md",
    "agent_card.json",
    "quality_baseline.json",
    "meta.json",
]

# These files are included only if they exist in the source AIAP directory
SNAPSHOT_MANIFEST_CONDITIONAL = [
    "AIAP_cn.md",
    "protocol_config.json",
]

# meta.json canonical fields per STANDARD.version_snapshot_schema.meta_schema
META_REQUIRED_FIELDS = [
    "version",
    "created_at",
    "source_version",
    "files",
    "file_count",
    "governance_hash",
    "pipeline_run_id",
]


def compute_sha256(file_path: str) -> str:
    """Compute SHA-256 hex digest of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def enumerate_aisop_files(directory: str) -> list:
    """Enumerate all *.aisop.json files in a directory, sorted by filename."""
    aisop_files = []
    for entry in os.listdir(directory):
        if entry.endswith(".aisop.json"):
            aisop_files.append(entry)
    return sorted(aisop_files)


def audit_snapshot(snapshot_dir: str, version: str, aiap_dir: str) -> dict:
    """
    Audit a version snapshot directory for completeness and integrity.

    Args:
        snapshot_dir: Path to the snapshot directory (.version_history/{version}/)
        version: Expected semver version string
        aiap_dir: Path to the source AIAP directory

    Returns:
        dict: Audit report with status, findings, and details
    """
    report = {
        "status": "PASS",
        "version": version,
        "files_expected": 0,
        "files_found": 0,
        "missing": [],
        "extra": [],
        "hash_mismatches": [],
        "meta_valid": False,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    # Build expected file list
    expected_files = set()

    # 1. All *.aisop.json files from the AIAP directory
    aiap_aisop_files = enumerate_aisop_files(aiap_dir)
    for f in aiap_aisop_files:
        expected_files.add(f)

    # 2. Fixed manifest files
    for f in SNAPSHOT_MANIFEST_FIXED:
        expected_files.add(f)

    # 3. Conditional manifest files (only if they exist in source)
    for f in SNAPSHOT_MANIFEST_CONDITIONAL:
        source_path = os.path.join(aiap_dir, f)
        if os.path.isfile(source_path):
            expected_files.add(f)

    report["files_expected"] = len(expected_files)

    # Enumerate actual files in snapshot directory
    if not os.path.isdir(snapshot_dir):
        report["status"] = "FAIL"
        report["missing"] = list(expected_files)
        report["files_found"] = 0
        return report

    actual_files = set()
    for entry in os.listdir(snapshot_dir):
        if os.path.isfile(os.path.join(snapshot_dir, entry)):
            actual_files.add(entry)

    report["files_found"] = len(actual_files)

    # Check for missing files
    missing = expected_files - actual_files
    if missing:
        report["missing"] = sorted(list(missing))
        report["status"] = "FAIL"

    # Check for extra/unexpected files
    extra = actual_files - expected_files
    if extra:
        report["extra"] = sorted(list(extra))
        # Extra files are a warning but do not fail the audit

    # Verify SHA-256 hashes of snapshot files against originals
    # (meta.json is generated, not copied, so skip hash comparison for it)
    files_to_hash_check = expected_files - {"meta.json"}
    for filename in sorted(files_to_hash_check):
        snapshot_path = os.path.join(snapshot_dir, filename)
        source_path = os.path.join(aiap_dir, filename)

        if not os.path.isfile(snapshot_path):
            continue  # Already captured in missing
        if not os.path.isfile(source_path):
            continue  # Conditional file not in source

        snapshot_hash = compute_sha256(snapshot_path)
        source_hash = compute_sha256(source_path)

        if snapshot_hash != source_hash:
            report["hash_mismatches"].append({
                "file": filename,
                "snapshot_hash": snapshot_hash,
                "source_hash": source_hash,
            })
            report["status"] = "FAIL"

    # Verify meta.json exists and has required canonical fields
    meta_path = os.path.join(snapshot_dir, "meta.json")
    if os.path.isfile(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)

            # Check all required fields are present
            missing_fields = [
                field for field in META_REQUIRED_FIELDS if field not in meta
            ]

            if missing_fields:
                report["meta_valid"] = False
                report["meta_missing_fields"] = missing_fields
                report["status"] = "FAIL"
            else:
                # Validate field types
                type_errors = []
                if not isinstance(meta.get("version"), str):
                    type_errors.append("version must be string")
                if not isinstance(meta.get("created_at"), str):
                    type_errors.append("created_at must be string")
                if not isinstance(meta.get("source_version"), str):
                    type_errors.append("source_version must be string")
                if not isinstance(meta.get("files"), list):
                    type_errors.append("files must be array")
                if not isinstance(meta.get("file_count"), int):
                    type_errors.append("file_count must be integer")
                if not isinstance(meta.get("governance_hash"), str):
                    type_errors.append("governance_hash must be string")
                if not isinstance(meta.get("pipeline_run_id"), str):
                    type_errors.append("pipeline_run_id must be string")

                if type_errors:
                    report["meta_valid"] = False
                    report["meta_type_errors"] = type_errors
                    report["status"] = "FAIL"
                else:
                    report["meta_valid"] = True

                # P2 FIX: reject placeholder / agent-fabricated created_at.
                # This tool is READ-ONLY and cannot WRITE the timestamp, so the
                # contract "created_at MUST be Python-computed" can only be
                # ENFORCED here by rejecting obvious fakes. The agent placeholder
                # signature is midnight-exact (00:00:00) — a real finalize time
                # is virtually never exactly midnight to microsecond precision.
                created_at = meta.get("created_at")
                if isinstance(created_at, str):
                    ca_error = None
                    try:
                        dt = datetime.datetime.fromisoformat(
                            created_at.replace("Z", "+00:00")
                        )
                        if (dt.hour, dt.minute, dt.second, dt.microsecond) == (0, 0, 0, 0):
                            ca_error = (
                                "created_at is midnight-exact (00:00:00) — agent "
                                "placeholder, not a Python-computed finalize time"
                            )
                        elif not (2025 <= dt.year <= 2100):
                            ca_error = (
                                f"created_at year {dt.year} outside plausible "
                                "range [2025, 2100]"
                            )
                    except (ValueError, TypeError) as e:
                        ca_error = f"created_at not ISO-8601 parseable: {e}"
                    if ca_error:
                        report["meta_valid"] = False
                        report["meta_created_at_invalid"] = ca_error
                        report["status"] = "FAIL"

                # Validate version matches expected
                if meta.get("version") != version:
                    report["meta_version_mismatch"] = {
                        "expected": version,
                        "found": meta.get("version"),
                    }
                    report["status"] = "FAIL"

        except json.JSONDecodeError as e:
            report["meta_valid"] = False
            report["meta_parse_error"] = str(e)
            report["status"] = "FAIL"
    else:
        report["meta_valid"] = False
        # meta.json missing is already captured in the missing files list

    return report


def emit_created_at():
    """
    Emit a Python-computed UTC ISO 8601 timestamp to stdout.

    This subcommand provides a trustworthy, system-clock-derived timestamp
    for meta.json created_at field. The audit main path (audit_snapshot)
    remains READ-ONLY — this subcommand only PRINTS; it never writes files.

    Usage:
        python snapshot_audit.py --emit-created-at

    Output:
        ISO 8601 UTC timestamp string to stdout (e.g. 2026-05-30T12:34:56.789012+00:00)
    """
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    print(ts)


def main():
    parser = argparse.ArgumentParser(
        description="Audit version snapshot integrity (READ-ONLY)"
    )
    parser.add_argument(
        "--snapshot_dir",
        required=False,
        default=None,
        help="Path to the snapshot directory (.version_history/{version}/)",
    )
    parser.add_argument(
        "--version",
        required=False,
        default=None,
        help="Expected semver version string",
    )
    parser.add_argument(
        "--aiap_dir",
        required=False,
        default=None,
        help="Path to the source AIAP directory",
    )
    parser.add_argument(
        "--emit-created-at",
        action="store_true",
        dest="emit_created_at",
        help="Emit a Python-computed UTC ISO 8601 timestamp to stdout and exit. "
             "Does not write any file. Use this to obtain a trustworthy created_at "
             "value for meta.json.",
    )

    args = parser.parse_args()

    # Subcommand: --emit-created-at
    if args.emit_created_at:
        emit_created_at()
        sys.exit(0)

    # Main audit path requires all three arguments
    if not args.snapshot_dir or not args.version or not args.aiap_dir:
        parser.error(
            "the following arguments are required for audit mode: "
            "--snapshot_dir, --version, --aiap_dir"
        )

    # Resolve paths
    snapshot_dir = os.path.abspath(args.snapshot_dir)
    aiap_dir = os.path.abspath(args.aiap_dir)

    # Run audit
    report = audit_snapshot(snapshot_dir, args.version, aiap_dir)

    # Output JSON report to stdout
    print(json.dumps(report, indent=2, ensure_ascii=False))

    # Exit code: 0 = PASS, 1 = FAIL
    sys.exit(0 if report["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
