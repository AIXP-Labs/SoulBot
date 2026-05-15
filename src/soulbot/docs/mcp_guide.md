# MCP Server Configuration Guide

MCP (Model Context Protocol) servers extend agent capabilities by providing
additional tools (database access, web search, file I/O, APIs, etc.).

SoulBot agents communicate with CLI backends (Claude Code, Gemini CLI, OpenCode)
via ACP. Each CLI session can be configured with MCP servers at session creation
time through the `mcpServers` parameter.

---

## Configuration Format

MCP servers are specified as a list of objects in `session/new`:

```json
{
  "mcpServers": [
    {
      "name": "server-name",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-package", "/path"],
      "env": {
        "API_KEY": "your-key"
      }
    }
  ]
}
```

### Fields

| Field     | Type       | Required | Description                                  |
|-----------|------------|----------|----------------------------------------------|
| `name`    | string     | Yes      | Unique identifier for this server            |
| `command` | string     | Yes      | Executable to launch (e.g. `npx`, `node`, `python`) |
| `args`    | string[]   | No       | Command-line arguments                       |
| `env`     | object     | No       | Extra environment variables for the process  |

---

## Common MCP Server Examples

### Filesystem Access

```json
{
  "name": "filesystem",
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-filesystem", "/allowed/path"]
}
```

### Web Search (Brave)

```json
{
  "name": "brave-search",
  "command": "npx",
  "args": ["-y", "@anthropic-ai/mcp-server-brave-search"],
  "env": {
    "BRAVE_API_KEY": "your-api-key"
  }
}
```

### SQLite Database

```json
{
  "name": "sqlite",
  "command": "npx",
  "args": ["-y", "@anthropic-ai/mcp-server-sqlite", "/path/to/database.db"]
}
```

### GitHub

```json
{
  "name": "github",
  "command": "npx",
  "args": ["-y", "@anthropic-ai/mcp-server-github"],
  "env": {
    "GITHUB_TOKEN": "ghp_xxx"
  }
}
```

### Custom Python MCP Server

```json
{
  "name": "custom-tools",
  "command": "python",
  "args": ["-m", "my_mcp_server"],
  "env": {}
}
```

---

## Where to Configure

### Option 1: Per-Agent (agent.py)

Set MCP servers in the agent's configuration or environment so they are passed
to the ACP client during `session/new`. Currently SoulBot passes `mcpServers: []`
by default in all ACP clients (`claude_client.py`, `gemini_client.py`,
`opencode_client.py`).

### Option 2: CLI-Level

Configure MCP servers in the CLI's own config file:

- **Claude Code**: `~/.claude/claude_desktop_config.json` → `mcpServers` section
- **Gemini CLI**: `~/.gemini/settings.json` → `mcpServers` section

CLI-level servers are always available regardless of SoulBot config.

---

## Notes

- MCP servers run as child processes of the CLI backend, not SoulBot itself.
- Each server provides tools that the LLM can discover and invoke autonomously.
- Server processes are started when the session begins and stopped when it ends.
- Keep the number of MCP servers minimal to reduce startup latency.
- Store API keys in environment variables, not in code or config files.
