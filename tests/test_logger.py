"""Tests for the Friday logging subsystem."""

from pathlib import Path

from src.config import LoggingConfig
from src.logger import LoggerFactory, get_logger


def test_logger_factory_is_a_singleton() -> None:
    assert LoggerFactory() is LoggerFactory()


def test_get_logger_returns_the_same_logger_instance() -> None:
    logger_a = get_logger("tests.alpha")
    logger_b = get_logger("tests.alpha")

    assert logger_a is logger_b


def test_repeated_logger_requests_do_not_duplicate_handlers(tmp_path: Path) -> None:
    config = LoggingConfig(
        level="INFO",
        log_dir=tmp_path,
        log_filename="friday.log",
        max_bytes=1024,
        backup_count=1,
        console_enabled=True,
        file_enabled=True,
    )
    factory = LoggerFactory()
    factory.configure(config)

    get_logger("tests")
    get_logger("tests")

    application_logger = get_logger()
    assert len(application_logger.handlers) == 2


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

    logger = get_logger("tests")
    logger.info("logger smoke test")

    for handler in get_logger().handlers:
        handler.flush()

    log_file = tmp_path / "friday.log"
    assert log_file.exists()
    assert "logger smoke test" in log_file.read_text(encoding="utf-8")


def test_logger_exception_output_contains_traceback(tmp_path: Path) -> None:
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

    try:
        raise RuntimeError("boom")
    except RuntimeError:
        get_logger("tests").exception("unexpected failure")

    for handler in get_logger().handlers:
        handler.flush()

    log_text = (tmp_path / "friday.log").read_text(encoding="utf-8")
    assert "unexpected failure" in log_text
    assert "Traceback" in log_text
    assert "RuntimeError: boom" in log_text


def test_logger_respects_configured_level(tmp_path: Path) -> None:
    config = LoggingConfig(
        level="ERROR",
        log_dir=tmp_path,
        log_filename="friday.log",
        max_bytes=1024,
        backup_count=1,
        console_enabled=False,
        file_enabled=True,
    )
    factory = LoggerFactory()
    factory.configure(config)

    logger = get_logger("tests")
    logger.debug("debug message")
    logger.info("info message")
    logger.error("error message")

    for handler in get_logger().handlers:
        handler.flush()

    log_text = (tmp_path / "friday.log").read_text(encoding="utf-8")
    assert "debug message" not in log_text
    assert "info message" not in log_text
    assert "error message" in log_text
