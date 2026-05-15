from .base_llm import BaseLlm
from .llm_request import GenerateContentConfig, LlmRequest, LlmResponse
from .registry import ModelRegistry

# Register ACP adapter for all supported providers
from .acp_llm import ACPLlm

ModelRegistry.register(r"claude-acp/.*", ACPLlm)
ModelRegistry.register(r"gemini-acp/.*", ACPLlm)
ModelRegistry.register(r"opencode-acp/.*", ACPLlm)
ModelRegistry.register(r"openclaw/.*", ACPLlm)
ModelRegistry.register(r"cursor-cli/.*", ACPLlm)
ModelRegistry.register(r"codex-acp/.*", ACPLlm)

__all__ = [
    "BaseLlm",
    "GenerateContentConfig",
    "LlmRequest",
    "LlmResponse",
    "ModelRegistry",
    "ACPLlm",
]
