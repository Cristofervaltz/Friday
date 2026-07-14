"""Abstract interfaces for Friday LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseLLMProvider(ABC):
    """Common interface implemented by every language-model provider."""

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Generate a text response for a single prompt."""

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
