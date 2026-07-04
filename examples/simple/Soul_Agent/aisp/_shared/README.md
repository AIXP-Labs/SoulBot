# `_shared/` — cross-skill shared resources (AISP ecosystem)

This directory is part of the standard AISP skill-directory layout
(AISP V1.0.0, ecosystem conformance — "`_shared/` Scope"):

- Skills declare a resource with `"scope": "shared"`; its `path` then resolves
  **relative to `aisp/_shared/`** instead of the skill's own folder.
- `_shared/` carries **no `_aisp` suffix**, so the registry scanner
  (`aisp_list.py`, glob `*_aisp/`) naturally ignores it — it is never a skill.
- M5 confinement still applies: resource paths may only live inside the skill
  folder or `_shared/`; no `../` escape.

Example (from a skill's `aisp_contract.resources[]`):

```json
{ "id": "finance_terms", "path": "finance_terms.md", "kind": "doc",
  "mode": "read_only", "scope": "shared" }
```

→ resolves to `aisp/_shared/finance_terms.md`.

**Currently empty by design**: none of the skills bundled in this repository
declares a `scope: "shared"` resource. Shared resources travel **in pairs with
their host skill** — if a skill using `scope: "shared"` is added later, its
shared files must be added here in the same change (and removed together too).
