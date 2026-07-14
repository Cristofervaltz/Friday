"""Additional tests for OpenRouter and Ollama providers."""

from src.config import LLMConfig
from src.llm import OllamaProvider, OpenRouterProvider

# Tests for OpenRouter Provider


def test_openrouter_provider_initialization() -> None:
    """Test OpenRouter provider initialization with explicit values."""
    provider = OpenRouterProvider(
        api_key="test-key",
        model="openai/gpt-4-turbo",
    )

    assert provider.model_name() == "openai/gpt-4-turbo"
    assert provider.is_available()


def test_openrouter_provider_uses_correct_base_url() -> None:
    """Test that OpenRouter uses the correct base URL."""
    provider = OpenRouterProvider(
        api_key="test-key",
        model="openai/gpt-4-turbo",
    )

    # OpenRouter should use openrouter.ai as base URL
    assert "openrouter.ai" in provider._base_url


def test_openrouter_provider_from_config() -> None:
    """Test OpenRouter provider initialization from config."""
    config = LLMConfig(
        provider="openrouter",
        api_key="test-key",
        model="anthropic/claude-3-sonnet",
    )

    provider = OpenRouterProvider.from_config(config)
    assert provider.model_name() == "anthropic/claude-3-sonnet"


# Tests for Ollama Provider


def test_ollama_provider_initialization() -> None:
    """Test Ollama provider initialization with explicit values."""
    provider = OllamaProvider(
        model="llama2",
        base_url="http://localhost:11434",
    )

    assert provider.model_name() == "llama2"
    assert provider.is_available()


def test_ollama_provider_uses_default_values() -> None:
    """Test that Ollama provider uses sensible defaults."""
    provider = OllamaProvider()

    assert provider.model_name() == "llama2"
    assert "localhost:11434" in provider._base_url


def test_ollama_provider_from_config() -> None:
    """Test Ollama provider initialization from config."""
    config = LLMConfig(
        provider="ollama",
        model="mistral",
        base_url="http://localhost:11434",
    )

    provider = OllamaProvider.from_config(config)
    assert provider.model_name() == "mistral"


def test_ollama_provider_requires_model() -> None:
    """Test that Ollama uses default model when config model is empty."""
    config = LLMConfig(
        provider="ollama",
        model="",  # Empty model should use default
    )

    provider = OllamaProvider.from_config(config)
    # Should use default model "llama2"
    assert provider.model_name() == "llama2"
