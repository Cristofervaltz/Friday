"""Command executor with safety boundaries, timeouts, and output management."""

from __future__ import annotations

import os
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class CommandResult:
    """Result of command execution.

    Attributes:
        exit_code: Process return code (0 for success).
        stdout: Standard output string.
        stderr: Standard error string.
        duration_seconds: Time taken to execute command in seconds.
    """

    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float

    @property
    def success(self) -> bool:
        """Return True if command finished with exit code 0."""
        return self.exit_code == 0


class CommandExecutor:
    """Executes shell commands with safety checks, timeouts, and output capturing."""

    # Default list of command prefixes deemed highly dangerous
    DEFAULT_BLOCKED_PATTERNS: list[str] = [
        "rm -rf /",
        "rmdir /s /q c:\\",
        "mkfs",
        ":(){ :|:& };:",
        "dd if=/dev/zero",
    ]

    def __init__(
        self,
        default_timeout: float = 30.0,
        max_output_length: int = 10000,
        confirmation_callback: Callable[[str], bool] | None = None,
        blocked_patterns: list[str] | None = None,
    ) -> None:
        """Initialize CommandExecutor.

        Args:
            default_timeout: Maximum execution time in seconds.
            max_output_length: Truncation threshold for stdout/stderr.
            confirmation_callback: Optional function to ask user permission.
            blocked_patterns: Custom list of blocked command patterns.
        """
        self.default_timeout = default_timeout
        self.max_output_length = max_output_length
        self.confirmation_callback = confirmation_callback
        self.blocked_patterns = (
            blocked_patterns
            if blocked_patterns is not None
            else list(self.DEFAULT_BLOCKED_PATTERNS)
        )

    def is_safe(self, command: str) -> bool:
        """Check if command passes basic safety checks.

        Args:
            command: Shell command string.

        Returns:
            True if command is safe to execute, False otherwise.
        """
        cmd_lower = command.strip().lower()
        for pattern in self.blocked_patterns:
            if pattern.lower() in cmd_lower:
                return False
        return True

    def execute(
        self,
        command: str,
        cwd: str | None = None,
        timeout: float | None = None,
        env: dict[str, str] | None = None,
    ) -> CommandResult:
        """Execute a shell command safely.

        Args:
            command: Shell command string to execute.
            cwd: Optional working directory path.
            timeout: Optional custom timeout in seconds (overrides default_timeout).
            env: Optional environment variables dictionary.

        Returns:
            CommandResult instance containing execution output and exit code.

        Raises:
            ValueError: If command is blocked by safety policy or rejected.
            TimeoutError: If execution exceeds specified timeout.
        """
        if not self.is_safe(command):
            raise ValueError(f"Command execution blocked by safety policy: {command}")

        if self.confirmation_callback is not None:
            if not self.confirmation_callback(command):
                raise ValueError(f"Command execution rejected by user: {command}")

        effective_timeout = timeout if timeout is not None else self.default_timeout
        working_dir = cwd if cwd is not None else os.getcwd()

        start_time = time.monotonic()
        try:
            completed_proc = subprocess.run(
                command,
                shell=True,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=effective_timeout,
                env=env,
            )
            duration = time.monotonic() - start_time

            stdout = self._truncate_output(completed_proc.stdout)
            stderr = self._truncate_output(completed_proc.stderr)

            return CommandResult(
                exit_code=completed_proc.returncode,
                stdout=stdout,
                stderr=stderr,
                duration_seconds=round(duration, 3),
            )
        except subprocess.TimeoutExpired as exc:
            duration = time.monotonic() - start_time
            raise TimeoutError(
                f"Command '{command}' timed out after {effective_timeout} seconds"
            ) from exc

    def _truncate_output(self, text: str) -> str:
        """Truncate text if it exceeds max_output_length."""
        if len(text) > self.max_output_length:
            truncated_len = self.max_output_length
            return (
                text[:truncated_len]
                + f"\n... [Output truncated to {truncated_len} characters]"
            )
        return text
