# 01 — Function Call (Tool) 使用说明

## 概述

Function Call 是 LLM 调用外部工具的标准机制。LLM 在响应中返回结构化的 `function_call`，框架执行对应的工具函数，将结果作为 `function_response` 反馈给 LLM，LLM 根据结果继续推理。

## 执行流程

```
用户消息
    ↓
LlmAgent._run_async_impl() while 循环
    ↓
1. _build_request() — 构建 LlmRequest（含工具 schema）
    ↓
2. before_model_callback — 可短路返回
    ↓
3. LLM 调用 — llm.generate_content_async()
    ↓
4. after_model_callback — 可修改响应
    ↓
5. _response_to_event() — 转为 Event
    ↓
6. 检查 function_calls
   ├── 有 → _handle_function_calls() → yield function_response → continue（回到 1）
   └── 无 → 进入 6.5/7
    ↓
7. yield 最终文本响应 → break
```

## 定义工具

### 方式 A：普通函数（自动包装为 FunctionTool）

最简单的方式。传入普通函数，框架自动推断 schema：

```python
async def search_web(query: str, max_results: int = 5) -> list[str]:
    """Search the web and return URLs.

    :param query: The search query string
    :param max_results: Maximum number of results to return
    """
    return ["https://example.com"]

agent = LlmAgent(
    name="researcher",
    model="gpt-4o-mini",
    tools=[search_web],  # 自动包装为 FunctionTool
)
```

自动生成的 schema：

```json
{
  "name": "search_web",
  "description": "Search the web and return URLs.",
  "parameters": {
    "type": "object",
    "properties": {
      "query": {"type": "string", "description": "The search query string"},
      "max_results": {"type": "integer", "description": "Maximum number of results to return"}
    },
    "required": ["query"]
  }
}
```

**支持的类型映射：**

| Python 类型 | JSON Schema 类型 |
|-------------|-----------------|
| `str` | `string` |
| `int` | `integer` |
| `float` | `number` |
| `bool` | `boolean` |
| `list[T]` | `array` (items: T) |
| `dict` | `object` |
| `Optional[T]` | 解包为 T，非 required |
| Pydantic `BaseModel` | 完整 object schema（自动 coerce） |

**Docstring 参数描述支持：**
- Sphinx 格式：`:param name: desc`
- Google 格式：`name: desc`

### 方式 B：继承 BaseTool（完全控制）

需要自定义 schema 逻辑或复杂初始化时使用：

```python
from soulbot.tools.base_tool import BaseTool

class DatabaseQueryTool(BaseTool):
    def __init__(self, db_connection, *, timeout: float = 10.0):
        super().__init__(
            name="query_database",
            description="Execute a SQL query against the database.",
            timeout=timeout,
        )
        self.db = db_connection

    def get_declaration(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "SQL query"},
                    "limit": {"type": "integer", "description": "Max rows"},
                },
                "required": ["sql"],
            },
        }

    async def run_async(self, *, args: dict, tool_context) -> Any:
        sql = args["sql"]
        limit = args.get("limit", 100)
        rows = await self.db.execute(sql, limit=limit)
        return {"rows": rows, "count": len(rows)}

agent = LlmAgent(
    name="analyst",
    model="gpt-4o-mini",
    tools=[DatabaseQueryTool(db_conn, timeout=30.0)],
)
```

## 注册工具

`LlmAgent.tools` 接受混合列表 — `BaseTool` 子类、普通函数、async 函数均可：

```python
agent = LlmAgent(
    name="assistant",
    model="gpt-4o-mini",
    tools=[search_web, DatabaseQueryTool(db), my_sync_function],
)
```

`model_post_init` 自动调用 `_ensure_tool()` 将 callable 包装为 `FunctionTool`。

当 agent 有 `sub_agents` 时，`_resolve_tools()` 自动注入 `TransferToAgentTool`。

## 工具执行

### 并行执行

所有 function_call 通过 `asyncio.gather` **并行执行**：

```python
# llm_agent.py L467
async def _handle_function_calls(self, ctx, llm_request, function_calls):
    tasks = [self._run_single_tool(ctx, llm_request, fc) for fc in function_calls]
    results = await asyncio.gather(*tasks, return_exceptions=True)
```

### 单个工具执行流程

