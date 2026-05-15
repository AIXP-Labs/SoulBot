"""Smoke tests for semconv constants.

Verifies the module loads, exports the expected namespace, and key constants
have the expected string values (so typos don't silently break span queries).
"""
from __future__ import annotations

from soulbot.observability import semconv as sc


def test_gen_ai_prefix():
    assert sc.GEN_AI_OPERATION_NAME == "gen_ai.operation.name"
    assert sc.GEN_AI_AGENT_NAME == "gen_ai.agent.name"
    assert sc.GEN_AI_PROVIDER_NAME == "gen_ai.provider.name"
    assert sc.GEN_AI_REQUEST_MODEL == "gen_ai.request.model"
    assert sc.GEN_AI_USAGE_INPUT_TOKENS == "gen_ai.usage.input_tokens"
    assert sc.GEN_AI_USAGE_OUTPUT_TOKENS == "gen_ai.usage.output_tokens"
    assert sc.GEN_AI_SERVER_TTFT == "gen_ai.server.time_to_first_token"


def test_acp_prefix():
    assert sc.ACP_PROVIDER_NAME == "acp.provider.name"
    assert sc.ACP_SESSION_ID == "acp.session.id"
    assert sc.ACP_SESSION_ROTATED == "acp.session.rotated"
    assert sc.ACP_POOL_QUEUE_TIME_S == "acp.pool.queue_time_s"
    assert sc.ACP_POOL_ATTEMPT == "acp.pool.attempt"
    assert sc.ACP_PROMPT_LENGTH_CHARS == "acp.prompt.length_chars"
    assert sc.ACP_AUTH_ERROR_DETECTED == "acp.auth.error_detected"


def test_soulbot_prefix():
    assert sc.SOULBOT_NODE_NAME == "soulbot.node.name"
    assert sc.SOULBOT_AIAP_NAME == "soulbot.aiap.name"
    assert sc.SOULBOT_TURN_ID == "soulbot.turn.id"
    assert sc.SOULBOT_STREAMING == "soulbot.streaming"


def test_metric_names():
    assert sc.METRIC_OPERATION_DURATION == "gen_ai.client.operation.duration"
    assert sc.METRIC_ESTIMATED_TOKEN_USAGE == "soulbot.estimated.token.usage"
    assert sc.METRIC_ACP_SUBPROCESS_TTFT == "acp.subprocess.ttft"
    assert sc.METRIC_ACP_POOL_QUEUE_TIME == "acp.pool.queue_time"


def test_schema_url_present():
    assert sc.SCHEMA_URL.startswith("https://opentelemetry.io/schemas/")


def test_v22_deleted_anthropic_specific_not_present():
    """v2.2 removed Anthropic-specific constants — ensure they stayed gone."""
    for deleted in (
        "ANTHROPIC_CACHE_READ_TOKENS",
        "ANTHROPIC_CACHE_CREATION_5M_TOKENS",
        "ANTHROPIC_CACHE_CREATION_1H_TOKENS",
        "ANTHROPIC_SERVICE_TIER",
        "SOULBOT_COST_USD",
        "SOULBOT_LLM_FAST_MODE",
        "SOULBOT_LLM_THINKING_TTFT_MS",
    ):
        assert not hasattr(sc, deleted), (
            f"{deleted} should not be in semconv.py after v2.2 ACP architecture alignment"
        )
