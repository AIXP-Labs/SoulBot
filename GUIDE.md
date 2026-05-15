# SoulBot — AI Agent Framework 使用指南

> **1266 单元测试通过** | Python 3.11+ | 通过 CLI 子进程 (ACP) 接入 LLM，无需 API Key

```bash
pip install -e .
soulbot web --agents-dir examples/simple
```

---

## 一、简介

SoulBot 是一个 AI Agent 开发框架，核心特点：

- **免 API Key** — 通过 Claude Code / Gemini CLI / OpenCode 等 CLI 工具接入 LLM
- **多模型切换** — Claude / Gemini / OpenCode（Kimi 等），`.env` 一行切换
- **AISOP 驱动** — Agent 行为由 .aisop.json 蓝图定义，mermaid 流程图确定执行路径
- **AIAP 包系统** — 可插拔功能包（*_aiap），热插拔扩展 Agent 能力
- **Agent 组合** — 单 Agent、多 Agent 路由、Sequential / Parallel / Loop 工作流
- **工具系统** — Python 函数自动包装为 LLM 可调用工具
- **多通道接入** — 终端 CLI、Web Dev UI、Telegram Bot
- **流式输出** — SSE 打字机效果（Web + Telegram）

---

## 二、项目结构

```
SoulBot/
├── src/soulbot/              # 框架源码
│   ├── agents/               # Agent 系统 (LlmAgent, Sequential, Parallel, Loop)
│   ├── tools/                # 工具系统 (FunctionTool, AgentTool, TransferToAgentTool)
│   ├── models/               # 模型层 (ACPLlm, ModelRegistry)
│   ├── acp/                  # ACP 协议 (Claude/Gemini/OpenCode 客户端 + 连接池)
│   ├── runners/              # Runner (驱动 Agent 执行)
│   ├── sessions/             # Session (InMemory / SQLite + State delta)
│   ├── events/               # Event 数据模型
│   ├── bus/                  # EventBus (pub/sub + 过滤 + 优先级)
│   ├── connect/              # 通道连接器 (Telegram)
│   ├── server/               # Web/API Server (FastAPI + SSE + Dev UI)
│   ├── commands/             # CMD 命令系统 (嵌入式系统命令)
│   ├── plugins/              # 插件系统
│   ├── scheduler/            # 定时任务
│   ├── history/              # 对话历史
│   ├── conversation/         # 对话缓存
│   ├── artifacts/            # Artifact 版本存储
│   ├── tracking/             # Token 使用追踪
│   ├── templates/            # Agent 脚手架模板
│   ├── docs/                 # 内置文档 (STANDARD, schedule_guide, mcp_guide)
│   └── cli.py                # CLI 入口
├── examples/simple/          # 示例 Agent
│   └── SoulBot_Agent/        # 主 Agent (AISOP + AIAP 包路由)
│       ├── agent.py          # Agent 定义
│       ├── main.aisop.json   # AISOP 蓝图 (意图路由)
│       └── aiap/             # AIAP 功能包目录
│           ├── soulbot_chat_aiap/              # 聊天包
│           └── aiap_creator_evolution_aiap/     # Creator 包
├── tests/                    # 1266 单元测试
├── docs/                     # 设计文档与开发者指南
│   └── guide/
│       ├── 01-function-call-guide.md   # Function Call 开发指南
│       └── 02-soulbot-cmd-guide.md     # SoulBot CMD 开发指南
└── pyproject.toml            # 项目配置
```

---

## 三、安装

### 3.1 基础安装

```bash
cd /path/to/SoulBot

# 安装（开发模式）— 修改代码即时生效
pip install -e ".[dev]"

# 安装后即可全局使用 soulbot 命令
soulbot --help
```

> 详细的安装与发布说明见 [INSTALL.md](INSTALL.md)

### 3.2 可选依赖

```bash
# Telegram Bot 支持
pip install -e ".[telegram]"

# SQLite 持久化 Session
pip install -e ".[sqlite]"

# 全部安装
pip install -e ".[dev,telegram,sqlite]"
```

### 3.3 LLM CLI 工具（至少安装一个）

| 工具 | 安装命令 | 登录 |
|------|----------|------|
| Claude Code | `npm install -g @anthropic-ai/claude-code` | `claude login` |
| Gemini CLI | `npm install -g @google/gemini-cli` | `gemini login` |
| OpenCode | `npm install -g opencode` | 免费模型无需登录 |

---

## 四、快速开始

### 4.1 创建一个新 Agent

```bash
soulbot create my_agent
```

生成的文件：

```
my_agent/
├── agent.py          # Agent 定义 (含 AISOP Runtime)
├── main.aisop.json   # AISOP 蓝图 (意图路由到 AIAP 包)
├── .env              # 配置（模型选择等）
└── aiap/             # AIAP 功能包目录
    └── README.md     # 将 *_aiap 包放在此目录
```

