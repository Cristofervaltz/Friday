"""Application entry point for Friday."""

from __future__ import annotations

from .config import AppConfig
from .logger import LoggerFactory


def build_startup_message(config: AppConfig) -> str:
    """Build the human-readable startup message for the current runtime."""
    return (
        f"{config.app_name} v{config.version} initialized "
        f"in {config.environment} mode."
    )


def main() -> int:
    """Initialize the minimal Friday application bootstrap."""
    config = AppConfig.from_environment()
    config.paths.ensure_directories()

    logger_factory = LoggerFactory()
    logger_factory.configure(config.logging)
    logger = logger_factory.get_logger(__name__)

    startup_message = build_startup_message(config)
    print(startup_message)
    logger.info(startup_message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
