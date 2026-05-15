# SoulBot

**AI Agent Framework with AISOP Protocol and AIAP Package System**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-1259%20passed-brightgreen.svg)](#testing)

[中文文档](README_CN.md) | English

## What is SoulBot?

SoulBot is a Python-based AI Agent framework that connects to LLMs through CLI subprocesses using the ACP protocol (via [soulacp](https://soulacp.dev)) — **no API keys required**. It introduces a unique architecture where agent behavior is defined by **AISOP blueprints** (`.aisop.json`, Mermaid flowcharts) and extended through **AIAP packages** (`*_aiap`), making AI agent behavior deterministic, reproducible, and version-controlled.

### Key Features

- **No API Key Required** — Connects to LLMs via Claude Code / Gemini CLI / OpenCode CLI subprocesses (powered by [soulacp](https://soulacp.dev))
- **Multi-Model Switching** — Claude, Gemini, OpenCode (Kimi, etc.) — switch with one line in `.env`
- **AISOP Protocol** — Agent behavior defined by `.aisop.json` (Mermaid flowcharts) blueprints
- **AIAP Package System** — Hot-pluggable capability packages (`*_aiap`) with AISOP entry points, extending agent functionality
- **Agent Composition** — Single agent, multi-agent routing, Sequential / Parallel / Loop workflows
- **Tool System** — Python functions auto-wrapped as LLM-callable tools
- **Multi-Channel** — Terminal CLI, Web Dev UI, Telegram Bot
- **Streaming Output** — SSE typewriter effect (Web + Telegram)

---

## Quick Start

### Prerequisites

- Python 3.11+
- At least one LLM CLI tool installed:

| Tool | Install | Login |
|------|---------|-------|
| Claude Code | `npm install -g @anthropic-ai/claude-code` | `claude login` |
| Gemini CLI | `npm install -g @google/gemini-cli` | `gemini login` |
| OpenCode | `npm install -g opencode` | Free models, no login needed |

> 💡 **Recommended combination**: SoulBot + Claude Code CLI + Claude Opus 4.7. This project is primarily developed and tested with this stack. New users: start here.

### Install

```bash
git clone https://github.com/AIXP-Labs/SoulBot.git
cd SoulBot
pip install -e .
```

### First-time setup

Before running, rename the example config to `.env`:

```bash
mv examples/simple/SoulBot_Agent/.env.example examples/simple/SoulBot_Agent/.env
```

Open the new `.env` and pick your LLM backend (Claude / Gemini / OpenCode).

### Run

```bash
# Simple mode (one-click Web Dev UI)
python start.py

# Web Dev UI (open http://127.0.0.1:2026)
soulbot web --agents-dir examples/simple

# Terminal interactive mode
soulbot run examples/simple/SoulBot_Agent

# Telegram Bot
soulbot telegram examples/simple/SoulBot_Agent
```

### Create Your Own Agent

```bash
soulbot create my_agent
```

This generates:

```
my_agent/
├── agent.py          # Agent definition
├── main.aisop.json   # AISOP blueprint (Mermaid flowchart)
├── .env              # Configuration (model selection)
└── aisop_aiap/       # AISOP-format AIAP package directory
```

Edit `.env` to select your LLM backend, then run:

```bash
soulbot run my_agent
```

---

## Architecture

### AISOP + AIAP

SoulBot introduces two core concepts:

| Concept | Description |
|---------|-------------|
| **AISOP V1.0.0** | AI Standard Operating Procedure — a JSON-based blueprint protocol that defines agent behavior through **Mermaid flowcharts** |
| **AIAP Packages** | AI Application Packages — hot-pluggable capability modules (`*_aiap/`) with AISOP entry point (`main.aisop.json`) |

**The key insight**: flowcharts serve as deterministic execution paths (like circuit diagrams), while prompts provide context and constraints (like component specifications). AISOP uses Mermaid syntax (ideal for visualization). This separation makes agent behavior reproducible and version-controllable.

```
User Message
    ↓
agent.py → _dynamic_instruction()
    ├── _SYSTEM_PROMPT (WHO — runtime identity)
    ├── main.aisop.json (WHAT — routing rules)
    └── [Available AIAP packages] (capabilities, scanned from aisop_aiap/)
    ↓
LLM follows flowchart:
    NLU[Match Intent] → Run[Load & Execute *_aiap/main.aisop.json]
    ↓
AIAP package's flow executes domain-specific logic
    ↓
Response returned to user
```

### Governance Domains

AIAP operates under a tripartite federated trust model:

- **aisop.dev** (Seed Layer): Defines the unchangeable format structure.
- **aiap.dev** (Authority Layer): Defines the evolving governance rules.
- **soulbot.dev** (Executor Layer): The reference runtime engine that physically acts upon AISOP code.

### System Architecture

```
Entry Points
├── CLI Terminal     →  soulbot run <agent_dir>
├── Web Dev UI       →  soulbot web --agents-dir <dir>
├── API Server       →  soulbot api-server --agents-dir <dir>
└── Telegram Bot     →  soulbot telegram <agent_dir>
         ↓
Runner
├── Agent Tree       →  LlmAgent / SequentialAgent / ParallelAgent / LoopAgent
├── AISOP Engine       →  .aisop.json (Mermaid) → AIAP routing
├── Tool Calls       →  FunctionTool / AgentTool / TransferToAgentTool
├── CMD System       →  Embedded commands (scheduling, etc.)
├── Sessions         →  InMemory / SQLite + State delta
├── EventBus         →  pub/sub + filtering + priority
└── Streaming        →  partial Events → SSE / Telegram typewriter
         ↓
Model Layer
├── ModelRegistry    →  regex matching → adapter selection
└── ACPLlm           →  soulacp library
     (soulacp wraps CLI subprocesses as JSON-RPC clients;
      supports claude-acp/* | gemini-acp/* | opencode-acp/*)
```

---

## Agent Development

### Minimal Agent

```python
from soulbot.agents import LlmAgent

root_agent = LlmAgent(
    name="my_agent",
    model="claude-acp/sonnet",
    instruction="You are a helpful assistant.",
)
```

### Agent with Tools

```python
from soulbot.agents import LlmAgent

def get_weather(city: str) -> dict:
    """Get weather for a city."""
    return {"city": city, "temp": 25, "condition": "sunny"}

root_agent = LlmAgent(
    name="weather_agent",
    model="claude-acp/sonnet",
    instruction="You can check weather for any city.",
    tools=[get_weather],
)
```

Functions are auto-wrapped as LLM tools: function name becomes tool name, docstring becomes description, type hints become JSON Schema.

### Multi-Agent Routing

```python
from soulbot.agents import LlmAgent

billing = LlmAgent(name="billing", model="claude-acp/sonnet",
                    description="Handles billing questions",
                    instruction="You are a billing specialist.")

tech = LlmAgent(name="tech", model="claude-acp/sonnet",
                description="Handles technical issues",
                instruction="You are tech support.")

root_agent = LlmAgent(
    name="router",
    model="claude-acp/sonnet",
    instruction="Route user to the appropriate specialist.",
    sub_agents=[billing, tech],
)
```

### Workflow Agents

```python
from soulbot.agents import LlmAgent, SequentialAgent, ParallelAgent, LoopAgent

# Sequential: run agents in order
root_agent = SequentialAgent(name="pipeline", sub_agents=[analyzer, responder])

# Parallel: run agents concurrently
root_agent = ParallelAgent(name="parallel", sub_agents=[search, summarize])

# Loop: repeat until escalation
root_agent = LoopAgent(name="refiner", sub_agents=[draft, review], max_iterations=3)
```

---

## Configuration

### .env Reference

```env
# LLM Backend (set one to true)
CLAUDE_CLI=true
GEMINI_CLI=false
OPENCODE_CLI=false

# Model names
CLAUDE_MODEL=claude-acp/sonnet
GEMINI_MODEL=gemini-acp/gemini-3-flash-preview
OPENCODE_MODEL=opencode-acp/opencode/gemini-3-flash-preview

# Behavior
WORKSPACE_DIR=aiap            # AIAP package directory
ENABLE_FALLBACK=false         # Auto-switch model on failure
AUTO_APPROVE_PERMISSIONS=true # Auto-approve CLI permissions
SHOW_THOUGHTS=false           # Show AI thinking process

# Telegram (optional)
TELEGRAM_BOT_TOKEN=
```

### Model Name Formats

| Format | Description |
|--------|-------------|
| `claude-acp/sonnet` | Claude Sonnet |
| `claude-acp/opus` | Claude Opus |
| `gemini-acp/gemini-3-flash-preview` | Gemini Flash |
| `opencode-acp/opencode/gemini-3-flash-preview` | OpenCode Gemini Flash |
| `opencode-acp/anthropic/claude-sonnet-4-5` | OpenCode → Claude |

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `soulbot run <agent_path>` | Terminal interactive mode |
| `soulbot web --agents-dir <dir>` | Web Dev UI + API Server |
| `soulbot api-server --agents-dir <dir>` | API Server only (no UI) |
| `soulbot telegram <agent_path>` | Telegram Bot |
| `soulbot create <name>` | Scaffold a new agent project |

`python -m soulbot` can be used instead of `soulbot` without installation.

---

## Web Dev UI

```bash
soulbot web --agents-dir examples/simple
# Open http://127.0.0.1:2026
```

Features: Markdown rendering, SSE streaming, agent switching, session management, dark theme.

### API Endpoints

| Route | Method | Description |
|-------|--------|-------------|
| `/health` | GET | Health check |
| `/list-apps` | GET | List all agents |
| `/apps/{name}` | GET | Agent details |
| `/run` | POST | Synchronous execution |
| `/run_sse` | POST | SSE streaming execution |

---

## Telegram Bot

1. Get a bot token from [@BotFather](https://t.me/BotFather)
2. Add `TELEGRAM_BOT_TOKEN=your_token` to `.env`
3. Run: `soulbot telegram examples/simple/SoulBot_Agent`

Or run Web + Telegram together: `soulbot web --agents-dir examples/simple`

Bot commands: `/start`, `/clear`, `/history`

Features: streaming output, Markdown rendering, auto message splitting, multi-agent routing via InlineKeyboard.

---

## Scheduling

AI-driven scheduling system — the AI embeds `<!--SOULBOT_CMD:-->` directives in responses to create scheduled tasks.

- Three trigger types: Once / Interval / Cron
- Cross-agent scheduling: Agent A creates tasks for Agent B
- AISOP payload: scheduled tasks carry complete AISOP V1.0.0 blueprints
- Persistent recovery: auto-restore active tasks after restart

---

## Project Structure

```
SoulBot/
├── src/soulbot/              # Framework source
│   ├── agents/               # Agent system (LlmAgent, Sequential, Parallel, Loop)
│   ├── tools/                # Tool system (FunctionTool, AgentTool)
│   ├── models/               # ACPLlm + ModelRegistry (delegates to soulacp library)
│   ├── runners/              # Runner (drives agent execution)
│   ├── sessions/             # Session (InMemory / SQLite)
│   ├── server/               # Web/API Server (FastAPI + SSE)
│   ├── connect/              # Channel connectors (Telegram)
│   ├── commands/             # CMD system (embedded commands)
│   ├── scheduler/            # Task scheduling
│   ├── templates/            # Agent scaffolding templates
│   └── cli.py                # CLI entry point
├── examples/simple/          # Example agents
│   └── SoulBot_Agent/        # Main agent with AIAP packages
├── tests/                    # 1266 unit tests
├── docs/                     # Documentation
└── pyproject.toml            # Project configuration
```

---

## Testing

```bash
# All unit tests
python -m pytest tests/ -q

# Specific module
python -m pytest tests/test_agents/ -q

# E2E tests (requires real CLI login)
python -m pytest tests/e2e/ -m live -q
```

---

## Installation Options

```bash
# Development (editable)
pip install -e ".[dev]"

# With Telegram support
pip install -e ".[telegram]"

# With SQLite sessions
pip install -e ".[sqlite]"

# Everything
pip install -e ".[dev,telegram,sqlite]"

# From GitHub
pip install git+https://github.com/AIXP-Labs/SoulBot.git

# One-line run (uv)
uvx --from git+https://github.com/AIXP-Labs/SoulBot.git soulbot web --agents-dir .
```

See [INSTALL.md](INSTALL.md) for detailed installation and publishing guide.

---

## Documentation

| Document | Description |
|----------|-------------|
| [GUIDE.md](GUIDE.md) | Comprehensive usage guide (Chinese) |
| [INSTALL.md](INSTALL.md) | Installation, packaging, and publishing (Chinese) |
| [SECURITY.md](SECURITY.md) | Security policy and vulnerability reporting (EN + CN) |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Contribution process |
| [GOVERNANCE.md](GOVERNANCE.md) | Project governance and decision-making |
| [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) | Community code of conduct (Axiom 0 alignment) |
| [CHANGELOG.md](CHANGELOG.md) | Release history including security fixes |
| [docs/guide/01-function-call-guide.md](docs/guide/01-function-call-guide.md) | Function Call developer guide |
| [docs/guide/02-soulbot-cmd-guide.md](docs/guide/02-soulbot-cmd-guide.md) | SoulBot CMD developer guide |

---

## AIXP Labs [aixp.dev](https://aixp.dev)

AIXP Labs develops and maintains the following core projects:

| Project | Description | Website |
|---------|-------------|---------|
| [HSAW](https://hsaw.dev) | Human Sovereignty and Wellbeing — Axiom 0 white paper (foundation) | hsaw.dev |
| [AILP](https://ailp.dev) | AI List Protocol — agent discovery and capability advertising | ailp.dev |
| [AIVP](https://aivp.dev) | AI Value Protocol — international commerce, crypto asset settlement | aivp.dev |
| [AIRP](https://airp.dev) | AI RMB Protocol — Mainland China commerce, RMB licensed settlement | airp.dev |
| [AIBP](https://aibp.dev) | AI Bot Protocol — social communication and trust | aibp.dev |
| [AIAP](https://aiap.dev) | AI Application Protocol — governance and compliance | aiap.dev |
| [AISOP](https://aisop.dev) | AI Standard Operating Protocol — flow program definition | aisop.dev |
| [SoulBot](https://soulbot.dev) | AI agent runtime and framework (this project) | soulbot.dev |
| [SoulACP](https://soulacp.dev) | Adapter library — bridging CLI tools and LLM providers | soulacp.dev |

---

## ⚠️ Disclaimer

This software is **experimental** and provided for **research and educational purposes only**. Not intended for production use. Use at your own risk. The authors assume no liability for any damages arising from the use of this software. See [LICENSE](LICENSE) for full terms (Apache 2.0).

---

## License

[Apache License 2.0](LICENSE) - Copyright 2026 AIXP Labs AIXP.dev | SoulBot.dev

---

Align Axiom 0: Human Sovereignty and Wellbeing. Version: SoulBot V1.0.0. www.soulbot.dev
