# Changelog

All notable user-facing changes to SoulBot are documented in this file.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/). The
framework itself is not strictly SemVer-versioned; engines and skills carry
their own versions inside their packages.

## [Unreleased] — 2026-07-04

### Added
- **AISP V1.0.0 support (dual-protocol runtime)** — the engine natively runs
  single-file AISP skills (`*_aisp/aisp.aisop.json`) alongside AIAP programs.
  Package registries are generated, not hand-maintained: folders are the source
  of truth, `aiap/aiap_list.py` / `aisp/aisp_list.py` produce the caches, and a
  missing or stale cache self-heals on the next turn.
- **Contract red-line hard gates** — `aisp_contract.non_negotiable` rules bound
  via `enforced_by: "<node>.<step>:sys.assert"` are enforced by the engine on
  both agent-dispatched and inline execution paths: a failing red-line
  assertion HARD_FAIL-halts the run (no retry, no degrade) and surfaces the
  triggered rule to the human. Each run leaves an audit trail
  (`redline_map_audit_run` in the execution cache).
- **Routing ask-principle (Axiom 0)** — when several packages cover the same
  intent and the user did not explicitly name one, the router presents a
  numbered candidate list and waits for the user's choice instead of silently
  picking. Protocol words that describe the *product* (e.g. "create an AISP
  skill") do not count as naming an executor.
- **aisp_store** — six bundled AISP skills: `aisp_creator_evolution` v1.1.0,
  `webapp_testing` v1.3.0, `mcp_builder` v2.0.0, `yijing`, `random_draw`, and
  `redline_breach_test` (a probe that deliberately violates its own red line so
  you can verify the hard gate halts on your machine).
- **Creator default landing** — newly created skills land in `aisp_store/`
  (delivery ≠ install): nearest-`aisp_store` resolution with a
  sibling-directory fallback; an explicit `output_path` always wins.
- `templates/basic` now ships `aisp/` (registry generator + `_shared/`
  cross-skill resource directory with its concept README).

### Fixed
- Foreground Ctrl+C now stops the process immediately: the ACP auto-resume
  loop no longer fights user shutdown (zero-progress circuit breaker, shutdown
  gates before resume, uvicorn exit signal honored).
- `resolve_target` store-scope and POSIX-path capture bugs in the creator
  toolchain.

### Changed
- `agent.py` registry handling externalized to generated caches
  (`aiap_list.json` / `aisp_list.json`); routing discipline hardened — explicit
  naming is absolute, execution runs continuously to a designed gate
  (`sys.io.confirm` / user gate) or HARD_FAIL, with no mid-run
  "shall I continue" pauses.
