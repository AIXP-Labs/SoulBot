#!/usr/bin/env python3
"""
resolve_target.py - Deterministic Evolution Target Resolution + Sovereignty Guard

Purpose (B-4, sovereignty-class):
  Replace the LLM-inferred "AUTHORITATIVE TARGET RESOLUTION" prose rule
  (PipelineStart step1(b), B1 v2.30.0) with a deterministic tool, because the
  prose rule ("NEVER fall back to _index.target as evolution target") has been
  repeatedly ignored by the sub-agent (cache/105: "would have modified the LIVE
  runner"), violating the target != runner invariant.

Responsibility:
  1. READ _index.json: user_message (the original user request, authoritative
     operand source), target (the executor / runner), workspace_dir.
  2. Deterministically extract the explicit evolution target from user_message
     (absolute-path regex first, then '{name}_aiap' name match).
  3. Resolve the extracted target to the actual AISOP directory on disk.
  4. SOVEREIGNTY GUARD: if the resolved target's realpath collapses onto the
     runner's realpath WHILE user_message named a DIFFERENT explicit path
     (user named another target but it landed on the runner) -> HARD_FAIL,
     exit 1 status=OPERAND_AMBIGUITY, do NOT write target. If user_message's
     explicit path IS the runner (legitimate engine-style self-evolution, where
     target == runner) -> ALLOW.
  5. Write authoritative _index.target_aiap_dir + pipeline_context.creator_directory
     (PipelineStart / DependencyCheck consume these directly; no LLM inference).

Scope discipline (sovereignty toolset class — pure stdlib helper):
  - Pure Python stdlib only (argparse, json, os, re, sys). No network, no LLM.
  - READ everything; WRITE ONLY the _index.json target fields
    (target_aiap_dir, pipeline_context.target_aiap_dir, pipeline_context.creator_directory).
  - NEVER touches *.aisop.json, AIAP.md, agent_card.json, quality_baseline.json,
    or any governance / snapshot file.

Usage:
    python resolve_target.py --cache_dir <path>
    python resolve_target.py --cache_dir <path> --dry-run
    python resolve_target.py --cache_dir <path> --chosen <aiap_store_program_dir>
        (NEEDS_INTENT_JUDGMENT follow-up: write the upstream-chosen aiap_store
         program as target — tool validates it is inside aiap_store first)

Options:
    --dry-run   Resolve + run sovereignty guard, print the resolution, but do
                NOT write _index.json. Read-only mode for verification reuse.

Target resolution (2026-06-14 spec):
    1. Absolute path/dir in user_message -> VALIDATE it exists on disk -> use.
       A non-existent absolute path is REJECTED (no parent-exists fake-path).
    2. No absolute path -> search ONLY aiap_store (NEVER the runner workspace_dir
       or any other directory). Exact '{name}_aiap' match in aiap_store -> use
       (deterministic python strong match). 0 or >1 matches -> emit the aiap_store
       candidate set for upstream LLM intent judgment (confidence > 80% -> use;
       <= 80% -> find related programs and ask the user).

Exit codes:
    0 = SUCCESS (target resolved + sovereignty guard passed; _index written
        unless --dry-run)
    1 = FAILURE — one of:
          OPERAND_AMBIGUITY     (user named other target but it lands on runner)
          NONEXISTENT_TARGET    (explicit absolute path does not exist on disk)
          NO_TARGET_IN_MESSAGE  (nothing parseable AND no aiap_store found)
          CHOSEN_NOT_FOUND      (--chosen path is not an existing directory)
          CHOSEN_OUTSIDE_AIAP_STORE (--chosen is not inside aiap_store)
          INDEX_NOT_FOUND       (_index.json missing/unreadable)
    2 = NEEDS_INTENT_JUDGMENT (no abs path + no exact aiap_store name; the
        aiap_store candidate set is returned for upstream LLM intent judgment /
        user choice — NEVER auto-defaults to the runner)

Output: JSON to stdout: {status, target_aiap_dir, creator_directory, source, ...}.
"""

import argparse
import json
import os
import re
import sys


def _realpath(p):
    """Normalized real path for robust same-directory comparison.

    Lowercases the drive letter region on Windows so that 'D:\\...' and 'd:/...'
    compare equal; normalizes separators and case-folds for case-insensitive
    filesystems (Windows). On POSIX this is a no-op beyond realpath.
    """
    if not p:
        return ""
    rp = os.path.realpath(os.path.abspath(p))
    rp = os.path.normcase(rp)
    return rp


