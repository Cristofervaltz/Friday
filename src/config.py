"""Centralized configuration models for Friday.

The module uses dataclasses to keep configuration explicit, type-safe, and easy
to extend as the application grows.
"""

from __future__ import annotations

from dataclasses import dataclass
from os import getenv
from pathlib import Path
from typing import Any

from .constants import (
    APP_NAME,
    APP_VERSION,
    DEFAULT_ENVIRONMENT,
    DEFAULT_LOG_DIRNAME,
    DEFAULT_LOG_FILENAME,
    DEFAULT_LOG_LEVEL,
)


@dataclass(frozen=True)
class PathsConfig:
    """Filesystem locations used by the application bootstrap layer."""

    base_dir: Path
    app_home: Path
    logs_dir: Path
    data_dir: Path
    state_dir: Path

    @classmethod
    def from_base_dir(cls, base_dir: Path) -> PathsConfig:
        """Build path configuration from a repository or runtime base directory."""
        from os import getenv
        resolved_base_dir = base_dir.expanduser().resolve()
        
        # Use FRIDAY_HOME if set (useful for tests), otherwise use global home dir
        env_home = getenv("FRIDAY_HOME")
        if env_home:
            app_home = Path(env_home).expanduser().resolve()
        else:
            # Use a stable global app home directory so settings aren't lost when launched from different CWDs
            app_home = Path.home() / ".friday"
            
        return cls(
            base_dir=resolved_base_dir,
            app_home=app_home,
            logs_dir=app_home / DEFAULT_LOG_DIRNAME,
            data_dir=app_home / "data",
            state_dir=app_home / "state",
        )

    def ensure_directories(self) -> None:
        """Create runtime directories required by the current configuration."""
        for directory in (self.app_home, self.logs_dir, self.data_dir, self.state_dir):
            directory.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class LoggingConfig:
    """Logging configuration for the application runtime."""

    level: str
    log_dir: Path
    log_filename: str
    max_bytes: int = 1_048_576
    backup_count: int = 5
    console_enabled: bool = True
    file_enabled: bool = True

    @property
    def log_file_path(self) -> Path:
        """Return the fully qualified path to the active log file."""
        return self.log_dir / self.log_filename


@dataclass(frozen=True)
class LLMConfig:
    """Configuration for the LLM provider subsystem."""

    provider: str = "openai"
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None
    timeout: float = 30.0
    system_prompt: str | None = None
    max_iterations: int = 10


@dataclass(frozen=True)
class AppConfig:
    """Top-level application configuration object for Friday."""

    app_name: str
    version: str
    environment: str
    paths: PathsConfig
    logging: LoggingConfig
    llm: LLMConfig
    speech_language: str = "ru-RU"
    theme: str = "dark"
    accent_color: str | None = None

    @classmethod
    def from_environment(cls, base_dir: Path | None = None) -> AppConfig:
        """Create configuration from the environment and optional base directory."""
        resolved_base_dir = base_dir or Path.cwd()
        paths = PathsConfig.from_base_dir(resolved_base_dir)

        # First, try to load settings from config.json
        config_file = paths.app_home / "config.json"
        saved_settings = {}
        if config_file.exists():
            import json

            try:
                with open(config_file, encoding="utf-8") as f:
                    saved_settings = json.load(f)
            except Exception:
                pass

        def get_val(key: str, env_key: str, default: Any = None) -> Any:
            val = saved_settings.get(key)
            if val is not None and val != "":
                return str(val)
            env_val = getenv(env_key)
            if env_val is not None and env_val != "":
                return str(env_val)
            return default

        configured_log_dir = Path(
            get_val("log_dir", "FRIDAY_LOG_DIR") or str(paths.logs_dir)
        )
        logging_config = LoggingConfig(
            level=get_val("log_level", "FRIDAY_LOG_LEVEL", DEFAULT_LOG_LEVEL).upper(),
            log_dir=configured_log_dir.expanduser().resolve(),
            log_filename=get_val(
                "log_filename", "FRIDAY_LOG_FILENAME", DEFAULT_LOG_FILENAME
            ),
            max_bytes=int(get_val("log_max_bytes", "FRIDAY_LOG_MAX_BYTES", "1048576")),
            backup_count=int(
                get_val("log_backup_count", "FRIDAY_LOG_BACKUP_COUNT", "5")
            ),
            console_enabled=str(
                get_val("console_logging", "FRIDAY_CONSOLE_LOGGING", "true")
            ).lower()
            in {"1", "true", "yes", "on"},
            file_enabled=str(
                get_val("file_logging", "FRIDAY_FILE_LOGGING", "true")
            ).lower()
            in {"1", "true", "yes", "on"},
        )

        llm_config = LLMConfig(
            provider=get_val("llm_provider", "FRIDAY_LLM_PROVIDER", "openai"),
            api_key=get_val("llm_api_key", "FRIDAY_LLM_API_KEY"),
            base_url=get_val("llm_base_url", "FRIDAY_LLM_BASE_URL"),
            model=get_val("llm_model", "FRIDAY_LLM_MODEL"),
            timeout=float(get_val("llm_timeout", "FRIDAY_LLM_TIMEOUT", "30.0")),
            system_prompt=get_val("system_prompt", "FRIDAY_SYSTEM_PROMPT"),
            max_iterations=int(get_val("max_iterations", "FRIDAY_MAX_ITERATIONS", "10")),
        )

        return cls(
            app_name=get_val("app_name", "FRIDAY_APP_NAME", APP_NAME),
            version=get_val("version", "FRIDAY_VERSION", APP_VERSION),
            environment=get_val(
                "environment", "FRIDAY_ENVIRONMENT", DEFAULT_ENVIRONMENT
            ),
            paths=paths,
            logging=logging_config,
            llm=llm_config,
            speech_language=get_val("speech_language", "FRIDAY_SPEECH_LANGUAGE", "ru-RU"),
            theme=get_val("theme", "FRIDAY_THEME", "dark"),
            accent_color=get_val("accent_color", "FRIDAY_ACCENT_COLOR"),
        )


def load_settings(base_dir: Path | None = None) -> dict[str, Any]:
    resolved_base_dir = base_dir or Path.cwd()
    paths = PathsConfig.from_base_dir(resolved_base_dir)
    config_file = paths.app_home / "config.json"
    if config_file.exists():
        import json

        try:
            with open(config_file, encoding="utf-8") as f:
                return json.load(f)  # type: ignore
        except Exception:
            return {}
    return {}


def save_settings(settings: dict[str, Any], base_dir: Path | None = None) -> None:
    resolved_base_dir = base_dir or Path.cwd()
    paths = PathsConfig.from_base_dir(resolved_base_dir)
    paths.ensure_directories()
    config_file = paths.app_home / "config.json"

    current = load_settings(base_dir)
    current.update(settings)

    import json

    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=4)
