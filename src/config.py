"""Centralized configuration models for Friday.

The module uses dataclasses to keep configuration explicit, type-safe, and easy
to extend as the application grows.
"""

from __future__ import annotations

from dataclasses import dataclass
from os import getenv
from pathlib import Path

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
        resolved_base_dir = base_dir.expanduser().resolve()
        app_home = resolved_base_dir / ".friday"
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
class AppConfig:
    """Top-level application configuration object for Friday."""

    app_name: str
    version: str
    environment: str
    paths: PathsConfig
    logging: LoggingConfig

    @classmethod
    def from_environment(cls, base_dir: Path | None = None) -> AppConfig:
        """Create configuration from the environment and optional base directory."""
        resolved_base_dir = base_dir or Path.cwd()
        paths = PathsConfig.from_base_dir(resolved_base_dir)

        configured_log_dir = Path(getenv("FRIDAY_LOG_DIR", str(paths.logs_dir)))
        logging_config = LoggingConfig(
            level=getenv("FRIDAY_LOG_LEVEL", DEFAULT_LOG_LEVEL).upper(),
            log_dir=configured_log_dir.expanduser().resolve(),
            log_filename=getenv("FRIDAY_LOG_FILENAME", DEFAULT_LOG_FILENAME),
            max_bytes=int(getenv("FRIDAY_LOG_MAX_BYTES", "1048576")),
            backup_count=int(getenv("FRIDAY_LOG_BACKUP_COUNT", "5")),
            console_enabled=getenv("FRIDAY_CONSOLE_LOGGING", "true").lower()
            in {"1", "true", "yes", "on"},
            file_enabled=getenv("FRIDAY_FILE_LOGGING", "true").lower()
            in {"1", "true", "yes", "on"},
        )

        return cls(
            app_name=APP_NAME,
            version=APP_VERSION,
            environment=getenv("FRIDAY_ENV", DEFAULT_ENVIRONMENT),
            paths=paths,
            logging=logging_config,
        )
