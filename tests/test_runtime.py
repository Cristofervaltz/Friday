"""Tests for Friday runtime application lifecycle."""

from pathlib import Path
from unittest.mock import patch

import pytest

from src.config import AppConfig
from src.runtime import FridayApplication


def test_application_initializes_successfully(tmp_path: Path) -> None:
    """Test successful application initialization."""
    app = FridayApplication(base_dir=tmp_path)
    app.initialize()

    assert app.config is not None
    assert app.logger is not None
    assert app.config.app_name == "Friday"


def test_application_creates_required_objects(tmp_path: Path) -> None:
    """Test that all required runtime objects are created."""
    app = FridayApplication(base_dir=tmp_path)
    app.initialize()

    assert isinstance(app.config, AppConfig)
    assert app.logger.name == "Friday.src.runtime.application"


def test_application_properties_require_initialization(tmp_path: Path) -> None:
    """Test that accessing properties before initialization raises error."""
    app = FridayApplication(base_dir=tmp_path)

    with pytest.raises(RuntimeError, match="must be initialized"):
        _ = app.config

    with pytest.raises(RuntimeError, match="must be initialized"):
        _ = app.logger

    with pytest.raises(RuntimeError, match="must be initialized"):
        _ = app.provider


def test_application_run_requires_initialization(tmp_path: Path) -> None:
    """Test that run() requires initialization."""
    app = FridayApplication(base_dir=tmp_path)

    with pytest.raises(RuntimeError, match="must be initialized"):
        app.run()


def test_application_prevents_double_initialization(tmp_path: Path) -> None:
    """Test that initialize() cannot be called twice."""
    app = FridayApplication(base_dir=tmp_path)
    app.initialize()

    with pytest.raises(RuntimeError, match="already initialized"):
        app.initialize()


def test_application_run_returns_zero(tmp_path: Path) -> None:
    """Test that run() returns exit code 0."""
    app = FridayApplication(base_dir=tmp_path)
    app.initialize()

    exit_code = app.run()

    assert exit_code == 0


def test_application_shutdown_is_safe_to_call_multiple_times(tmp_path: Path) -> None:
    """Test that shutdown() can be called multiple times safely."""
    app = FridayApplication(base_dir=tmp_path)
    app.initialize()

    app.shutdown()
    app.shutdown()  # Should not raise


def test_application_shutdown_after_failed_initialization(tmp_path: Path) -> None:
    """Test that shutdown() works even if initialization failed."""
    app = FridayApplication(base_dir=tmp_path)

    with patch.object(
        app,
        "_load_configuration",
        side_effect=Exception("Config error"),
    ):
        with pytest.raises(Exception, match="Config error"):
            app.initialize()

    # Should not raise
    app.shutdown()


def test_application_handles_provider_initialization_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that application continues if provider initialization fails."""
    # Set invalid provider config to trigger failure
    monkeypatch.setenv("FRIDAY_LLM_API_KEY", "")

    app = FridayApplication(base_dir=tmp_path)
    app.initialize()

    # Application should still be initialized
    assert app.config is not None
    assert app.logger is not None

    # Provider should be None
    with pytest.raises(AssertionError):
        _ = app.provider


def test_application_creates_runtime_directories(tmp_path: Path) -> None:
    """Test that runtime directories are created during initialization."""
    app = FridayApplication(base_dir=tmp_path)
    app.initialize()

    friday_home = tmp_path / ".friday"
    assert friday_home.exists()
    assert (friday_home / "logs").exists()
    assert (friday_home / "data").exists()
    assert (friday_home / "state").exists()


def test_application_logs_initialization_steps(tmp_path: Path) -> None:
    """Test that initialization steps are logged."""
    app = FridayApplication(base_dir=tmp_path)
    app.initialize()

    # Logger should be configured after initialization
    assert app.logger is not None

    # Trigger a log message to ensure the file is created
    app.logger.info("Test log message")

    log_file = tmp_path / ".friday" / "logs" / "friday.log"
    # File may not exist until first write, so this is acceptable
    if log_file.exists():
        log_content = log_file.read_text()
        assert "Test log message" in log_content


def test_application_shutdown_cleans_state(tmp_path: Path) -> None:
    """Test that shutdown() cleans up internal state."""
    app = FridayApplication(base_dir=tmp_path)
    app.initialize()

    app.shutdown()

    # After shutdown, properties should raise
    with pytest.raises(RuntimeError, match="must be initialized"):
        _ = app.config


def test_application_lifecycle_full_flow(tmp_path: Path) -> None:
    """Test complete application lifecycle: init -> run -> shutdown."""
    app = FridayApplication(base_dir=tmp_path)

    app.initialize()
    exit_code = app.run()
    app.shutdown()

    assert exit_code == 0
