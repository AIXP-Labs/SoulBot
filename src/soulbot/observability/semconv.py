"""Centralized OTel GenAI semconv + SoulBot ACP extension field names.

SoulBot uses ACP (Agent Communication Protocol) over stdio to CLI tools
(Claude Code / Gemini CLI / OpenCode / OpenClaw / Cursor), NOT the Anthropic
Python SDK. Fields here reflect that architecture:

- gen_ai.*        : OTel standard (still Development status as of 2026-Q1)
- acp.*           : SoulBot ACP-specific (pool / session / provider / retry)
- soulbot.*       : SoulBot self-extension (AIAP / node / turn)
- METRIC_*        : histogram names for MeterProvider views

Importing from this module (vs hard-coding strings) makes future semconv
renames (when gen_ai.* stabilizes) a one-file change.

Reference: Doc 12 v2.3 §5.1
"""
from __future__ import annotations


# --- OTel GenAI semconv (still Development) ---
GEN_AI_OPERATION_NAME = "gen_ai.operation.name"
GEN_AI_AGENT_NAME = "gen_ai.agent.name"
GEN_AI_PROVIDER_NAME = "gen_ai.provider.name"  # e.g. "anthropic" / "google" / "xai"
GEN_AI_REQUEST_MODEL = "gen_ai.request.model"  # ACP model: "claude-acp/sonnet-4.5"
GEN_AI_CONVERSATION_ID = "gen_ai.conversation.id"  # maps to SoulBot session_id

# Estimated tokens (ACP CLI mode has no precise usage field)
GEN_AI_USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"  # estimated, ≈ len(prompt)/4
GEN_AI_USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"  # estimated, ≈ len(output)/4
GEN_AI_SERVER_TTFT = "gen_ai.server.time_to_first_token"  # ACP first chunk (streaming)

# Content (opt-in, default disabled)
GEN_AI_INPUT_MESSAGES = "gen_ai.input.messages"
GEN_AI_OUTPUT_MESSAGES = "gen_ai.output.messages"

# --- SoulBot ACP-specific ---
ACP_PROVIDER_NAME = "acp.provider.name"  # "claude"|"gemini"|"opencode"|"openclaw"|"cursor"
ACP_SESSION_ID = "acp.session.id"  # soulacp ACP session id (subprocess lifecycle)
ACP_SESSION_ROTATED = "acp.session.rotated"  # bool, rotated this call
ACP_SESSION_RESTORED_FROM_STORE = "acp.session.restored_from_store"  # bool
ACP_POOL_HIT = "acp.pool.hit"  # bool, connection reused vs new spawn
ACP_POOL_QUEUE_TIME_S = "acp.pool.queue_time_s"  # float, pool.acquire wait
ACP_POOL_ATTEMPT = "acp.pool.attempt"  # int, which retry succeeded (1=first)
ACP_PROMPT_LENGTH_CHARS = "acp.prompt.length_chars"  # int
ACP_OUTPUT_LENGTH_CHARS = "acp.output.length_chars"  # int
ACP_AUTH_ERROR_DETECTED = "acp.auth.error_detected"  # bool

# --- soulbot.* self-extension (no OTel standard yet) ---
SOULBOT_NODE_NAME = "soulbot.node.name"
SOULBOT_AIAP_NAME = "soulbot.aiap.name"
SOULBOT_TURN_INDEX = "soulbot.turn.index"
SOULBOT_TURN_ID = "soulbot.turn.id"
SOULBOT_STREAMING = "soulbot.streaming"

# --- Metrics (histogram names) ---
METRIC_OPERATION_DURATION = "gen_ai.client.operation.duration"  # seconds
METRIC_ESTIMATED_TOKEN_USAGE = "soulbot.estimated.token.usage"  # tokens (estimated)
METRIC_TOKEN_TYPE = "gen_ai.token.type"  # "input" | "output"
METRIC_ACP_SUBPROCESS_TTFT = "acp.subprocess.ttft"  # seconds, streaming first chunk
METRIC_ACP_POOL_QUEUE_TIME = "acp.pool.queue_time"  # seconds

# --- Schema URL for semconv version pin ---
SCHEMA_URL = "https://opentelemetry.io/schemas/1.30.0"
