#!/usr/bin/env python3
"""P5 — deterministic version-snapshot BUILDER for AIAP evolution targets.

Why this exists (plan22/02 P5 + plan22/03 §13.2): building the
`.evolution_snapshot/v<ver>/` snapshot was a prose step inside the (bypassable)
ReviewFinalize node -> it got skipped run-to-run (cache/89 had none) and used
placeholder timestamps. This tool makes snapshot-building DETERMINISTIC and
target-aware: it copies the governance file set and writes meta.json with a REAL
Python-emitted created_at (E4 — never an agent placeholder like 00:00:00) plus
per-file sha256 and the current governance_hash.

It is the snapshot analogue of governance_hash.py (the SOLE-AUTHORITY hash tool).
ReviewFinalize SHOULD call it; the band-out finalize_audit.py also calls it so
snapshot-building does not depend on the orchestrator's cooperation.

Usage:
    python -X utf8 snapshot_build.py --program_dir <target_aiap_dir> --version 5.30.0
                                     [--snapshot_root <dir>]   # default: <program_dir>/.evolution_snapshot

Exit 0 = built OK. Exit 1 = error. Pure stdlib, no network, no LLM.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone

# Non-.aisop governance files included in a snapshot (copied only if present).
GOV_EXTRA = [
    "AIAP.md",
    "AIAP_cn.md",
    "agent_card.json",
    "quality_baseline.json",
    "protocol_config.json",
    "mcp_config.json",
]


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_governance_hash(program_dir: str):
    """Best-effort read of the current governance_hash from agent_card.json."""
    ac = os.path.join(program_dir, "agent_card.json")
    if os.path.exists(ac):
        try:
            with open(ac, "r", encoding="utf-8") as f:
                v = json.load(f).get("governance_hash")
            return v if isinstance(v, str) else None
        except Exception:
            return None
    return None


def build_snapshot(program_dir: str, version: str, snapshot_root: str | None = None, pipeline_run_id: str = "") -> dict:
    program_dir = os.path.abspath(program_dir)
    if not os.path.isdir(program_dir):
        return {"status": "error", "errors": [f"program_dir not found: {program_dir}"]}

    snapshot_root = snapshot_root or os.path.join(program_dir, ".evolution_snapshot")
    dest = os.path.join(snapshot_root, f"v{version}")

    aisop = sorted(glob.glob(os.path.join(program_dir, "*.aisop.json")))
    files = [os.path.basename(p) for p in aisop]
    for extra in GOV_EXTRA:
        if os.path.exists(os.path.join(program_dir, extra)):
            files.append(extra)

    if not files:
        return {"status": "error", "errors": [f"no snapshot-able files in {program_dir}"]}

    os.makedirs(dest, exist_ok=True)
    file_hashes = {}
    for fn in files:
        src = os.path.join(program_dir, fn)
        shutil.copy2(src, os.path.join(dest, fn))
        file_hashes[fn] = "sha256:" + _sha256_file(src)

    # E4: REAL timestamp, Python-emitted. NEVER an agent placeholder (00:00:00 / on-the-minute).
    created_at = datetime.now(timezone.utc).isoformat()

    meta = {
        # snapshot_audit.py META_REQUIRED_FIELDS contract (2026-06-10 fix): the
        # builder MUST emit version / source_version / pipeline_run_id (the new
        # builder previously only emitted snapshot_version -> snapshot_audit exit 1).
        "version": version,
        "source_version": version,
        "pipeline_run_id": pipeline_run_id,
        "snapshot_version": version,
        "created_at": created_at,
        "source_dir": program_dir.replace("\\", "/"),
        "governance_hash": _read_governance_hash(program_dir),
        "file_count": len(files) + 1,  # + meta.json itself
        "files": files,
        "file_hashes": file_hashes,
        "built_by": "snapshot_build.py (P5, band-out deterministic; created_at is real per E4)",
    }
    with open(os.path.join(dest, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    return {
        "status": "ok",
        "dest": dest.replace("\\", "/"),
        "version": version,
        "file_count": len(files) + 1,
        "created_at": created_at,
        "governance_hash": meta["governance_hash"],
        "files": files,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="P5 deterministic version-snapshot builder")
    ap.add_argument("--program_dir", required=True, help="Target AIAP dir to snapshot")
    ap.add_argument("--version", required=True, help="Version label, e.g. 5.30.0 (snapshot dir = v<version>)")
    ap.add_argument("--snapshot_root", default=None, help="Override snapshot root (default <program_dir>/.evolution_snapshot)")
    ap.add_argument("--pipeline_run_id", default="", help="Pipeline run id (UUID) for meta.json — required by snapshot_audit.py; pass the run's id")
    args = ap.parse_args()
    result = build_snapshot(args.program_dir, args.version, args.snapshot_root, pipeline_run_id=args.pipeline_run_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
