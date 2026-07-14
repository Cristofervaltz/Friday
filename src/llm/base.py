"""Abstract interfaces for Friday LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMResponse:
    """Response from LLM provider.

    Attributes:
        content: Generated text content (None if tool call).
        tool_calls: List of tool calls requested by LLM.
        finish_reason: Reason for completion (stop, tool_calls, length, etc).
    """

    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    finish_reason: str = "stop"


class BaseLLMProvider(ABC):
    """Common interface implemented by every language-model provider."""

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Generate a text response for a single prompt."""

    @abstractmethod
    def generate_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        """Generate response with function calling support.

        Args:
            messages: Conversation history in OpenAI format.
            tools: Available tools in OpenAI function calling format.

        Returns:
            LLMResponse with content or tool calls.
        """

    def is_available(self) -> bool:
        """Return whether the provider is configured and ready to use."""
        return True

    @abstractmethod
    def model_name(self) -> str:
        """Return the configured model name."""

    @staticmethod
    def validate_prompt(prompt: str) -> str:
        """Validate and normalize a prompt before dispatching it."""
        normalized_prompt = prompt.strip()
        if not normalized_prompt:
            raise ValueError("Prompt must not be empty.")
        return normalized_prompt