def _aisop_dir_of(path):
    """Given a path that may point at a file (e.g. main.aisop.json) or a
    directory, return the containing AISOP program directory.

    A path to a .aisop.json file -> its parent directory (by suffix, regardless
    of on-disk existence, so the sovereignty comparison is robust even when the
    runner file is missing). Any other existing file -> its parent directory.
    A directory path -> itself.
    """
    if not path:
        return ""
    # Strip a *.aisop.json operand to its containing dir by suffix — independent
    # of whether the file currently exists on disk (robust runner comparison).
    base = os.path.basename(path)
    if base.endswith(".aisop.json"):
        return os.path.dirname(path)
    if os.path.isfile(path):
        return os.path.dirname(path)
    return path


# Absolute-path regex: Windows drive paths (D:\... or D:/...) and POSIX (/...).
# Captures contiguous path-like runs; trailing punctuation is stripped later.
# The character class [^\s'"，,；;。、：！？（）【】《》「」]+ is a single (non-nested) quantifier — it is
# linear-time-safe and NOT subject to catastrophic backtracking / ReDoS (RF-3,
# Tier1 arxiv 1301.0849 + CVE-2026-40319). stdlib re has no RE2 backend, so the
# regex itself is kept deliberately simple AND the matched input is length-capped
# below (see _PATH_SCAN_CAP) to bound worst-case scan cost over attacker-
# influenceable free-text user_message.
_WIN_ABS_RE = re.compile(r'[A-Za-z]:[\\/][^\s\'"，,；;。、：！？（）【】《》「」]+')
_POSIX_ABS_RE = re.compile(r'/[^\s\'"，,；;。、：！？（）【】《》「」]+')
# '{name}_aiap' bare-name token (no path separators), e.g. soulbot_creator_evolution_aiap
_NAME_AIAP_RE = re.compile(r'(?<![A-Za-z0-9_\-])([A-Za-z0-9][A-Za-z0-9_\-]*_aiap)(?![A-Za-z0-9_\-])')

# RF-3 length cap (LEVEL_C additive hardening): cap how much of the free-text
# user_message is fed to the path/name regexes. An evolution target path appears
# in the FIRST operand line of the request; capping the scan window bounds the
# worst-case regex cost on a long, attacker-influenceable user_message while
# still covering every realistic target reference. Generous (8192) so multi-line
# directive blocks whose target lives at the top are unaffected.
_PATH_SCAN_CAP = 8192


def _cap(text):
    """Return at most the first _PATH_SCAN_CAP chars of text (RF-3 length cap).

    Bounds the regex scan window over free-text user_message to keep matching
    linear-time-safe regardless of input length. Non-string / empty -> ''.
    """
    if not text:
        return ""
    return text[:_PATH_SCAN_CAP]


def _strip_trailing(p):
    """Strip trailing path separators and stray punctuation from an extracted path."""
    return p.rstrip('\\/ \t\r\n.,;:，。；：、')


def _find_aiap_store(workspace_dir):
    """Locate the aiap_store directory via a bounded walk-up from workspace_dir.

    Spec (2026-06-14): when no explicit absolute path is given, the evolution
    target is searched ONLY inside aiap_store — never the runner workspace_dir or
    any other directory. Returns the absolute aiap_store path, or None if none is
    found within the bounded walk-up.
    """
    anc = workspace_dir
    for _ in range(6):  # bounded walk-up
        if not anc:
            break
        store = os.path.join(anc, "aiap_store")
        if os.path.isdir(store):
            return os.path.abspath(store)
        parent = os.path.dirname(anc)
        if parent == anc:
            break
        anc = parent
    return None


def _enumerate_aiap_store_candidates(aiap_store):
    """List every '{name}_aiap' program in aiap_store with its agent_card
    name/description, for upstream LLM intent judgment. READ-ONLY.

    Returns a list of {dir, path, name, description}. agent_card name/description
    (often Chinese) let the upstream judge match cross-language user intent.
    """
    out = []
    if not aiap_store or not os.path.isdir(aiap_store):
        return out
    for entry in sorted(os.listdir(aiap_store)):
        d = os.path.join(aiap_store, entry)
        if not (entry.endswith("_aiap") and os.path.isdir(d)):
            continue
        name, desc = "", ""
        ac = os.path.join(d, "agent_card.json")
        if os.path.isfile(ac):
            try:
                with open(ac, "r", encoding="utf-8") as f:
                    data = json.load(f)
                name = data.get("name") or ""
                desc = data.get("description") or ""
            except Exception:
                pass
        out.append({
            "dir": entry,
            "path": os.path.abspath(d),
            "name": name,
            "description": desc,
        })
    return out


