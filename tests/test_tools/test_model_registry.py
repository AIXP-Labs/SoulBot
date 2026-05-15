"""Tests for ModelRegistry."""

import pytest

from soulbot.models.base_llm import BaseLlm
from soulbot.models.registry import ModelRegistry


class DummyLlm(BaseLlm):
    """A dummy LLM for testing."""

    @classmethod
    def supported_models(cls) -> list[str]:
        return [r"dummy-.*"]

    async def generate_content_async(self, llm_request, *, stream=False):
        yield  # pragma: no cover


class TestModelRegistry:
    def setup_method(self):
        """Reset the registry before each test."""
        ModelRegistry.reset()

    def test_register_and_resolve(self):
        ModelRegistry.register(r"dummy-.*", DummyLlm)
        llm = ModelRegistry.resolve("dummy-v1")
        assert isinstance(llm, DummyLlm)
        assert llm.model == "dummy-v1"

    def test_resolve_unknown_raises(self):
        with pytest.raises(ValueError, match="No adapter registered"):
            ModelRegistry.resolve("unknown-model")

    def test_last_registered_wins(self):
        class DummyA(DummyLlm):
            pass

        class DummyB(DummyLlm):
            pass

        ModelRegistry.register(r"test-.*", DummyA)
        ModelRegistry.register(r"test-.*", DummyB)
        llm = ModelRegistry.resolve("test-v1")
        assert isinstance(llm, DummyB)

    def test_regex_patterns(self):
        ModelRegistry.register(r"gpt-.*", DummyLlm)
        ModelRegistry.register(r".+/.+", DummyLlm)

        assert isinstance(ModelRegistry.resolve("gpt-4o"), DummyLlm)
        assert isinstance(ModelRegistry.resolve("provider/model"), DummyLlm)

        with pytest.raises(ValueError):
            ModelRegistry.resolve("claude")  # No match

    def test_cache_invalidation(self):
        ModelRegistry.register(r"cached-.*", DummyLlm)
        llm1 = ModelRegistry.resolve("cached-v1")

        # Re-registering should invalidate cache
        class OtherLlm(DummyLlm):
            pass

        ModelRegistry.register(r"cached-.*", OtherLlm)
        llm2 = ModelRegistry.resolve("cached-v1")
        assert isinstance(llm2, OtherLlm)

    def test_reset(self):
        ModelRegistry.register(r"test-.*", DummyLlm)
        ModelRegistry.resolve("test-v1")  # populate cache
        ModelRegistry.reset()
        with pytest.raises(ValueError):
            ModelRegistry.resolve("test-v1")
