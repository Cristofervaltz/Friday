"""Tests for Friday configuration models."""

from pathlib import Path

import pytest

from src.config import AppConfig
from src.constants import APP_NAME, APP_VERSION, DEFAULT_LOG_LEVEL


def test_app_config_uses_expected_defaults(tmp_path: Path) -> None:
    config = AppConfig.from_environment(base_dir=tmp_path)

    assert config.app_name == APP_NAME
    assert config.version == APP_VERSION
    assert config.logging.level == DEFAULT_LOG_LEVEL
    assert config.paths.logs_dir == tmp_path.resolve() / ".friday" / "logs"
    assert config.llm.provider == "openai"
    assert config.llm.api_key is None
    assert config.llm.base_url is None
    assert config.llm.model is None
    assert config.llm.timeout == 30.0


def test_app_config_reads_environment_overrides(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("FRIDAY_ENVIRONMENT", "test")
    monkeypatch.setenv("FRIDAY_LOG_LEVEL", "debug")
    monkeypatch.setenv("FRIDAY_LOG_FILENAME", "runtime.log")
    monkeypatch.setenv("FRIDAY_LOG_MAX_BYTES", "2048")
    monkeypatch.setenv("FRIDAY_LOG_BACKUP_COUNT", "2")
    monkeypatch.setenv("FRIDAY_CONSOLE_LOGGING", "false")
    monkeypatch.setenv("FRIDAY_FILE_LOGGING", "true")
    monkeypatch.setenv("FRIDAY_LLM_PROVIDER", "openai")
    monkeypatch.setenv("FRIDAY_LLM_API_KEY", "env-key")
    monkeypatch.setenv("FRIDAY_LLM_BASE_URL", "https://example.com/v1")
    monkeypatch.setenv("FRIDAY_LLM_MODEL", "gpt-4.1-mini")
    monkeypatch.setenv("FRIDAY_LLM_TIMEOUT", "45.5")

    config = AppConfig.from_environment(base_dir=tmp_path)

    assert config.environment == "test"
    assert config.logging.level == "DEBUG"
    assert config.logging.log_filename == "runtime.log"
    assert config.logging.max_bytes == 2048
    assert config.logging.backup_count == 2
    assert config.logging.console_enabled is False
    assert config.logging.file_enabled is True
    assert config.llm.provider == "openai"
    assert config.llm.api_key == "env-key"
    assert config.llm.base_url == "https://example.com/v1"
    assert config.llm.model == "gpt-4.1-mini"
    assert config.llm.timeout == 45.5