```python
# llm_agent.py L514
async def _run_single_tool(self, ctx, llm_request, fc):
    # 1. 查找工具
    tool = llm_request.tools_dict.get(fc.name)

    # 2. before_tool_callback（可短路）
    if self.before_tool_callback:
        override = self.before_tool_callback(ctx, fc.name, args)

    # 3. 创建 ToolContext
    tool_ctx = Context(invocation_context=ctx, ...)

    # 4. 执行（含 timeout）
    _tool_timeout = tool.timeout or ctx.run_config.tool_timeout
    if _tool_timeout:
        result = await asyncio.wait_for(
            tool.run_async(args=args, tool_context=tool_ctx),
            timeout=_tool_timeout,
        )
    else:
        result = await tool.run_async(args=args, tool_context=tool_ctx)

    # 5. commit state delta
    tool_ctx.commit_state_delta()

    # 6. after_tool_callback（可修改结果）
    return result, tool_ctx.actions
```

### 结果反馈格式

工具结果作为 `FunctionResponse` 反馈，role 为 `"user"`：

```python
Part(function_response=FunctionResponse(
    name="search_web",            # 匹配 FunctionCall.name
    response={"result": [...]},   # 工具返回值（非 dict 自动包装）
    id="fc-xxx",                  # 匹配 FunctionCall.id
))
```

LLM 在下一轮看到：`Tool result (search_web): {"result": [...]}`

## ToolContext

工具函数可以通过 `tool_context` 参数访问运行时上下文：

```python
async def my_tool(query: str, tool_context: ToolContext) -> dict:
    # 读写 session state
    tool_context.state["last_query"] = query
    prev = tool_context.state.get("history", [])

    # 触发 agent 转移
    tool_context.actions.transfer_to_agent = "specialist_agent"

    # 信号 LoopAgent 退出
    tool_context.actions.escalate = True

    # 读取信息
    agent_name = tool_context.agent_name
    session = tool_context.session
    invocation_id = tool_context.invocation_id

    return {"result": "done"}
```

> `tool_context` 参数自动注入，不会出现在 LLM 的工具 schema 中。

| 能力 | 用法 |
|------|------|
| 读写 session state | `tool_context.state["key"] = value` |
| 触发 agent 转移 | `tool_context.actions.transfer_to_agent = "name"` |
| 信号循环退出 | `tool_context.actions.escalate = True` |
| 当前 agent 名 | `tool_context.agent_name` |
| 当前 session | `tool_context.session` |
| 调用 ID | `tool_context.invocation_id` |
| 原始 InvocationContext | `tool_context.invocation_context` |

## Timeout 机制

### 优先级

```
tool.timeout（per-tool）> RunConfig.tool_timeout（全局）> None（无限制）
```

### 设置方式

**全局（RunConfig）：**

```python
events = runner.run(
    user_id="u1", session_id="s1", message="hello",
    run_config=RunConfig(tool_timeout=10.0),
)
```

**单个工具：**

```python
tool = FunctionTool(slow_function)
tool.timeout = 5.0  # 覆盖全局

# 或 BaseTool 子类
class MyTool(BaseTool):
    def __init__(self):
        super().__init__(name="my_tool", timeout=5.0)
```

### 超时行为

超时返回 error dict，LLM 可以在下一轮看到并处理：

```
Tool result (slow_tool): {"error": "Tool 'slow_tool' timed out after 5.0s"}
```

LLM 可以：选择重试、换一个方案、告知用户。

## Callbacks

| Callback | 位置 | 作用 |
|----------|------|------|
| `before_model_callback` | LLM 调用前 | 可短路返回，跳过 LLM |
| `after_model_callback` | LLM 调用后 | 可修改 LLM 响应 |
| `before_tool_callback` | 工具执行前 | 可短路返回固定结果 |
| `after_tool_callback` | 工具执行后 | 可修改工具结果 |

```python
agent = LlmAgent(
    name="my_agent",
    model="gpt-4o-mini",
    tools=[my_tool],
    before_tool_callback=lambda ctx, name, args: {"blocked": True} if name == "dangerous" else None,
    after_tool_callback=lambda ctx, name, result: {**result, "audited": True},
)
```

## 内置工具

| 工具 | 文件 | 说明 |
|------|------|------|
| `FunctionTool` | `tools/function_tool.py` | 自动包装普通函数 |
| `AgentTool` | `tools/agent_tool.py` | 将 agent 包装为工具（单参数 `request`） |
| `TransferToAgentTool` | `tools/transfer_to_agent_tool.py` | 自动注入，用于 agent 转移 |
| `history_tool` | `tools/history_tool.py` | 搜索历史记录工具（工厂函数） |

## EventBus 事件

| 事件 | 时机 | 数据 |
|------|------|------|
| `tool.call` | 工具调用前 | `{"tool": name, "args": {...}}` |
| `tool.result` | 工具返回后 | `{"tool": name, "response": {...}}` |
