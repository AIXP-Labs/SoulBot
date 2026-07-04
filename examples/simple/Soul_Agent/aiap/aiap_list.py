#!/usr/bin/env python3
"""aiap_list.py — discover AIAP packages under this folder.

Scans <this_dir>/*_aiap/main.aisop.json, reads each package's
system.content self-describing metadata (id/name/version/summary/loading_mode),
prints a human/AI-readable list, and (with --json) writes aiap_list.json.
Zero deps (stdlib). Side effect: only --json writes aiap_list.json; --check is
read-only and fails on drift. Any malformed *_aiap package is a hard index
error, not a silent skip.
  python -B aiap_list.py          # print the list
  python -B aiap_list.py --json   # also (re)generate aiap_list.json
  python -B aiap_list.py --check  # verify committed aiap_list.json
  python -B aiap_list.py --help   # print usage

Structure mirrors the sibling aisp/aisp_list.py (spec-normative reference);
if you change one, review the other.

Security guarantees (SE5 / ST1). This script MUST be zero-dependency (standard
library only) and human-auditable. It MUST NOT: access the network; import
third-party packages; execute package code; modify any file except
aiap_list.json when --json is explicitly used; read files outside the aiap/
directory. The reference implementation below meets all of these: it imports
only `json` and `sys` from the stdlib, globs only `*_aiap/main.aisop.json`
under its own directory, and writes only `aiap_list.json`.
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VALID_LOADING_MODES = ("normal", "node", "lite")
USAGE = """usage: python -B aiap_list.py [--json] [--check] [--help]

Discover AIAP packages under this directory.

Options:
  --json   regenerate aiap_list.json from *_aiap/main.aisop.json folders
  --check  verify aiap_list.json is current without writing
  --help   show this help
"""

def discover():
    packages = []
    errors = []
    for f in sorted(ROOT.glob("*_aiap/main.aisop.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8-sig"))
            sc = data[0]["content"]                  # system: self-describing metadata
        except Exception as e:
            errors.append(f"{f}: {e}")
            continue
        if not isinstance(sc, dict):
            errors.append(f"{f}: system.content must be an object")
            continue
        loading_mode = sc.get("loading_mode", "normal")   # missing -> normal (legacy default)
        if loading_mode not in VALID_LOADING_MODES:
            errors.append(f"{f}: invalid loading_mode '{loading_mode}' (expected one of {VALID_LOADING_MODES})")
            continue
        packages.append({
            "id": f.parent.name,                     # directory name incl. _aiap suffix (unique key)
            "name": sc.get("name"),
            "version": sc.get("version", ""),
            "summary": sc.get("summary") or sc.get("description", ""),
            "path": str(f.relative_to(ROOT.parent)).replace("\\", "/"),
            "loading_mode": loading_mode,
        })
    return packages, errors

def render_index(packages):
    return json.dumps({"aiap_list_version": "1.0", "packages": packages},
                      ensure_ascii=False, indent=2) + "\n"

def normalized(text):
    return text.replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿").rstrip("\n")

def main():
    allowed_args = {"--json", "--check", "--help", "-h"}
    unknown_args = [arg for arg in sys.argv[1:] if arg not in allowed_args]
    if unknown_args:
        print(f"ERROR: unknown argument(s): {', '.join(unknown_args)}", file=sys.stderr)
        print(USAGE.rstrip(), file=sys.stderr)
        return 2
    if "--help" in sys.argv or "-h" in sys.argv:
        print(USAGE.rstrip())
        return 0
    packages, errors = discover()
    if errors:
        print("ERROR: cannot build AIAP index:", file=sys.stderr)
        for error in errors:
            print(f"  {error}", file=sys.stderr)
        return 1
    for p in packages:
        print(f"- {p['id']}: {p['summary']}  ->  {p['path']}")
    print(f"\n{len(packages)} AIAP package(s).")
    expected = render_index(packages)
    if "--check" in sys.argv:
        out = ROOT / "aiap_list.json"
        if not out.exists():
            print(f"{out} is missing; run python -B aiap_list.py --json", file=sys.stderr)
            return 1
        actual = out.read_text(encoding="utf-8-sig")
        if normalized(actual) != normalized(expected):
            print(f"{out} is stale; run python -B aiap_list.py --json", file=sys.stderr)
            return 1
        print("aiap_list.json ok")
        return 0
    if "--json" in sys.argv:
        out = ROOT / "aiap_list.json"
        out.write_text(expected, encoding="utf-8", newline="\n")
        print(f"Wrote {out}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
