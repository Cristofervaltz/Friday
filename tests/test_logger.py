"""Tests for the Friday logging subsystem."""

from pathlib import Path

from src.config import LoggingConfig
from src.logger import LoggerFactory


def test_logger_factory_is_a_singleton() -> None:
    assert LoggerFactory() is LoggerFactory()


def test_logger_factory_writes_to_rotating_file(tmp_path: Path) -> None:
    config = LoggingConfig(
        level="INFO",
        log_dir=tmp_path,
        log_filename="friday.log",
        max_bytes=1024,
        backup_count=1,
        console_enabled=False,
        file_enabled=True,
    )
    factory = LoggerFactory()
    factory.configure(config)

    logger = factory.get_logger("tests")
    logger.info("logger smoke test")

    for handler in factory.get_logger().handlers:
        handler.flush()

    log_file = tmp_path / "friday.log"
    assert log_file.exists()
    assert "logger smoke test" in log_file.read_text(encoding="utf-8")
