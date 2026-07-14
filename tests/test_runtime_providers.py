"""Additional tests for Runtime provider factory."""

from pathlib import Path

import pytest

from src.runtime import FridayApplication


def test_runtime_initializes_openrouter_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that Runtime correctly initializes OpenRouter provider."""
    monkeypatch.setenv("FRIDAY_LLM_PROVIDER", "openrouter")
    monkeypatch.setenv(
        "FRIDAY_LLM_API_KEY",
        "sk-or-v1-FAKE_KEY_FOR_TESTING_DO_NOT_USE_IN_PRODUCTION_12345678",
    )
    monkeypatch.setenv("FRIDAY_LLM_MODEL", "openai/gpt-4-turbo")

    app = FridayApplication(base_dir=tmp_path)
    app.initialize()

    assert app.provider is not None
    assert app.provider.model_name() == "openai/gpt-4-turbo"

    app.shutdown()


def test_runtime_initializes_ollama_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that Runtime correctly initializes Ollama provider."""
    monkeypatch.setenv("FRIDAY_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("FRIDAY_LLM_MODEL", "llama2")
    monkeypatch.setenv("FRIDAY_LLM_BASE_URL", "http://localhost:11434")

    app = FridayApplication(base_dir=tmp_path)
    app.initialize()

    assert app.provider is not None
    assert app.provider.model_name() == "llama2"

    app.shutdown()


def test_runtime_handles_unknown_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that Runtime gracefully handles unknown provider types."""
    monkeypatch.setenv("FRIDAY_LLM_PROVIDER", "unknown-provider")
    monkeypatch.setenv("FRIDAY_LLM_API_KEY", "test-key")
    monkeypatch.setenv("FRIDAY_LLM_MODEL", "test-model")

    app = FridayApplication(base_dir=tmp_path)
    app.initialize()

    # Should initialize successfully but provider should be None
    # Cannot access app.provider directly as it will raise AssertionError
    # Check internal state instead
    assert app._provider is None

    app.shutdown()
