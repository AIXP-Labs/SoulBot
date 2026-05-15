# 02 — SOULBOT CMD 使用说明

## 概述

SOULBOT CMD 是嵌入在 LLM 文本响应中的系统级命令机制。LLM 在回复中嵌入 `<!--SOULBOT_CMD:{...}-->`，框架解析并执行命令，将结果作为 `function_response` 反馈给 LLM。

与 Function Call 的核心区别：Function Call 是 LLM API 的结构化字段；CMD 是**文本内容中的隐藏标记**，对用户不可见。

## 执行流程

```
LLM 返回文本（含 <!--SOULBOT_CMD:...-->）
    ↓
Step 6: 检查 function_calls — 无
    ↓
Step 6.5: 检查 SOULBOT_CMD
    ↓
parse_commands(text) → commands[], cleaned_text
    ↓
yield cleaned_text（用户看到的干净文本）
    ↓
_inject_cmd_routing() — 自动注入 from_agent 等路由信息
    ↓
cmd_executor.execute_all(commands, context)
  └─ 逐条执行 → execute(cmd) → service.action(**params)
    ↓
构建 function_response event（格式同 Function Call）
    ↓
yield function_response → continue（回到 while 循环）
    ↓
LLM 看到结果，继续推理
```

> Function Call（Step 6）优先级高于 CMD（Step 6.5）。两者不会同时触发。

## CMD 格式

```
<!--SOULBOT_CMD:{"service":"<service>","action":"<action>", ...params}-->
```

嵌入在 LLM 回复文本中，用户不可见（解析后自动剥离）。

## 解析器

**文件：** `src/soulbot/commands/parser.py`

```python
from soulbot.commands.parser import parse_commands

commands, cleaned_text = parse_commands(raw_text)
# commands: list[ParsedCommand]
# cleaned_text: 去掉所有 CMD 标记后的文本
```

**ParsedCommand 结构：**

```python
@dataclass
class ParsedCommand:
    service: str   # "service" 字段（pop 出）
    action: str    # "action" 字段（pop 出）
    params: dict   # 剩余所有字段
    raw: str       # 原始 <!--SOULBOT_CMD:...--> 文本
```

**解析特性：**
- 括号平衡扫描（`_find_json_end`）— JSON 字符串内的 `-->` 不会干扰
- 支持一段文本中的多个 CMD
- 解析失败的 CMD 被 regex 兜底清除
- 三个以上连续换行合并为两个

## 执行器

**文件：** `src/soulbot/commands/executor.py`

### 服务注册

```python
from soulbot.commands.executor import CommandExecutor

executor = CommandExecutor()
executor.register_service("schedule", ScheduleService(...))
executor.register_service("math", MathService())
```

服务是普通 Python 对象，方法名即 action 名。支持 sync 和 async 方法。

### 注入到 Runner

```python
from soulbot.runners import Runner

runner = Runner(
    agent=my_agent,
    app_name="my_app",
    session_service=session_service,
    cmd_executor=executor,  # 注入
)
```

`Runner` → `InvocationContext.cmd_executor` → `LlmAgent` 读取。
`cmd_executor` 为 `None` 时 CMD 处理完全跳过。

### 执行流程

```python
# execute() 单条命令
async def execute(self, cmd, context=None):
    service = self._services[cmd.service]    # 查找服务
    method = getattr(service, cmd.action)     # 查找方法

    params = dict(cmd.params)
    timeout = params.pop("timeout", None)     # 提取 timeout（不传给方法）

    if asyncio.iscoroutinefunction(method):
        coro = method(**params)
        if timeout:
            result = await asyncio.wait_for(coro, timeout=timeout)
        else:
            result = await coro
    else:
        result = method(**params)

    return {"success": True, "data": result}
```

```python
# execute_all() 批量顺序执行
async def execute_all(self, commands, context=None):
    for cmd in commands:
        # 安全检查：阻止嵌套调度
        if context.get("type") == "scheduled" and cmd.service == "schedule":
            → {"success": False, "error": "Nested scheduling blocked"}
        result = await self.execute(cmd, context)
```

### 返回值格式

| 情况 | 返回 |
|------|------|
| 成功 | `{"success": True, "data": <方法返回值>}` |
| 服务未找到 | `{"success": False, "error": "Unknown service: xxx"}` |
| 方法未找到 | `{"success": False, "error": "Unknown action: xxx.yyy"}` |
| 执行异常 | `{"success": False, "error": "<异常信息>"}` |
| 超时 | `{"success": False, "error": "Timed out after Xs"}` |

## 结果反馈

CMD 结果以 `FunctionResponse` 格式反馈给 LLM（与 Function Call 相同格式）：

```python
Part(function_response=FunctionResponse(
    name="schedule.add",          # service.action
    response={"entry_id": "...", "status": "active"},
))
```

LLM 在下一轮看到：`Tool result (schedule.add): {"entry_id": "...", "status": "active"}`

