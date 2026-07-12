"""Tests for the Friday application entry point."""

from pathlib import Path

import pytest

from src.main import main


def test_main_bootstraps_and_prints_startup_message(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FRIDAY_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("FRIDAY_CONSOLE_LOGGING", "false")

    exit_code = main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Friday v0.0.1 initialized" in captured.out
