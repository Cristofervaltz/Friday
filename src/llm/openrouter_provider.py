"""OpenRouter-compatible LLM provider implementation for Friday."""

from __future__ import annotations

from typing import Self

from src.config import LLMConfig

from .openai_provider import OpenAIProvider

_DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_DEFAULT_OPENROUTER_MODEL = "openai/gpt-4-turbo"


class OpenRouterProvider(OpenAIProvider):
    """Provider for OpenRouter API endpoints.

    OpenRouter is fully compatible with the OpenAI API format, so this class
    inherits from OpenAIProvider and only overrides default values.

    OpenRouter provides access to multiple LLM providers through a unified API.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        retry_delay: float | None = None,
        config: LLMConfig | None = None,
    ) -> None:
        """Create a new OpenRouter provider.

        Args:
            api_key: OpenRouter API key (starts with sk-or-v1-).
            model: Model identifier (e.g., "openai/gpt-4-turbo").
            base_url: OpenRouter API base URL (defaults to openrouter.ai).
            timeout: Request timeout in seconds.
            max_retries: Maximum number of retry attempts.
            retry_delay: Delay in seconds between retries.
            config: Optional Friday LLMConfig to load settings from.
        """
        resolved_base_url = (
            base_url
            if base_url is not None
            else (
                config.base_url
                if config and config.base_url
                else _DEFAULT_OPENROUTER_BASE_URL
            )
        )
        resolved_model = (
            model
            if model is not None
            else (
                config.model if config and config.model else _DEFAULT_OPENROUTER_MODEL
            )
        )

        super().__init__(
            api_key=api_key,
            model=resolved_model,
            base_url=resolved_base_url,
            timeout=timeout,
            max_retries=max_retries,
            retry_delay=retry_delay,
            config=config,
        )

    @classmethod
    def from_config(cls, config: LLMConfig) -> Self:
        """Construct a provider directly from Friday's configuration model."""
        return cls(config=config)
