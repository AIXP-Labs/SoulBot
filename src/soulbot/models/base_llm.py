"""BaseLlm — abstract interface for model adapters."""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, AsyncGenerator

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from .llm_request import LlmRequest, LlmResponse


class BaseLlm(BaseModel):
    """Abstract base for all LLM adapters.

    Subclasses must implement :meth:`generate_content_async` and
    :meth:`supported_models`.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    model: str
    """The model identifier (e.g. 'gpt-4o-mini')."""

    @classmethod
    def supported_models(cls) -> list[str]:
        """Return regex patterns for models this adapter handles."""
        return []

    @abstractmethod
    async def generate_content_async(
        self, llm_request: "LlmRequest", *, stream: bool = False
    ) -> AsyncGenerator["LlmResponse", None]:
        """Generate content from the model.

        Args:
            llm_request: The fully-built LLM request.
            stream: Whether to stream partial responses.

        Yields:
            LlmResponse objects.  In non-streaming mode, yields exactly one.
            In streaming mode, intermediate responses have ``partial=True``
            and the final one has ``partial=False``.
        """
        raise NotImplementedError
        yield  # pragma: no cover — make this an async generator
