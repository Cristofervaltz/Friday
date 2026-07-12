"""Reusable logging infrastructure for Friday."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import ClassVar

from .config import LoggingConfig
from .constants import APP_NAME, DATE_FORMAT, LOG_FORMAT


class LoggerFactory:
    """Singleton factory responsible for configuring and returning loggers."""

    _instance: ClassVar[LoggerFactory | None] = None

    def __new__(cls) -> LoggerFactory:
        instance = cls._instance
        if instance is None:
            instance = super().__new__(cls)
            instance._configured = False
            cls._instance = instance
        return instance

    def configure(self, config: LoggingConfig) -> None:
        """Configure the application logger using the provided settings."""
        application_logger = logging.getLogger(APP_NAME)
        application_logger.handlers.clear()
        application_logger.setLevel(self._resolve_level(config.level))
        application_logger.propagate = False

        formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)

        if config.console_enabled:
            application_logger.addHandler(self._build_console_handler(formatter))

        if config.file_enabled:
            application_logger.addHandler(self._build_file_handler(config, formatter))

        self._configured = True

    def get_logger(self, name: str | None = None) -> logging.Logger:
        """Return a configured application logger or a namespaced child logger."""
        if not self._configured:
            raise RuntimeError("LoggerFactory must be configured before use.")

        if not name:
            return logging.getLogger(APP_NAME)

        child_logger = logging.getLogger(f"{APP_NAME}.{name}")
        child_logger.propagate = True
        return child_logger

    def _build_console_handler(self, formatter: logging.Formatter) -> logging.Handler:
        """Create a console log handler bound to stdout."""
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        return handler

    def _build_file_handler(
        self,
        config: LoggingConfig,
        formatter: logging.Formatter,
    ) -> logging.Handler:
        """Create a rotating file log handler."""
        self._ensure_directory(config.log_dir)
        handler = RotatingFileHandler(
            filename=config.log_file_path,
            maxBytes=config.max_bytes,
            backupCount=config.backup_count,
            encoding="utf-8",
        )
        handler.setFormatter(formatter)
        return handler

    def _ensure_directory(self, directory: Path) -> None:
        """Ensure that the logging directory exists before file handlers are created."""
        directory.mkdir(parents=True, exist_ok=True)

    def _resolve_level(self, level_name: str) -> int:
        """Resolve a textual log level to its logging module constant."""
        resolved_level = logging.getLevelName(level_name.upper())
        if isinstance(resolved_level, int):
            return resolved_level
        raise ValueError(f"Unsupported log level: {level_name}")
