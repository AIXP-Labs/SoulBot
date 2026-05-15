# Contributing to SoulBot

Thank you for your interest in contributing to SoulBot!

> ⚠️ **Contribution Status (Current Stage)**
>
> We welcome **discussion through GitHub Issues** at this stage of development.
>
> **External Pull Requests are not currently accepted.** If you have a proposal — bug report, feature idea, new agent example, or improvement — please open an issue describing it. If we agree it adds value, maintainers will implement it and credit you.
>
> This policy may be revisited in the future.

> **Stage Status (v1.0.0)**
>
> SoulBot is at early development stage. The processes below describe the *target* development model. Initial decisions are made by AIXP Labs core maintainers; community discussion period scales as the contributor base grows.

## How to Contribute

### Reporting Issues

- Use [GitHub Issues](https://github.com/AIXP-Labs/SoulBot/issues) to report bugs, suggest features, or propose new examples
- Include Python version, OS, and LLM CLI tool version
- Provide minimal reproduction steps
- For AISOP / AIAP-related issues, link to the relevant `.aisop.json` file

### Discussion-Driven Development

1. Propose discussion via issue
2. Maintainers evaluate value, feasibility, and Axiom 0 alignment
3. After consensus, maintainers implement the change
4. Contributors are credited in commit / release notes

### Proposing a New Agent Example

When proposing a new example, include in the issue:

- **Use case** — what problem the agent solves
- **Agent type** — LLM / Sequential / Parallel / Loop / Multi-agent
- **AIAP package format?** — yes/no
- **External dependencies** — LLM API, MCP servers, tools needed
- **Why** the example is broadly useful

Maintainers will assess and implement if approved.

## Guidelines

### Quality Standards

- All new code must include tests (unit + integration where feasible)
- Code style: `ruff` (configured in `pyproject.toml`)
- Python 3.11+ type hints required
- Max line length: 100 characters
- Docstrings for public functions and classes
- No wildcard imports

### AISOP / AIAP Contributions

Changes to AISOP blueprints (`.aisop.json`) or AIAP packages (`*_aiap/`) should:

- Follow the [AIAP Protocol](https://github.com/AIXP-Labs/AIAP) specification
- Maintain deterministic execution paths in mermaid graphs
- Include governance metadata in `AIAP.md` for new packages

### Bilingual Requirement

README and CONTRIBUTING are maintained in English and Chinese. Issues can be in either language.

## Code of Conduct

By participating, you agree to abide by the [Code of Conduct](CODE_OF_CONDUCT.md).

## License of Contributions

By submitting (via issue or any future PR), your contribution is licensed under [Apache License 2.0](LICENSE).

Copyright 2026 AIXP Labs AIXP.dev | SoulBot.dev

---

Align Axiom 0: Human Sovereignty and Wellbeing. Version: SoulBot V1.0.0. www.soulbot.dev
