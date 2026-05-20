#!/usr/bin/env python3
"""check_dispatch_capability.py — Deterministic capability probe for node_engine dispatch.

Called from node_engine.aisop.json::step3 (d.1) to detect which sub-agent mechanism
is actually available, removing AI subjective fallback decisions.

Output (JSON, single line to stdout):
  {
    "agent_tool": bool,       # Claude Code Agent tool available
    "task_tool": bool,         # OpenCode Task tool available
    "gemini_cli": bool,        # `gemini` CLI in PATH
    "in_subagent": bool,       # We are running INSIDE a sub-agent already
    "subagent_depth": int,     # How deep (0 = main session)
    "recommended": str,        # "agent" | "task" | "gemini" | "inline_fallback"
    "reason": str              # Concrete reason for the recommendation
  }

Detection signals (best-effort across host AIs):
  - AGENT_HOST env var (set by some hosts: "claude_code" / "opencode" / "gemini_cli")
  - SUBAGENT_DEPTH env var (orchestrator increments per spawn)
  - CLAUDE_CODE_SESSION / OPENCODE_SESSION env presence
  - `gemini` binary presence in PATH (via shutil.which)
  - .claude/ or .opencode/ config dirs in working tree (advisory)

Exit code: 0 always. Caller reads JSON from stdout.
"""

from __future__ import annotations

import json
import os
import shutil
import sys


def _env_flag(name: str) -> bool:
    return bool(os.environ.get(name, "").strip())


def probe() -> dict:
    host = os.environ.get("AGENT_HOST", "").lower()

    # Subagent depth detection — orchestrator MUST increment SUBAGENT_DEPTH
    # before spawning. Depth 0 = main host session; >=1 = nested context where
    # spawning another Agent tool is typically disabled or risky.
    depth_raw = os.environ.get("SUBAGENT_DEPTH", "0")
    try:
        subagent_depth = int(depth_raw)
    except ValueError:
        subagent_depth = 0
    in_subagent = subagent_depth > 0

    # Capability flags (env-driven; deterministic — no AI guessing)
    agent_tool = (host == "claude_code") or _env_flag("CLAUDE_CODE_SESSION")
    task_tool = (host == "opencode") or _env_flag("OPENCODE_SESSION")
    gemini_cli = shutil.which("gemini") is not None

    # If host AI didn't declare itself via env, fall back to install-marker hints.
    # Checks (in order): cwd .claude/, user-home .claude/, user-home .opencode/.
    # Advisory only — does NOT silently promote inline to agent.
    if not (agent_tool or task_tool):
        cwd = os.getcwd()
        home = os.path.expanduser("~")
        if os.path.isdir(os.path.join(cwd, ".claude")) or os.path.isdir(
            os.path.join(home, ".claude", "projects")
        ):
            agent_tool = True
        elif os.path.isdir(os.path.join(cwd, ".opencode")) or os.path.isdir(
            os.path.join(home, ".opencode")
        ):
            task_tool = True

    # Priority decision tree (matches node_engine step3 (d.2))
    if agent_tool and not in_subagent:
        recommended = "agent"
        reason = "Claude Code Agent tool available + not in nested subagent"
    elif task_tool and not in_subagent:
        recommended = "task"
        reason = "OpenCode Task tool available + not in nested subagent"
    elif gemini_cli:
        recommended = "gemini"
        reason = "gemini CLI in PATH"
    elif in_subagent:
        recommended = "inline_fallback"
        reason = (
            f"Already in subagent (depth={subagent_depth}); nested spawn unreliable. "
            "Inline_fallback is correct but MUST be logged with fallback_reason."
        )
    else:
        recommended = "inline_fallback"
        reason = (
            "No sub-agent capability detected: AGENT_HOST unset, no .claude/.opencode "
            "config, no gemini in PATH. inline_fallback is the only viable mode."
        )

    return {
        "agent_tool": agent_tool,
        "task_tool": task_tool,
        "gemini_cli": gemini_cli,
        "in_subagent": in_subagent,
        "subagent_depth": subagent_depth,
        "recommended": recommended,
        "reason": reason,
    }


def main() -> int:
    result = probe()
    json.dump(result, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
