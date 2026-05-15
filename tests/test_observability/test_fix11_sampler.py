"""Fix 11: AlwaysKeepCriticalSampler — critical spans kept even at rate=0.0.

Tests cover the six critical-detection branches:
1. Critical name prefix
2. gen_ai.operation.name in always-keep set
3. status ∈ {"fail", "error"}
4. wallclock_elapsed_s > threshold
5. acp.session.rotated / acp.auth.error_detected
6. gen_ai.usage.output_tokens > threshold

Plus fallthrough to fallback for non-critical spans.
"""
from __future__ import annotations

from opentelemetry.sdk.trace.sampling import ALWAYS_OFF, Decision

from soulbot.observability.otel_sampler import AlwaysKeepCriticalSampler


def _sample(sampler: AlwaysKeepCriticalSampler, name: str, attrs: dict | None = None):
    result = sampler.should_sample(
        parent_context=None,
        trace_id=0x1234,
        name=name,
        attributes=attrs,
    )
    return result.decision


class TestAlwaysKeepCriticalSampler:
    def setup_method(self):
        # Fallback = ALWAYS_OFF so only sampler's "always keep" rules trigger RECORD_AND_SAMPLE
        self.sampler = AlwaysKeepCriticalSampler(ALWAYS_OFF)

    def test_critical_name_prefix_kept(self):
        for name in (
            "security.injection.suspected",
            "cost.exceed",
            "pipeline.breaker.open",
            "pipeline.guardrail.abort",
            "pipeline.speaker.selected",
            "pipeline.stage.resume",
            "guardrail.abort",
        ):
            assert _sample(self.sampler, name) == Decision.RECORD_AND_SAMPLE, name

    def test_critical_operation_name_kept(self):
        for op in ("guardrail_abort", "speaker_selection", "resume"):
            d = _sample(self.sampler, "some.normal.name", {"gen_ai.operation.name": op})
            assert d == Decision.RECORD_AND_SAMPLE, op

    def test_error_status_kept(self):
        assert _sample(self.sampler, "normal.span", {"status": "fail"}) == Decision.RECORD_AND_SAMPLE
        assert _sample(self.sampler, "normal.span", {"status": "error"}) == Decision.RECORD_AND_SAMPLE

    def test_slow_elapsed_kept(self, monkeypatch):
        monkeypatch.setenv("SOULBOT_SLOW_THRESHOLD_S", "5.0")
        assert _sample(self.sampler, "normal", {"wallclock_elapsed_s": 6.0}) == Decision.RECORD_AND_SAMPLE
        # Below threshold → falls through to ALWAYS_OFF
        assert _sample(self.sampler, "normal", {"wallclock_elapsed_s": 1.0}) == Decision.DROP

    def test_acp_session_rotated_kept(self):
        assert _sample(self.sampler, "normal", {"acp.session.rotated": True}) == Decision.RECORD_AND_SAMPLE

    def test_acp_auth_error_kept(self):
        assert _sample(self.sampler, "normal", {"acp.auth.error_detected": True}) == Decision.RECORD_AND_SAMPLE

    def test_heavy_token_usage_kept(self, monkeypatch):
        monkeypatch.setenv("SOULBOT_TOKEN_THRESHOLD", "1000")
        assert _sample(self.sampler, "normal", {"gen_ai.usage.output_tokens": 2000}) == Decision.RECORD_AND_SAMPLE
        # Below threshold → falls through
        assert _sample(self.sampler, "normal", {"gen_ai.usage.output_tokens": 500}) == Decision.DROP

    def test_non_critical_defers_to_fallback(self):
        # ALWAYS_OFF fallback → DROP
        assert _sample(self.sampler, "plain.span", {}) == Decision.DROP

    def test_description_includes_fallback(self):
        desc = self.sampler.get_description()
        assert "AlwaysKeepCriticalSampler" in desc
        assert "AlwaysOff" in desc  # ALWAYS_OFF sampler