## 路由自动注入

**文件：** `src/soulbot/agents/llm_agent.py` L445 `_inject_cmd_routing()`

对 `schedule.add` 命令，框架自动注入：
- `from_agent` — 当前 agent 名
- `to_agent` — 默认为 `from_agent`（如果未指定）
- `origin_channel` — 来自 session
- `origin_user` — 来自 session

LLM 不需要在 CMD 中写 `from_agent`，框架自动处理。

## Timeout 机制

### 两层 timeout

| 层级 | 设置方式 | 作用范围 |
|------|----------|----------|
| Per-CMD | CMD payload 中 `"timeout": 5` | 单条命令 |
| 全局 | `RunConfig(cmd_timeout=10.0)` | `execute_all` 整体 |

### Per-CMD timeout

LLM 在 CMD JSON 中写 `"timeout": 5`：

```
<!--SOULBOT_CMD:{"service":"schedule","action":"add","timeout":5,"trigger":{...}}-->
```

`executor.execute()` 自动 pop `timeout`（不传给 service 方法），用 `asyncio.wait_for` 包装。

### 全局 timeout

```python
runner.run(
    user_id="u1", session_id="s1", message="hello",
    run_config=RunConfig(cmd_timeout=10.0),
)
```

包装 `execute_all()` 整体。超时时所有命令返回：

```python
{"success": False, "error": "Timed out after 10.0s"}
```

### 两层共存

Per-CMD timeout 对单条命令生效；RunConfig.cmd_timeout 对整个批次生效。两者独立工作。

## 安全机制

### 嵌套调度阻止

当任务处于 scheduled 执行上下文中时，`schedule` 服务的 CMD 被阻止：

```python
# execute_all() 中
if context.get("type") == "scheduled" and cmd.service == "schedule":
    return {"success": False, "error": "Nested scheduling blocked"}
```

防止定时任务无限创建新的定时任务。

### 上下文传递

`ScheduleService._execute_task()` 执行时注入上下文：

```python
context = {
    "type": "scheduled",
    "entry_id": entry.id,
    "origin_channel": entry.origin_channel,
    "origin_user": entry.origin_user,
}
```

通过 `RunConfig.context` → `execute_all(context=...)` 传递。

## 创建自定义服务

```python
class MathService:
    """同步方法示例"""
    def add(self, a: int, b: int) -> int:
        return a + b

    def multiply(self, a: int, b: int) -> int:
        return a * b

class WeatherService:
    """异步方法示例"""
    async def fetch(self, city: str) -> dict:
        data = await http_client.get(f"/weather/{city}")
        return {"city": city, "temp": data["temp"]}

executor = CommandExecutor()
executor.register_service("math", MathService())
executor.register_service("weather", WeatherService())
```

对应的 CMD：

```
<!--SOULBOT_CMD:{"service":"math","action":"add","a":3,"b":4}-->
<!--SOULBOT_CMD:{"service":"weather","action":"fetch","timeout":5,"city":"Tokyo"}-->
```

## CMD vs Function Call 对比

| 方面 | Function Call | SOULBOT CMD |
|------|-------------|-------------|
| 载体 | LLM API 结构化字段 | 文本中的 HTML 注释标记 |
| 发现方式 | LLM 通过工具 schema 知道有哪些工具 | LLM 通过 system prompt/guide 学习格式 |
| 解析 | LLM API / SDK 处理 | `parse_commands()` 应用层解析 |
| 执行方式 | `asyncio.gather` **并行** | `execute_all` **顺序** |
| 结果关联 | `FunctionResponse.id` 匹配 `FunctionCall.id` | 无 call ID |
| Callbacks | `before_tool_callback` / `after_tool_callback` | 无 |
| Timeout | `tool.timeout` 或 `RunConfig.tool_timeout` | CMD payload `timeout` 或 `RunConfig.cmd_timeout` |
| 安全规则 | 无（应用层自行处理） | 嵌套调度阻止 |
| 优先级 | Step 6 — **优先** | Step 6.5 — 仅在无 function_call 时检查 |
| 对用户 | 不可见（直到最终文本） | CMD 标记剥离后用户看到干净文本 |
| 反馈格式 | `FunctionResponse`（role="user"） | **相同** `FunctionResponse`（role="user"） |

> 两者反馈格式相同，LLM 看到的都是 `Tool result (name): {...}`，处理逻辑一致。

## EventBus 事件

| 事件 | 时机 | 数据 |
|------|------|------|
| `cmd.executed` | 每条 CMD 执行后 | `{"service": "...", "action": "...", "success": bool}` |

## 现有服务

| 服务 | 文件 | Actions |
|------|------|---------|
| `schedule` | `scheduler/schedule_service.py` | `add`, `list`, `get`, `cancel`, `pause`, `resume`, `modify` |

> 详细用法见 `src/soulbot/docs/schedule_guide.md`
