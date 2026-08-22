"""Centralized configuration models for Friday.

The module uses dataclasses to keep configuration explicit, type-safe, and easy
to extend as the application grows.
"""

from __future__ import annotations

import threading
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


def get_app_home() -> Path:
    """Return the application home directory as a Path object.

    Checks the FRIDAY_HOME environment variable first, defaulting to
    ``~/.friday``. Ensures that the directory is created safely if it does
    not already exist.
    """
    env_home = getenv("FRIDAY_HOME")
    if env_home:
        app_home = Path(env_home).expanduser().resolve()
    else:
        app_home = Path.home() / ".friday"
    app_home.mkdir(parents=True, exist_ok=True)
    return app_home


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
        resolved_base_dir = base_dir.expanduser().resolve()
        app_home = get_app_home()

        return cls(
            base_dir=resolved_base_dir,
            app_home=app_home,
            logs_dir=app_home / DEFAULT_LOG_DIRNAME,
            data_dir=app_home / "data",
            state_dir=app_home / "state",
        )

    def ensure_directories(self) -> None:
        """Create runtime directories required by the current configuration."""
        for directory in (
            self.app_home,
            self.logs_dir,
            self.data_dir,
            self.state_dir,
            self.app_home / "skills",
        ):
            directory.mkdir(parents=True, exist_ok=True)

        self._populate_default_skills(self.app_home / "skills")

    def _populate_default_skills(self, skills_dir: Path) -> None:
        """Populate default skills if the directory is empty."""
        try:
            if any(skills_dir.iterdir()):
                return

            defaults = {
                "reviewer.md": "You are a Strict Senior Code Reviewer.\n\nRULES:\n1. Focus on architectural flaws, security vulnerabilities, and performance bottlenecks.\n2. Do NOT nitpick formatting unless it violates standard PEP8/language conventions.\n3. Always provide concrete code snippets for your suggested fixes.\n4. Think step-by-step in your analysis before outputting the final review.\n5. If the code is perfect, say so clearly without making up fake issues.",
                "architect.md": "You are a Principal Software Architect.\n\nRULES:\n1. Focus on high-level system design, scalability, and maintainability.\n2. Use Mermaid.js diagrams to visualize complex relationships or data flows.\n3. Before writing any code, draft a clear 'Implementation Plan' and present it to the user.\n4. Consider edge cases, fault tolerance, and API contracts.",
                "writer.md": "You are an Expert Technical Writer.\n\nRULES:\n1. Write clear, concise, and professional documentation.\n2. Avoid passive voice. Use active, engaging language.\n3. Format beautifully using GitHub-flavored Markdown (bolding, lists, code blocks).\n4. When writing READMEs, always include standard sections: Installation, Usage, Architecture, and Configuration.",
            }

            for name, content in defaults.items():
                (skills_dir / name).write_text(content, encoding="utf-8")
        except Exception:
            pass


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
    max_retries: int = 3
    retry_delay: float = 0.5


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

        provider = get_val("llm_provider", "FRIDAY_LLM_PROVIDER", "openai")

        api_key = get_val(f"{provider}_api_key", f"FRIDAY_{provider.upper()}_API_KEY")
        if not api_key:
            api_key = get_val("llm_api_key", "FRIDAY_LLM_API_KEY")

        base_url = get_val(
            f"{provider}_base_url", f"FRIDAY_{provider.upper()}_BASE_URL"
        )
        if not base_url:
            base_url = get_val("llm_base_url", "FRIDAY_LLM_BASE_URL")

        llm_config = LLMConfig(
            provider=provider,
            api_key=api_key,
            base_url=base_url,
            model=get_val("llm_model", "FRIDAY_LLM_MODEL"),
            timeout=float(get_val("llm_timeout", "FRIDAY_LLM_TIMEOUT", "30.0")),
            system_prompt=get_val("system_prompt", "FRIDAY_SYSTEM_PROMPT"),
            max_iterations=int(
                get_val("max_iterations", "FRIDAY_MAX_ITERATIONS", "10")
            ),
            max_retries=int(get_val("llm_max_retries", "FRIDAY_LLM_MAX_RETRIES", "3")),
            retry_delay=float(
                get_val("llm_retry_delay", "FRIDAY_LLM_RETRY_DELAY", "0.5")
            ),
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
            speech_language=get_val(
                "speech_language", "FRIDAY_SPEECH_LANGUAGE", "ru-RU"
            ),
            theme=get_val("theme", "FRIDAY_THEME", "dark"),
            accent_color=get_val("accent_color", "FRIDAY_ACCENT_COLOR"),
        )


_settings_lock = threading.Lock()


def load_settings(base_dir: Path | None = None) -> dict[str, Any]:
    resolved_base_dir = base_dir or Path.cwd()
    paths = PathsConfig.from_base_dir(resolved_base_dir)
    config_file = paths.app_home / "config.json"
    with _settings_lock:
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

    with _settings_lock:
        current = {}
        if config_file.exists():
            import json

            try:
                with open(config_file, encoding="utf-8") as f:
                    current = json.load(f)
            except Exception:
                pass

        current.update(settings)

        import json

        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=4)
