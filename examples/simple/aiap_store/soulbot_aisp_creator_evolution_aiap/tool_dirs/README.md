# AIAP Creator Tool Directories

This directory prepares for future MCP (Model Context Protocol) Server integration per Pattern G and I13 compliance.

## Purpose

Tool directories enable:
- Bundled tool distribution alongside AIAP programs
- MCP ecosystem integration for standardized tool exposure
- Simplified dependency management for external tools
- Runtime-agnostic tool packaging

## Structure

```
tool_dirs/
├── README.md (this file)
├── manifest.json (tool metadata and MCP integration config)
└── [future tool implementations]
```

## MCP Integration

When MCP Server support is implemented, this directory will contain:
- Tool implementation stubs (Python/TypeScript/Go/Rust/Shell)
- MCP adapter for stdio JSON-RPC 2.0 bridge
- Dependency declarations (requirements.txt, package.json, etc.)
- Interface definitions (CLI args or JSON stdin/stdout)

## Security

All tools in this directory are subject to:
- I13 compliance checks (dependency pinning, network declarations, file scope)
- Trust level enforcement from parent AIAP (trust_level=4)
- Governance hash verification
- Permission auditing per aiap_tools/ security requirements

## Version

Introduced in AIAP Creator v2.23.0 as preparation infrastructure.
Tool implementations will be added in future versions based on ecosystem adoption.