### 4.2 配置 .env

编辑 `my_agent/.env`，选择一个 LLM 后端：

```env
# 方式 A：Claude（需要 claude login）
CLAUDE_CLI=true
GEMINI_CLI=false
OPENCODE_CLI=false
OPENCLAW_CLI=false
CLAUDE_MODEL=claude-acp/sonnet

# 方式 B：Gemini（需要 gemini login）
CLAUDE_CLI=false
GEMINI_CLI=true
OPENCODE_CLI=false
OPENCLAW_CLI=false
GEMINI_MODEL=gemini-acp/gemini-2.5-flash

# 方式 C：OpenCode（免费模型，无需登录）
CLAUDE_CLI=false
GEMINI_CLI=false
OPENCODE_CLI=true
OPENCLAW_CLI=false
OPENCODE_MODEL=opencode-acp/opencode/kimi-k2.5-free
```

### 4.3 运行

```bash
# 终端交互
soulbot run my_agent

# Web Dev UI（浏览器打开 http://127.0.0.1:2026）
soulbot web --agents-dir .

# Telegram Bot
soulbot telegram my_agent
```

---

## 五、CLI 命令

| 命令 | 说明 |
|------|------|
| `soulbot run <agent_path>` | 终端交互模式 |
| `soulbot web --agents-dir <dir>` | Web Dev UI + API Server |
| `soulbot api-server --agents-dir <dir>` | 仅 API Server（无 UI） |
| `soulbot telegram <agent_path>` | 单独运行 Telegram Bot |
| `soulbot create <name>` | 创建 Agent 项目脚手架 |

> 未安装时也可以用 `python -m soulbot` 替代 `soulbot`，功能完全一致。

### web 命令选项

```bash
soulbot web --agents-dir examples/simple --host 0.0.0.0 --port 8080

# Telegram 控制（默认：有 TELEGRAM_BOT_TOKEN 就自动启动）
soulbot web --agents-dir examples/simple --telegram       # 强制开启
soulbot web --agents-dir examples/simple --no-telegram    # 强制关闭
```

> `web` 命令会自动检测 `.env` 中的 `TELEGRAM_BOT_TOKEN`，如果有就同时启动 Web + Telegram。

---

## 六、Agent 开发

### 6.1 最简 Agent

```python
# agent.py
from soulbot.agents import LlmAgent

root_agent = LlmAgent(
    name="my_agent",
    model="claude-acp/sonnet",
    instruction="你是一个友好的助手。",
)
```

### 6.2 带工具的 Agent

```python
# agent.py
from soulbot.agents import LlmAgent

def get_weather(city: str) -> dict:
    """获取城市天气。"""
    return {"city": city, "temp": 25, "condition": "sunny"}

def calculate(expression: str) -> dict:
    """计算数学表达式。"""
    return {"result": eval(expression, {"__builtins__": {}})}

root_agent = LlmAgent(
    name="tool_agent",
    model="claude-acp/sonnet",
    instruction="你是一个助手，可以查天气和做计算。",
    tools=[get_weather, calculate],
)
```

FunctionTool 自动推断：

- 函数名 → 工具名
- docstring → 工具描述
- type hints → JSON Schema
- 支持 `str / int / float / bool / list / dict / Optional / Literal / Enum`

### 6.3 AISOP + AIAP 驱动的 Agent

```python
# agent.py — 通过 AISOP 蓝图和 AIAP 包驱动行为
import json, os
from pathlib import Path
from soulbot.agents import LlmAgent

_AGENT_DIR = Path(__file__).parent
_AIAP_DIR = (_AGENT_DIR / os.getenv("WORKSPACE_DIR", "aiap")).resolve()

_SYSTEM_PROMPT = (
    "You are the AISOP Runtime. "
    "Strictly follow the loaded AISOP file and RUN its mermaid flow. "
    "Always mirror User's exact language and script variant. "
    "IMPORTANT: Before responding, verify you followed the mermaid flow exactly. "
    "If not, regenerate."
)

def _dynamic_instruction(_ctx) -> str:
    parts = [_SYSTEM_PROMPT]
    # 加载 main.aisop.json ...
    # 发现 AIAP 包 ...
    return "\n\n".join(parts)

root_agent = LlmAgent(
    name="my_agent",
    model="claude-acp/sonnet",
    instruction=_dynamic_instruction,
)
```

AISOP 架构核心：
- **main.aisop.json** — Agent 蓝图，mermaid 定义执行路径
- **aiap/ 目录** — 可插拔功能包，每个 `*_aiap/main.aisop.json` 是包入口
- **mermaid = 电路图** — 确定性执行路径，prompt 提供约束参数

### 6.4 多 Agent 路由

