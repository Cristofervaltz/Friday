"""Tests for CommandExecutor in src/executor/command_executor.py."""

from __future__ import annotations

import pytest

from src.executor.command_executor import CommandExecutor, CommandResult


def test_command_result_properties() -> None:
    """Test CommandResult properties."""
    res_success = CommandResult(
        exit_code=0, stdout="ok", stderr="", duration_seconds=0.1
    )
    assert res_success.success is True

    res_fail = CommandResult(exit_code=1, stdout="", stderr="err", duration_seconds=0.1)
    assert res_fail.success is False


def test_executor_successful_execution() -> None:
    """Test executing a simple echo command."""
    executor = CommandExecutor()
    res = executor.execute("python -c \"print('hello friday')\"")
    assert res.success is True
    assert res.exit_code == 0
    assert "hello friday" in res.stdout
    assert res.duration_seconds >= 0.0


def test_executor_failing_command() -> None:
    """Test executing a command that exits with error."""
    executor = CommandExecutor()
    res = executor.execute('python -c "import sys; sys.exit(42)"')
    assert res.success is False
    assert res.exit_code == 42


def test_executor_safety_blocking() -> None:
    """Test safety blocking of dangerous commands."""
    executor = CommandExecutor()
    assert executor.is_safe("echo 123") is True
    assert executor.is_safe("rm -rf /") is False

    with pytest.raises(ValueError, match="blocked by safety policy"):
        executor.execute("rm -rf /")


def test_executor_confirmation_callback() -> None:
    """Test rejection via confirmation callback."""

    def reject_all(cmd: str) -> bool:
        return False

    executor = CommandExecutor(confirmation_callback=reject_all)
    with pytest.raises(ValueError, match="rejected by user"):
        executor.execute("echo test")


def test_executor_timeout() -> None:
    """Test command timeout exception."""
    executor = CommandExecutor(default_timeout=0.1)
    with pytest.raises(TimeoutError, match="timed out"):
        executor.execute('python -c "import time; time.sleep(1.0)"')


def test_executor_output_truncation() -> None:
    """Test truncating long outputs."""
    executor = CommandExecutor(max_output_length=50)
    res = executor.execute("python -c \"print('A' * 100)\"")
    assert len(res.stdout) < 100
    assert "... [Output truncated to 50 characters]" in res.stdout
