# AIAP Directory

This directory holds **agent-private AIAP packages** scanned at startup by `agent.py`'s `_get_aiap_registry()`.

## How to populate

Drop AIAP package directories here (each ending in `_aiap`):

```
aiap/
├── soulbot_chat_aiap/
│   ├── main.aisop.json
│   ├── AIAP.md
│   └── ...
├── my_custom_aiap/
│   ├── main.aisop.json
│   └── ...
```

## What gets injected into the LLM

- `[AIAP Directory]` system prompt block points here
- `[Available AIAP packages]` lists each `*_aiap` subdirectory with `loading_mode`, `entry`, `workspace_dir`
- LLM matches user request to a package and dispatches it via the engine