```python
from soulbot.agents import LlmAgent

billing = LlmAgent(name="billing", model="claude-acp/sonnet",
                    description="处理账单问题",
                    instruction="你是账单专员。")

tech = LlmAgent(name="tech", model="claude-acp/sonnet",
                description="处理技术问题",
                instruction="你是技术支持。")

# 路由 Agent — LLM 自动决定转移到哪个子 Agent
root_agent = LlmAgent(
    name="router",
    model="claude-acp/sonnet",
    instruction="根据用户问题转移到合适的专员。",
    sub_agents=[billing, tech],
)
```

`sub_agents` 会自动注入 `TransferToAgentTool`，LLM 主动选择转移目标。

### 6.5 工作流 Agent

```python
from soulbot.agents import LlmAgent, SequentialAgent

analyzer = LlmAgent(
    name="analyzer", model="claude-acp/sonnet",
    instruction="分析用户输入，输出摘要。",
    output_key="analysis",  # 输出写入 session.state["analysis"]
)

responder = LlmAgent(
    name="responder", model="claude-acp/sonnet",
    instruction="根据分析结果回复用户。\n分析：{analysis}",
)

root_agent = SequentialAgent(
    name="pipeline",
    sub_agents=[analyzer, responder],  # 按顺序执行
)
```

其他工作流：

- `ParallelAgent` — 并发执行子 Agent
- `LoopAgent` — 循环执行（`max_iterations=10`）

### 6.6 回调 (Callbacks)

```python
root_agent = LlmAgent(
    name="agent",
    model="claude-acp/sonnet",
    instruction="...",
    before_agent_callback=lambda ctx: print("Agent 开始"),
    after_agent_callback=lambda ctx: print("Agent 结束"),
    before_model_callback=lambda ctx, req: print("调用 LLM"),
    after_model_callback=lambda ctx, resp: print("LLM 返回"),
)
```

### 6.7 State 共享

```python
# 在工具或回调中
ctx.session.state["key"] = "value"       # 当前 Session 作用域
ctx.session.state["app:key"] = "value"   # 跨所有用户/会话共享
ctx.session.state["user:key"] = "value"  # 跨该用户所有会话共享
ctx.session.state["temp:key"] = "value"  # 临时，不持久化

# 在 instruction 中引用
instruction = "用户偏好：{user_preference}"  # 自动从 state 插值
```

---

## 七、Telegram Bot

### 7.1 获取 Bot Token

1. 在 Telegram 搜索 `@BotFather`
2. 发送 `/newbot`，按提示创建
3. 拿到 Token（格式：`123456:ABC-DEF...`）

### 7.2 配置

在 Agent 的 `.env` 中添加：

```env
TELEGRAM_BOT_TOKEN=你的Token
```

### 7.3 运行

```bash
# 方式 A：单独运行 Telegram Bot
soulbot telegram examples/simple/SoulBot_Agent

# 方式 B：Web + Telegram 同时运行
soulbot web --agents-dir examples/simple
```

### 7.4 Bot 命令

| 命令 | 说明 |
|------|------|
| `/start` | 显示 Agent 信息 |
| `/clear` | 清除当前会话 |
| `/history` | 查看最近 10 条对话 |
| 直接发消息 | AI 对话（带打字机效果） |

### 7.5 特性

- 流式输出：Producer-Consumer 模式，每 0.5 秒更新消息（打字机效果）
- Markdown 渲染：`**bold**` `*italic*` `` `code` `` 等自动转为 Telegram HTML
- 长消息分割：超过 4000 字符自动分多条发送
- HTML 降级：渲染失败自动降为纯文本
- 多 Agent 路由 — /agents + InlineKeyboard 切换，支持多个 Agent 共享一个 Bot Token

---

## 八、定时任务（Schedule）

- AI 自驱动定时调度 — AI 在回复中嵌入 `<!--SOULBOT_CMD:-->` 指令自动创建定时任务
- 三种触发器 — OnceTrigger（一次性）/ IntervalTrigger（间隔）/ CronTrigger（定时）
- 跨 Agent 调度 — `from_agent`/`to_agent` 支持 Agent A 创建任务让 Agent B 执行
- AISOP payload — 定时任务携带完整 AISOP V1.0.0 蓝图
- 持久化恢复 — `.soulbot_schedules.json` 原子写入，重启后自动恢复活跃任务
- EventBus 回传 — 任务执行结果通过 `schedule.executed` 事件回传 Telegram/Web

---

## 九、Web Dev UI

```bash
soulbot web --agents-dir examples/simple
# 浏览器打开 http://127.0.0.1:2026
```

功能：

- Markdown 实时渲染（marked.js）
- SSE 打字机效果
- Agent 切换下拉框
- Session 列表 / State 面板
- 暗色主题

### API 端点

