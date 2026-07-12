"""Minimal Friday bootstrap example."""

from src.config import AppConfig
from src.logger import LoggerFactory
from src.main import build_startup_message


def run() -> None:
    """Bootstrap the Friday foundation outside the package entry point."""
    config = AppConfig.from_environment()
    config.paths.ensure_directories()

    logger_factory = LoggerFactory()
    logger_factory.configure(config.logging)

    logger = logger_factory.get_logger(__name__)
    logger.info(build_startup_message(config))


if __name__ == "__main__":
    run()
