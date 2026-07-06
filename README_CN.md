# SoulBot

**基于 AISOP 协议和 AIAP 包系统的 AI Agent 框架**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-1263%20passed-brightgreen.svg)](#测试)

[English](README.md) | 中文文档

## SoulBot 是什么？

SoulBot 是一个基于 Python 的 AI Agent 框架，通过 CLI 子进程使用 ACP 协议（由 [soulacp](https://soulacp.dev) 驱动）连接 LLM —— **无需 API Key**。它引入了独特的架构：Agent 行为由 **AISOP 蓝图**（`.aisop.json`，Mermaid 流程图）定义，通过 **AIAP 包**（`*_aiap`）扩展能力，使 AI Agent 的行为变得确定性、可复现、可版本控制。

### 核心特性

- **免 API Key** — 通过 Claude Code / Gemini CLI / OpenCode CLI 子进程接入 LLM（由 [soulacp](https://soulacp.dev) 驱动）
- **多模型切换** — Claude、Gemini、OpenCode（Kimi 等），`.env` 一行切换
- **AISOP 协议** — Agent 行为由 `.aisop.json`（Mermaid 流程图）蓝图定义
- **AIAP 包系统** — 热插拔功能包（`*_aiap`），支持 AISOP 入口，即插即用扩展 Agent 能力
- **AISP 技能** — 单文件 AI 技能包（`*_aisp/`），携带机器强制的契约红线（违约即 HARD_FAIL 停机）与人审门 —— 同一引擎原生运行
- **Agent 组合** — 单 Agent、多 Agent 路由、Sequential / Parallel / Loop 工作流
- **工具系统** — Python 函数自动包装为 LLM 可调用工具
- **多通道接入** — 终端 CLI、Web Dev UI、Telegram Bot
- **流式输出** — SSE 打字机效果（Web + Telegram）

---

## 快速开始

### 前置条件

- Python 3.11+
- 至少安装一个 LLM CLI 工具：

| 工具 | 安装命令 | 登录 |
|------|----------|------|
| Claude Code | `npm install -g @anthropic-ai/claude-code` | `claude login` |
| Gemini CLI | `npm install -g @google/gemini-cli` | `gemini login` |
| OpenCode | `npm install -g opencode` | 免费模型，无需登录 |

> 💡 **推荐组合**: SoulBot + Claude Code CLI + Claude 旗舰模型。本项目主要在此组合下开发测试（已验证模型：Opus 4.8、Fable 5），首次使用建议从这里入手。

### 安装

```bash
git clone https://github.com/AIXP-Labs/SoulBot.git
cd SoulBot
pip install -e .
```

### 首次运行准备

运行前把示例配置重命名为 `.env`：

```bash
mv examples/simple/Soul_Agent/.env.example examples/simple/Soul_Agent/.env
```

打开新的 `.env`，选择 LLM 后端（Claude / Gemini / OpenCode）。

### 运行

```bash
# 简单模式（一键启动 Web Dev UI）
python start.py

# Web Dev UI（浏览器打开 http://127.0.0.1:2026）
soulbot web --agents-dir examples/simple

# 终端交互模式
soulbot run examples/simple/Soul_Agent

# Telegram Bot
soulbot telegram examples/simple/Soul_Agent
```

### 创建你自己的 Agent

```bash
soulbot create my_agent
```

生成以下文件：

```
my_agent/
├── agent.py                        # Agent 定义（双协议注册表消费者）
├── aiap/                           # AIAP 包（*_aiap/）+ aiap_list.py 注册表生成器
├── aisp/                           # AISP 技能（*_aisp/）+ aisp_list.py + _shared/
├── soulbot_execute_engine_aiap/    # AISOP 执行引擎（node/agent 派发、红线硬门）
├── soulbot_intent_classifier_aiap/ # 意图分类器包
└── heartbeat.aisop.json            # 定时任务蓝图
```

创建 `.env` 选择 LLM 后端（三层查找：agent 目录 → agents 目录 → SoulBot 根），然后运行：

```bash
soulbot run my_agent
```

---

## 架构

### AISOP + AIAP + AISP

SoulBot 引入了三个核心概念：

| 概念 | 说明 |
|------|------|
| **AISOP V1.0.0** | AI Standard Operating Procedure — 基于 JSON 的蓝图协议，通过 **Mermaid 流程图**定义 Agent 行为的控制流 |
| **AIAP 包** | AI Application Package — 热插拔功能模块（`*_aiap/`），支持 `main.aisop.json` 入口 |
| **AISP 技能** | AI Skill Protocol — 单文件技能（`*_aisp/aisp.aisop.json`），携带 `aisp_contract` 契约（non_negotiable 红线 + 人审门） |

**核心理念**：流程图是确定性执行路径（类似电路图），prompt 提供上下文和约束（类似元器件参数）。AISOP 用 Mermaid 语法（适合可视化）。这种分离使 Agent 行为可复现、可版本控制。

```
用户消息
    ↓
agent.py → _dynamic_instruction()
    ├── _SYSTEM_PROMPT（WHO — 运行时身份）
    ├── main.aisop.json（WHAT — 路由规则）
    └── [Available packages] — AIAP 程序 + AISP 技能
        （生成式注册表：aiap_list.json / aisp_list.json，源于 aiap/ 与 aisp/）
    ↓
LLM 按流程图执行：
    NLU[匹配意图] → Run[加载并执行 *_aiap/main.aisop.json
                        或 *_aisp/aisp.aisop.json]
    ↓
包内流程执行领域逻辑
    ↓
返回结果给用户
```

引擎是**协议无关的 AISOP 执行器**：经 `enforced_by` 绑定的契约红线是硬门（违约 → HARD_FAIL 停机、交人处置）；多候选路由歧义时**停下来询问用户**（公理 0），绝不静默代选。

### 治理域

AIAP 采用三方联邦信任模型：

- **aisop.dev**（种子层）：定义不可变的格式结构。
- **aiap.dev**（权威层）：定义可演进的治理规则。
- **soulbot.dev**（执行层）：物理执行 AISOP 代码的参考运行时引擎。

### 系统架构

```
用户入口
├── CLI Terminal     →  soulbot run <agent_dir>
├── Web Dev UI       →  soulbot web --agents-dir <dir>
├── API Server       →  soulbot api-server --agents-dir <dir>
└── Telegram Bot     →  soulbot telegram <agent_dir>
         ↓
Runner
├── Agent 树执行    →  LlmAgent / SequentialAgent / ParallelAgent / LoopAgent
├── AISOP 引擎       →  .aisop.json (Mermaid) → AIAP 包路由
├── 工具调用        →  FunctionTool / AgentTool / TransferToAgentTool
├── CMD 系统       →  嵌入式命令（定时任务等）
├── Session 管理    →  InMemory / SQLite + State delta
├── EventBus        →  发布/订阅 + 过滤 + 优先级
└── 流式输出        →  partial Event → SSE / Telegram 打字机效果
         ↓
模型层
├── ModelRegistry    →  正则匹配模型名 → 适配器选择
└── ACPLlm           →  soulacp 库
     (soulacp 把 CLI 子进程封装为 JSON-RPC 客户端；
      支持 claude-acp/* | gemini-acp/* | opencode-acp/*)
```

---

## Agent 开发

### 最简 Agent

```python
from soulbot.agents import LlmAgent

root_agent = LlmAgent(
    name="my_agent",
    model="claude-acp/sonnet",
    instruction="你是一个友好的助手。",
)
```

### 带工具的 Agent

```python
from soulbot.agents import LlmAgent

def get_weather(city: str) -> dict:
    """获取城市天气。"""
    return {"city": city, "temp": 25, "condition": "sunny"}

root_agent = LlmAgent(
    name="weather_agent",
    model="claude-acp/sonnet",
    instruction="你可以查询任何城市的天气。",
    tools=[get_weather],
)
```

函数自动包装为 LLM 工具：函数名 → 工具名，docstring → 描述，type hints → JSON Schema。

### 多 Agent 路由

```python
from soulbot.agents import LlmAgent

billing = LlmAgent(name="billing", model="claude-acp/sonnet",
                    description="处理账单问题",
                    instruction="你是账单专员。")

tech = LlmAgent(name="tech", model="claude-acp/sonnet",
                description="处理技术问题",
                instruction="你是技术支持。")

root_agent = LlmAgent(
    name="router",
    model="claude-acp/sonnet",
    instruction="根据用户问题转移到合适的专员。",
    sub_agents=[billing, tech],
)
```

### 工作流 Agent

```python
from soulbot.agents import LlmAgent, SequentialAgent, ParallelAgent, LoopAgent

# 顺序执行
root_agent = SequentialAgent(name="pipeline", sub_agents=[analyzer, responder])

# 并行执行
root_agent = ParallelAgent(name="parallel", sub_agents=[search, summarize])

# 循环执行
root_agent = LoopAgent(name="refiner", sub_agents=[draft, review], max_iterations=3)
```

### AISP 技能与 aisp_store

`examples/simple/aisp_store/` 随仓附带 6 个现成 AISP 技能（库存 —— **交付 ≠ 装机**）：

| 技能 | 展示什么 |
|---|---|
| `aisp_creator_evolution_aisp` v1.1.0 | 对话式创建/进化 AISP 技能（同时挂载于 `Soul_Agent/aisp/`，开箱可路由） |
| `webapp_testing_aisp` v1.3.0 | research 驱动的进化链（v1.0 → v1.3），Playwright 网页测试 |
| `mcp_builder_aisp` v2.0.0 | MCP 服务器构建 —— SemVer MAJOR（谓词翻转）活案例 |
| `yijing_aisp` | 易经占卜 —— 引擎原生运行的第一个 AISP 技能 |
| `random_draw_aisp` | 无偏随机抽签（CSPRNG，离线）—— 由创建器技能端到端造出 |
| `redline_breach_test_aisp` | **硬门探针**：故意违反自己的红线 —— 合规 runtime 必须在 `breach.step2` 停机。克隆后可亲手验证 |

- **装机**：把技能文件夹从 `aisp_store/` 复制到 `Soul_Agent/aisp/` —— 注册表（`aisp_list.json`）下一轮自动重生成（缺 cache 自愈）。
- **创建**：直接对话（如 `创建一个 AISP 技能:...`）—— 若多个创建器覆盖同一意图且未点名，路由会停下来问你（公理 0）；产物默认落 `aisp_store/`。
- **或用 Web UI**：`#/store` 页从 GitHub 浏览/下载/安装（版本感知 —— Up to date / Update / 本地更新时红字警告后才覆盖）；agent 设置页可从本地库一键装/卸技能。

---

## 配置

### .env 参考

```env
# LLM 后端（四选一设为 true）
CLAUDE_CLI=true
GEMINI_CLI=false
OPENCODE_CLI=false

# 模型名
CLAUDE_MODEL=claude-acp/sonnet
GEMINI_MODEL=gemini-acp/gemini-3-flash-preview
OPENCODE_MODEL=opencode-acp/opencode/gemini-3-flash-preview

# 行为控制
WORKSPACE_DIR=aiap            # AIAP 包目录
ENABLE_FALLBACK=false         # 失败自动切换备用模型
AUTO_APPROVE_PERMISSIONS=true # 自动批准 CLI 权限请求
SHOW_THOUGHTS=false           # 显示 AI 思考过程

# Telegram（可选）
TELEGRAM_BOT_TOKEN=
```

### 模型名格式

| 格式 | 说明 |
|------|------|
| `claude-acp/sonnet` | Claude Sonnet |
| `claude-acp/opus` | Claude Opus |
| `gemini-acp/gemini-3-flash-preview` | Gemini Flash |
| `opencode-acp/opencode/gemini-3-flash-preview` | OpenCode Gemini Flash |
| `opencode-acp/anthropic/claude-sonnet-4-5` | OpenCode 转接 Claude |

---

## CLI 命令

| 命令 | 说明 |
|------|------|
| `soulbot run <agent_path>` | 终端交互模式 |
| `soulbot web --agents-dir <dir>` | Web Dev UI + API Server |
| `soulbot api-server --agents-dir <dir>` | 仅 API Server（无 UI） |
| `soulbot telegram <agent_path>` | Telegram Bot |
| `soulbot create <name>` | 创建 Agent 项目脚手架 |

未安装时也可以用 `python -m soulbot` 替代 `soulbot`。

---

## Web Dev UI

```bash
soulbot web --agents-dir examples/simple
# 浏览器打开 http://127.0.0.1:2026
```

功能：Markdown 实时渲染、SSE 流式输出、Agent 切换、Session 管理、暗色主题、**Store 页**（从 GitHub 浏览/下载/安装 AIAP 程序**与 AISP 技能**，**版本感知**：Up to date / Update x→y / 本地更新时警告后安全覆盖）、**按 Agent 管理 AISP 技能**（设置页一键装/卸本地库技能；注册表下一轮自愈）。

### API 端点

| 路由 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/list-apps` | GET | 列出所有 Agent |
| `/apps/{name}` | GET | Agent 详情 |
| `/run` | POST | 同步执行 |
| `/run_sse` | POST | SSE 流式执行 |
| `/aiap-store/programs` | GET | 列出 GitHub 店的 AIAP 程序（带 `local_version`）|
| `/aisp-store/skills` | GET | 列出 GitHub 店的 AISP 技能（带 `local_version`）|
| `/aisp-store/download` / `install` | POST | 下载到本地库 / 安装到 agent（`overwrite` = 版本感知更新）|
| `/agents/{name}/aisps` | GET | agent 已挂载的 AISP 技能 |
| `/aisp-library` | GET | 本地 `aisp_store/` 库存 |

---

## Telegram Bot

1. 从 [@BotFather](https://t.me/BotFather) 获取 Bot Token
2. 在 `.env` 中添加 `TELEGRAM_BOT_TOKEN=你的Token`
3. 运行：`soulbot telegram examples/simple/Soul_Agent`

或 Web + Telegram 同时运行：`soulbot web --agents-dir examples/simple`

Bot 命令：`/start`、`/clear`、`/history`

特性：流式输出、Markdown 渲染、长消息自动分割、多 Agent 路由（InlineKeyboard 切换）。

---

## 定时任务

AI 自驱动定时调度系统 — AI 在回复中嵌入 `<!--SOULBOT_CMD:-->` 指令自动创建定时任务。

- 三种触发器：Once（一次性）/ Interval（间隔）/ Cron（定时）
- 跨 Agent 调度：Agent A 创建任务让 Agent B 执行
- AISOP payload：定时任务携带完整 AISOP V1.0.0 蓝图
- 持久化恢复：重启后自动恢复活跃任务

---

## 项目结构

```
SoulBot/
├── src/soulbot/              # 框架源码
│   ├── agents/               # Agent 系统 (LlmAgent, Sequential, Parallel, Loop)
│   ├── tools/                # 工具系统 (FunctionTool, AgentTool)
│   ├── models/               # ACPLlm + ModelRegistry（委托给 soulacp 库）
│   ├── runners/              # Runner (驱动 Agent 执行)
│   ├── sessions/             # Session (InMemory / SQLite)
│   ├── server/               # Web/API Server (FastAPI + SSE)
│   ├── connect/              # 通道连接器 (Telegram)
│   ├── commands/             # CMD 命令系统 (嵌入式命令)
│   ├── scheduler/            # 定时任务
│   ├── templates/            # Agent 脚手架模板
│   └── cli.py                # CLI 入口
├── examples/simple/          # 示例 Agent
│   └── Soul_Agent/        # 主 Agent（含 AIAP 包）
├── tests/                    # 1266 单元测试
├── docs/                     # 文档
└── pyproject.toml            # 项目配置
```

---

## 测试

```bash
# 全部单元测试
python -m pytest tests/ -q

# 指定模块
python -m pytest tests/test_agents/ -q

# E2E 测试（需要真实 CLI 登录）
python -m pytest tests/e2e/ -m live -q
```

---

## 安装选项

```bash
# 开发模式
pip install -e ".[dev]"

# 含 Telegram 支持
pip install -e ".[telegram]"

# 含 SQLite Session
pip install -e ".[sqlite]"

# 全部安装
pip install -e ".[dev,telegram,sqlite]"

# 从 GitHub 安装
pip install git+https://github.com/AIXP-Labs/SoulBot.git

# 一键运行（uv）
uvx --from git+https://github.com/AIXP-Labs/SoulBot.git soulbot web --agents-dir .
```

详细的安装与发布说明见 [INSTALL.md](INSTALL.md)。

---

## 文档

| 文档 | 说明 |
|------|------|
| [GUIDE.md](GUIDE.md) | 完整使用指南 |
| [INSTALL.md](INSTALL.md) | 安装、打包与发布 |
| [SECURITY.md](SECURITY.md) | 安全政策与漏洞报告（中英） |
| [CONTRIBUTING.md](CONTRIBUTING.md) / [CONTRIBUTING_CN.md](CONTRIBUTING_CN.md) | 贡献流程 |
| [GOVERNANCE.md](GOVERNANCE.md) | 项目治理与决策 |
| [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) | 社区行为准则（公理 0 对齐） |
| [CHANGELOG.md](CHANGELOG.md) | 发布历史含安全修复 |
| [docs/guide/01-function-call-guide.md](docs/guide/01-function-call-guide.md) | Function Call 开发指南 |
| [docs/guide/02-soulbot-cmd-guide.md](docs/guide/02-soulbot-cmd-guide.md) | SoulBot CMD 开发指南 |

---

## AIXP Labs [aixp.dev](https://aixp.dev)

AIXP Labs 开发并维护以下核心项目：

| 项目 | 描述 | 网站 |
|------|------|------|
| [HSAW](https://hsaw.dev) | 人类主权与福祉 —— Axiom 0 白皮书（基石） | hsaw.dev |
| [AIZP](https://aizp.dev) | AI Zenith-Zero Protocol —— 运行时行为对齐 | aizp.dev |
| [AILP](https://ailp.dev) | AI List Protocol —— agent 发现与能力广告 | ailp.dev |
| [AIVP](https://aivp.dev) | AI Value Protocol —— 国际商务、加密资产结算 | aivp.dev |
| [AIRP](https://airp.dev) | AI RMB Protocol —— 中国大陆商务、人民币持牌结算 | airp.dev |
| [AIBP](https://aibp.dev) | AI Bot Protocol —— 社交通信与信任 | aibp.dev |
| [AIAP](https://aiap.dev) | AI Application Protocol —— 治理与合规 | aiap.dev |
| [AISP](https://aisp.dev) | AI Skill Protocol —— 单文件技能包，机器强制的契约红线 | aisp.dev |
| [AISOP](https://aisop.dev) | AI Standard Operating Protocol —— 流程程序定义 | aisop.dev |
| [SoulSkill](https://soulskill.dev) | AISP 技能参考库 & 多 CLI 插件分发 | soulskill.dev |
| [SoulAgent](https://soulagent.dev) | 任何 CLI / SDK / IDE 直接调用的 drop-in AI agent | soulagent.dev |
| [SoulBot](https://soulbot.dev) | AI agent 运行时 & 自编排框架（定时、建 agent、agent 间通信） **（本项目）** | soulbot.dev |
| [SoulACP](https://soulacp.dev) | 适配库 —— 桥接 CLI 工具与 LLM 提供方 | soulacp.dev |

---

## ⚠️ 免责声明

本软件为**实验性**软件，仅供**研究和教育用途**。不适用于生产环境。使用风险由用户自行承担。作者对因使用本软件造成的任何损害不承担责任。完整条款见 [LICENSE](LICENSE)（Apache 2.0）。

---

## 许可证

[Apache License 2.0](LICENSE) - Copyright 2026 AIXP Labs AIXP.dev | SoulBot.dev

---

Align Axiom 0: Human Sovereignty and Wellbeing. Version: SoulBot V1.0.0. www.soulbot.dev