| 路由 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/list-apps` | GET | 列出所有 Agent |
| `/apps/{name}` | GET | Agent 详情 |
| `/run` | POST | 同步执行 |
| `/run_sse` | POST | SSE 流式执行 |

---

## 十、.env 配置参考

```env
# ─── Telegram ───
TELEGRAM_BOT_TOKEN=           # Bot Token（留空则不启动 Telegram）

# ─── LLM 后端选择（四选一设为 true）───
OPENCODE_CLI=false            # OpenCode CLI
CLAUDE_CLI=true               # Claude Code CLI
GEMINI_CLI=false              # Gemini CLI
OPENCLAW_CLI=false            # OpenClaw Gateway

# ─── 模型配置 ───
OPENCODE_MODEL=opencode-acp/opencode/kimi-k2.5-free
CLAUDE_MODEL=claude-acp/sonnet
GEMINI_MODEL=gemini-acp/gemini-2.5-flash
OPENCLAW_MODEL=openclaw/default

# ─── OpenClaw Gateway ───
OPENCLAW_URL=ws://127.0.0.1:18789
OPENCLAW_TOKEN=

# ─── 行为控制 ───
ENABLE_FALLBACK=false         # 失败自动切换备用模型
AUTO_APPROVE_PERMISSIONS=true # 自动批准 CLI 权限请求
SHOW_THOUGHTS=false           # 显示 AI 思考过程
WORKSPACE_DIR=aiap            # AIAP 包目录（相对于 Agent 目录）
```

---

## 十一、模型名格式

| 格式 | 说明 |
|------|------|
| `claude-acp/sonnet` | Claude Sonnet |
| `claude-acp/opus` | Claude Opus |
| `gemini-acp/gemini-2.5-flash` | Gemini Flash |
| `opencode-acp/opencode/kimi-k2.5-free` | OpenCode 免费 Kimi |
| `opencode-acp/anthropic/claude-sonnet-4-5` | OpenCode 转接 Claude |
| `openclaw/default` | OpenClaw 默认模型 |

模型名由 `ModelRegistry` 正则匹配到对应 ACP 客户端。

---

## 十二、运行测试

```bash
# 全部单元测试（1266 tests）
python -m pytest tests/ -q

# 指定模块
python -m pytest tests/test_agents/ -q
python -m pytest tests/test_connect/ -q

# E2E 测试（需要真实 CLI 登录）
python -m pytest tests/e2e/ -m live -q
```

---

## 十三、AISOP + AIAP 架构

### 核心概念

| 概念 | 说明 |
|------|------|
| **AISOP V1.0.0** | AI Standard Operating Procedure — Agent 行为蓝图协议 |
| **main.aisop.json** | Agent 主蓝图，定义 mermaid 执行流程和 NLU 路由 |
| **AIAP 包** | 功能包目录（`*_aiap/`），每个包含 `main.aisop.json` 入口 |
| **mermaid** | 执行路径（电路图），确定性流程，不靠 prompt 猜测 |

### Agent 执行流程

```
用户消息
    ↓
agent.py _dynamic_instruction()
    ├── 注入 _SYSTEM_PROMPT (WHO)
    ├── 注入 main.aisop.json (WHAT — 路由规则)
    └── 注入 [Available AIAP packages] (可用包列表)
    ↓
LLM 按 mermaid 流程执行：
    NLU[匹配意图到 AIAP 包] → Run[读取并执行 *_aiap/main.aisop.json]
    ↓
AIAP 包内的 mermaid 继续执行子流程
    ↓
返回结果给用户
```

---

## 十四、架构图

```
用户入口
├── CLI Terminal     →  soulbot run <agent_dir>
├── Web Dev UI       →  soulbot web --agents-dir <dir>
├── API Server       →  soulbot api-server --agents-dir <dir>
└── Telegram Bot     →  soulbot telegram <agent_dir>

         ↓

Runner (runners/runner.py)
├── Agent 树执行    →  LlmAgent / SequentialAgent / ParallelAgent / LoopAgent
├── AISOP 驱动     →  main.aisop.json → mermaid 流程 → AIAP 包路由
├── 工具调用        →  FunctionTool / AgentTool / TransferToAgentTool
├── CMD 系统       →  <!--SOULBOT_CMD:--> 嵌入式命令（定时任务等）
├── Session 管理    →  InMemory / SQLite + State delta
├── EventBus        →  pub/sub + 过滤 + 优先级
└── 流式输出        →  partial Event → SSE / Telegram 打字机效果

         ↓

模型层 (models/)
├── ModelRegistry    →  正则匹配模型名 → 适配器
└── ACPLlm           →  CLI 子进程 JSON-RPC
     ├── ClaudeACPClient    (claude-acp/*)
     ├── GeminiACPClient    (gemini-acp/*)
     ├── OpenCodeACPClient  (opencode-acp/*)
     └── OpenClawClient     (openclaw/*)
```
