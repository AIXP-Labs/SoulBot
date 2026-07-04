<!-- generated_from_aisp: true -->
<!-- source: aisp.aisop.json -->
<!-- generator: tools/aisp_readme.py -->

# Random Draw Picker

This README is a deterministic projection of `aisp.aisop.json`. The contract remains the source of truth.

## Identity

| Field | Value |
| --- | --- |
| Skill ID | `random_draw_aisp` |
| Version | `1.0.0` |
| Protocol | `AISP V1.0.0` |
| License | `Apache-2.0` |
| Risk Level | `low` |
| Category | utility |
| Tags | random-draw, lottery, random, decision, csprng |

## Purpose

本地等概率随机抽签, 从用户给定的多个对等选项中无偏随机抽取一个(非严肃决策建议)。

## When To Use

- 在多个对等选项间需要无偏随机抽取一个时
- 随机抽签/抓阄/多选一随机抉择
- 打破多选(>=2)僵局

## When Not To Use

- 医疗/法律/财务等严肃或高风险决策
- 需要按权重/概率不等的加权抽取
- 需要可复现的固定结果
- 任何需要联网数据的决策

## How To Run

With an AISOP runtime:

1. Load `aisp.aisop.json`.
2. Read `user.content.aisp_contract` before execution.
3. Run `user.content.aisop.main` exactly as declared.
4. Enforce every `non_negotiable` rule and every referenced `sys.*` mechanism.
5. Treat `sys.io.confirm` and other human-confirmation gates as blocking controls.

With a generic AI or non-AISOP agent:

- Treat this README as bootstrap guidance only.
- Verify external provenance or obtain explicit human approval before executing an untrusted package.
- Load the contract from `aisp.aisop.json`; do not treat this README as authoritative.
- Follow `RUN aisop.main` and the non-negotiable rules on a best-effort basis.
- Hard guarantees such as `sys.assert`, tool gating, and `sys.io.confirm` exist only in a conforming AISOP runtime.

## Non-Negotiable Rules

| Rule | Enforced By |
| --- | --- |
| 抽取必须使用本地密码学安全随机(Python secrets, 如 secrets.randbelow(len(options)) 或 secrets.choice), 绝不使用可预测的 random; 保证等概率 1/len(options)。脚本在 stdout JSON 中标记 rng='secrets', draw 节点断言该标记。 | `draw.step2:sys.assert` |
| 绝不联网: 不声明任何 web 工具, open_world=false, 仅本地计算/脚本(filesystem, shell)。 | `tools` |
| 每次输出必须包含免责声明: 结果为随机、非严肃/高风险决策的建议。 | `report.step3:sys.assert` |
| options 必须是 >=2 个非空且互异的选项; n 必须为 1..100 的整数; 越界/空/单项/重复即拒。 | `parse_input.step2:sys.assert` |

## Resources

| ID | Path | Kind | Mode | Scope | SHA-256 |
| --- | --- | --- | --- | --- | --- |
| draw_script | scripts/draw.py | script | execute_only | skill |  |
| script_behavior | evals/script-behavior.json | eval | read_only | skill |  |

## Integrity

| Hash | Value | Meaning |
| --- | --- | --- |
| `contract_sha256` | `795a45aa43fa9a833639e142ff8e79c429566af72aabcd7fb4c33511f7d45308` | Recomputable hash of `user.content.aisp_contract` |
| `resources_sha256` | `57e97cc11ad5be94db396d6b74c27e5099796150fd8118e525d1c87a4f989ab1` | Recomputable hash of declared resource records |

`package_sha256` is intentionally not embedded here because a README is part of the distributed package and package-level hashes belong in external registry/provenance artifacts. Recompute it with `tools/aisp_hash.py` at publication time.

These hashes show local integrity only. They do not prove trust, safety, or registry approval.

## Source Of Truth

`aisp.aisop.json` is authoritative. A successful README check proves only that this file matches the contract-derived projection; it does not prove that the skill is safe or trustworthy.