def extract_target_from_message(user_message, workspace_dir):
    """Deterministically extract the explicit evolution target from user_message.

    Resolution order (matches B1 v2.30.0 prose, now deterministic):
      (1) Absolute path in user_message that resolves to an AISOP directory.
      (2) '{name}_aiap' bare name -> scan workspace_dir for '{name}_aiap/'.

    Returns a tuple (resolved_aisop_dir, source) where source is one of
    'explicit_abs_path' | 'name_scan' | None. resolved_aisop_dir is None when
    no explicit target can be parsed.
    """
    if not user_message:
        return None, None

    # RF-3: cap the scan window over the free-text message before running any
    # regex (linear-time-safe bound; the target operand is always near the top).
    scan_text = _cap(user_message)

    # (1) Absolute path candidates. Prefer ones that contain '_aiap' or that
    # resolve to an existing directory / .aisop.json file.
    candidates = []
    for m in _WIN_ABS_RE.finditer(scan_text):
        candidates.append(m.group(0))
    for m in _POSIX_ABS_RE.finditer(scan_text):
        candidates.append(m.group(0))

    # Only TRUE absolute paths count as an explicit-path operand. A relative
    # fragment (e.g. free text caught with full-width parens like 'render_claim
    # （…）') must NEVER be abspath()'d into a CWD-relative target — that was the
    # fake-path fail-open (residual ②, 2026-06-14). Bare '{name}_aiap' names are
    # handled by the aiap_store search below, not here.
    abs_candidates = []
    for raw in candidates:
        cand = _strip_trailing(raw)
        if not cand or not os.path.isabs(cand):
            continue
        abs_candidates.append((cand, _aisop_dir_of(cand)))

    if abs_candidates:
        # Q2 (2026-06-14): an explicit absolute path MUST validate as an EXISTING
        # directory on disk. '_aiap'-named existing dirs first, then any existing.
        for cand, aisop_dir in abs_candidates:
            if ('_aiap' in os.path.basename(cand) or '_aiap' in os.path.basename(aisop_dir)) and os.path.isdir(aisop_dir):
                return os.path.abspath(aisop_dir), "explicit_abs_path"
        for cand, aisop_dir in abs_candidates:
            if os.path.isdir(aisop_dir):
                return os.path.abspath(aisop_dir), "explicit_abs_path"
        # Absolute path(s) given but NONE exist -> fail-closed. NEVER accept a
        # non-existent path because its parent exists (old Create-before-files
        # parent-only fake-path fail-open removed). main() -> NONEXISTENT_TARGET.
        return None, "abs_nonexistent"

    # (2) No absolute path operand. Per spec (2026-06-14): the target is searched
    # ONLY in aiap_store — NEVER the runner workspace_dir or any other directory
    # (unless the user gave an explicit absolute path/dir, handled above). This
    # enforces sovereignty (a bare name can never resolve onto the runner) AND
    # scopes intent judgment to the aiap_store program set.
    aiap_store = _find_aiap_store(workspace_dir)
    if not aiap_store:
        return None, None
    # python STRONG match (混合, deterministic first): an exact '{name}_aiap' dir
    # that lives in aiap_store and is named in the message.
    names = []
    for m in _NAME_AIAP_RE.finditer(scan_text):
        nm = m.group(1)
        if nm not in names:
            names.append(nm)
    matched = [nm for nm in names if os.path.isdir(os.path.join(aiap_store, nm))]
    if len(matched) == 1:
        return os.path.abspath(os.path.join(aiap_store, matched[0])), "name_scan"
    # 0 or >1 exact matches -> NO deterministic strong match. Defer to upstream
    # LLM intent judgment over the aiap_store candidate set (main() emits
    # NEEDS_INTENT_JUDGMENT with the candidate list).
    return None, None


