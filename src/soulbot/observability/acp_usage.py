"""ACP usage estimation + provider identification.

SoulBot uses ACP (subprocess CLI tools with subscription billing) not Anthropic
API, so precise token/cost is unavailable. This module provides rough estimates
for observability/budgeting — NOT for actual billing.

Reference: Doc 12 v2.3 §6.1
"""
from __future__ import annotations


# Characters-per-token heuristic. English/Chinese mixed, averaged across
# Claude / Gemini / GPT tokenizers. Use 4 as middle ground.
#   - OpenAI tiktoken GPT-4: ~3.7 chars/token
#   - Claude tokenizer: ~3.5-4.2 chars/token
#   - GPT-J: ~4.0 chars/token
# Chinese averages differ but we don't distinguish here — this is rough.
CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    """Rough token count from char count. Not for billing.

    Returns 0 for empty/None text; otherwise at least 1 (never 0 for non-empty).
    """
    if not text:
        return 0
    return max(1, len(text) // CHARS_PER_TOKEN)


# ACP model string formats:
#   "{provider}-acp/{variant}"   e.g. "claude-acp/sonnet-4.5", "gemini-acp/pro"
#   "{provider}-cli/{variant}"   e.g. "cursor-cli/sonnet"
#   "{provider}/{variant}"       e.g. "openclaw/sonnet"
#
# First token before '-' or '/' is the provider short name.

def resolve_provider_from_model(model: str) -> str:
    """Extract short provider name from ACP model string.

    Examples:
        resolve_provider_from_model("claude-acp/sonnet-4.5") -> "claude"
        resolve_provider_from_model("gemini-acp/pro")        -> "gemini"
        resolve_provider_from_model("cursor-cli/sonnet")     -> "cursor"
        resolve_provider_from_model("openclaw/sonnet")       -> "openclaw"
        resolve_provider_from_model("")                      -> "unknown"
    """
    if not model:
        return "unknown"
    for sep in ("-", "/"):
        if sep in model:
            return model.split(sep, 1)[0]
    return model


# Maps ACP provider short name to gen_ai.provider.name (OTel standard form).
# Keeps our gen_ai.* spans interoperable with OTel dashboards / Langfuse / etc.
PROVIDER_OTEL_NAME = {
    "claude": "anthropic",
    "gemini": "google",
    "opencode": "opencode",  # no OTel standard; pass-through
    "openclaw": "openclaw",
    "cursor": "cursor",
}


def resolve_gen_ai_provider(acp_provider: str) -> str:
    """Map ACP short name to standardized gen_ai.provider.name value.

    Returns input unchanged if not in the mapping (safe fallback).
    """
    return PROVIDER_OTEL_NAME.get(acp_provider, acp_provider)
