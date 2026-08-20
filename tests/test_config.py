"""Tests for Friday configuration models."""

from pathlib import Path

import pytest

from scripts.build_sidecar import get_target_triple
from src._compat import load_settings_safe
from src.config import AppConfig, get_app_home
from src.constants import APP_NAME, APP_VERSION, DEFAULT_LOG_LEVEL
from src.utils.port import cleanup_runtime_port, read_runtime_port, write_runtime_port


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


def test_get_app_home_respects_env_var(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    custom_home = tmp_path / "custom_friday"
    monkeypatch.setenv("FRIDAY_HOME", str(custom_home))
    home = get_app_home()
    assert home == custom_home
    assert home.exists()


def test_get_app_home_fallback_to_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FRIDAY_HOME", raising=False)
    home = get_app_home()
    assert home == Path.home() / ".friday"


def test_port_utilities_use_get_app_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    custom_home = tmp_path / "port_test_friday"
    monkeypatch.setenv("FRIDAY_HOME", str(custom_home))

    port_path = write_runtime_port(8765)
    assert port_path == custom_home / "runtime_port"
    assert read_runtime_port() == 8765

    cleanup_runtime_port()
    assert not port_path.exists()
    assert read_runtime_port() == 8000


def test_compat_load_settings_safe_respects_env_var(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    custom_home = tmp_path / "compat_friday"
    custom_home.mkdir(parents=True, exist_ok=True)
    (custom_home / "config.json").write_text('{"theme": "light"}', encoding="utf-8")

    monkeypatch.setenv("FRIDAY_HOME", str(custom_home))
    settings = load_settings_safe()
    assert settings.get("theme") == "light"


def test_build_sidecar_get_target_triple() -> None:
    triple = get_target_triple()
    assert isinstance(triple, str)
    assert len(triple) > 0