def load_index(cache_dir):
    """Read _index.json from cache_dir. Returns (data, path) or raises."""
    index_path = os.path.join(cache_dir, "_index.json")
    if not os.path.isfile(index_path):
        raise FileNotFoundError(index_path)
    with open(index_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data, index_path


def write_index_targets(index_path, index_data, target_aiap_dir):
    """Write ONLY the target fields back to _index.json via atomic .tmp+rename.

    Writes:
      - _index.target_aiap_dir
      - _index.pipeline_context.target_aiap_dir
      - _index.pipeline_context.creator_directory
    Preserves everything else verbatim.
    """
    index_data["target_aiap_dir"] = target_aiap_dir
    pc = index_data.get("pipeline_context")
    if isinstance(pc, dict):
        pc["target_aiap_dir"] = target_aiap_dir
        pc["creator_directory"] = target_aiap_dir
    tmp_path = index_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8", newline="") as f:
        json.dump(index_data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp_path, index_path)


def main():
    parser = argparse.ArgumentParser(
        description="Deterministic evolution target resolution + sovereignty guard "
                    "(target != runner operand integrity)."
    )
    parser.add_argument(
        "--cache_dir",
        required=True,
        help="Absolute path to the execution cache directory containing _index.json",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Resolve + run sovereignty guard and print result, but do NOT write "
             "_index.json. Read-only mode for verification reuse.",
    )
    parser.add_argument(
        "--chosen",
        default=None,
        help="Absolute path of the aiap_store program selected by UPSTREAM intent "
             "judgment (the NEEDS_INTENT_JUDGMENT follow-up: confidence > 80%, or a "
             "user pick). The tool VALIDATES it is an EXISTING directory INSIDE "
             "aiap_store (NEVER the runner / any other dir), runs the sovereignty "
             "guard, then writes the target — so the tool stays the SOLE AUTHORITY "
             "for the target write even on the intent-judgment path.",
    )
    args = parser.parse_args()

    cache_dir = os.path.abspath(args.cache_dir)
    dry_run = args.dry_run

    report = {
        "status": "SUCCESS",
        "cache_dir": cache_dir,
        "mode": "dry_run" if dry_run else "resolve_and_write",
        "target_aiap_dir": None,
        "creator_directory": None,
        "source": None,
        "runner": None,
    }

    # Step 1: Load _index.json
    try:
        index_data, index_path = load_index(cache_dir)
    except Exception as e:
        report["status"] = "INDEX_NOT_FOUND"
        report["error"] = f"Cannot read _index.json: {e}"
        print(json.dumps(report, indent=2, ensure_ascii=False))
        sys.exit(1)

    user_message = index_data.get("user_message") or index_data.get("initial_user_message") or ""
    runner_target = index_data.get("target") or ""
    workspace_dir = (
        index_data.get("workspace")
        or index_data.get("workspace_dir")
        or (index_data.get("pipeline_context") or {}).get("workspace_dir")
        or ""
    )
    report["runner"] = runner_target

    # Step 2: UPSTREAM-CHOSEN target (NEEDS_INTENT_JUDGMENT follow-up) OR
    # deterministic extraction from user_message. --chosen keeps the tool the SOLE
    # AUTHORITY for the write: it validates the path is an EXISTING dir INSIDE
    # aiap_store (never the runner / any other dir) before writing.
    if args.chosen:
        chosen = os.path.abspath(args.chosen)
        aiap_store = _find_aiap_store(workspace_dir)
        if not os.path.isdir(chosen):
            report["status"] = "CHOSEN_NOT_FOUND"
            report["error"] = f"--chosen path does not exist as a directory: {chosen}"
            print(json.dumps(report, indent=2, ensure_ascii=False))
            sys.exit(1)
        store_rp = _realpath(aiap_store) if aiap_store else ""
        chosen_rp = _realpath(chosen)
        if not store_rp or not (chosen_rp == store_rp or chosen_rp.startswith(store_rp + os.sep)):
            report["status"] = "CHOSEN_OUTSIDE_AIAP_STORE"
            report["error"] = (
                "--chosen must be a program directory INSIDE aiap_store "
                "(sovereignty: never the runner or any other directory)."
            )
            print(json.dumps(report, indent=2, ensure_ascii=False))
            sys.exit(1)
        resolved_dir, source = chosen, "intent_chosen"
    else:
        resolved_dir, source = extract_target_from_message(user_message, workspace_dir)

    # Q2 (2026-06-14): explicit absolute path given but it does NOT exist on disk
    # -> fail-closed. NEVER accept a non-existent path (old parent-exists fake-path
    # fail-open removed). Surface for user adjudication.
    if source == "abs_nonexistent":
        report["status"] = "NONEXISTENT_TARGET"
        report["error"] = (
            "Explicit absolute path operand does not exist on disk. The target must "
            "be a validated EXISTING directory — refusing a non-existent path. "
            "Escalate to user."
        )
        print(json.dumps(report, indent=2, ensure_ascii=False))
        sys.exit(1)

    if resolved_dir is None:
        aiap_store = _find_aiap_store(workspace_dir)
        if not aiap_store:
            # QR2 (2026-06-15): no absolute path AND no aiap_store directory found
            # to search -> nothing to resolve, and nothing to judge intent over.
            # Emit NO_TARGET_IN_MESSAGE (the docstring exit-1 status) instead of
            # NEEDS_INTENT_JUDGMENT over an EMPTY candidate set. NEVER default to
            # the runner -> escalate to user.
            report["status"] = "NO_TARGET_IN_MESSAGE"
            report["error"] = (
                "No absolute path operand and no aiap_store directory found to "
                "search — cannot resolve an evolution target. NEVER default to the "
                "runner — escalate to user."
            )
            print(json.dumps(report, indent=2, ensure_ascii=False))
            sys.exit(1)
        # aiap_store exists but no absolute path + no deterministic strong name
        # match -> hand the aiap_store candidate set to upstream LLM intent
        # judgment (混合: python strong-match first, LLM semantic when none;
        # confidence > 80% -> use, <= 80% -> find related programs and ask user).
        # Candidates come ONLY from aiap_store. NEVER default to the runner.
        report["status"] = "NEEDS_INTENT_JUDGMENT"
        report["aiap_store"] = aiap_store
        report["candidates"] = _enumerate_aiap_store_candidates(aiap_store)
        report["error"] = (
            "No absolute path and no exact '{name}_aiap' match. Deferring to upstream "
            "intent judgment over aiap_store candidates (confidence > 80% -> use; "
            "<= 80% -> find related programs and ask the user). NEVER default to runner."
        )
        print(json.dumps(report, indent=2, ensure_ascii=False))
        sys.exit(2)

    report["source"] = source
    # Step 3: resolved_dir is already a validated EXISTING aisop directory
    # (explicit_abs_path or aiap_store name_scan) — no further existence check.
    target_abs = os.path.abspath(resolved_dir)
    report["target_aiap_dir"] = target_abs
    report["creator_directory"] = target_abs

    # Step 4: SOVEREIGNTY GUARD (target != runner operand integrity).
    runner_aisop_dir = _aisop_dir_of(runner_target)
    target_rp = _realpath(target_abs)
    runner_rp = _realpath(runner_aisop_dir)
    lands_on_runner = bool(runner_rp) and (target_rp == runner_rp)

    # Did the user_message explicitly name the runner itself? If so, target==runner
    # is legitimate engine-style self-evolution and MUST be allowed.
    user_named_runner = False
    if runner_rp:
        runner_scan_text = _cap(user_message)  # RF-3 length cap (same bound)
        for m in _WIN_ABS_RE.finditer(runner_scan_text):
            if _realpath(_aisop_dir_of(_strip_trailing(m.group(0)))) == runner_rp:
                user_named_runner = True
                break
        if not user_named_runner:
            for m in _POSIX_ABS_RE.finditer(runner_scan_text):
                if _realpath(_aisop_dir_of(_strip_trailing(m.group(0)))) == runner_rp:
                    user_named_runner = True
                    break

    report["lands_on_runner"] = lands_on_runner
    report["user_named_runner"] = user_named_runner

    if lands_on_runner and not user_named_runner:
        # User named a DIFFERENT explicit target, yet it collapsed onto the runner.
        # HARD_FAIL — do NOT write target; surface for user adjudication.
        report["status"] = "OPERAND_AMBIGUITY"
        report["error"] = (
            "SOVEREIGNTY GUARD: resolved target realpath == runner realpath, but "
            "user_message named a different explicit target. Refusing to default the "
            "operand onto the runner (target != runner). Escalate to user."
        )
        print(json.dumps(report, indent=2, ensure_ascii=False))
        sys.exit(1)
    # else: either target != runner (normal), or user explicitly named the runner
    # (legitimate engine-style self-evolution) -> ALLOW.

    # Step 5: Write authoritative target fields to _index.json (unless dry-run).
    if not dry_run:
        try:
            write_index_targets(index_path, index_data, target_abs)
            report["index_written"] = True
        except Exception as e:
            report["status"] = "FAILURE"
            report["error"] = f"Failed to write _index.json target fields: {e}"
            print(json.dumps(report, indent=2, ensure_ascii=False))
            sys.exit(1)
    else:
        report["index_written"] = False

    print(json.dumps(report, indent=2, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
