"""Shell command execution tool for Friday."""

from __future__ import annotations

from typing import Any

from src.executor.command_executor import CommandExecutor
from src.tools.base import BaseTool, ToolResult


class ShellCommandTool(BaseTool):
    """Tool for executing shell commands safely."""

    def __init__(self, executor: CommandExecutor | None = None) -> None:
        """Initialize ShellCommandTool.

        Args:
            executor: Optional custom CommandExecutor instance.
        """
        self.executor = executor if executor is not None else CommandExecutor()

    @property
    def name(self) -> str:
        """Return tool name."""
        return "execute_command"

    @property
    def description(self) -> str:
        """Return tool description."""
        return (
            "Execute a shell command in the terminal (PowerShell/CMD on Windows) and return stdout, stderr, "
            "and exit code. Use for running tests, build scripts, file operations, "
            "or system commands."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        """Return JSON schema for tool parameters."""
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command string to execute",
                },
                "cwd": {
                    "type": "string",
                    "description": "Optional working directory for execution",
                },
                "timeout": {
                    "type": "number",
                    "description": "Optional custom timeout in seconds",
                },
            },
            "required": ["command"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute a shell command.

        Args:
            **kwargs: Must contain 'command'. Optional 'cwd' and 'timeout'.

        Returns:
            ToolResult with command output or execution error.
        """
        command = kwargs.get("command")
        if not command or not isinstance(command, str):
            return ToolResult(
                success=False,
                error="Parameter 'command' is required and must be a non-empty string",
            )

        cwd = kwargs.get("cwd")
        if cwd is not None and not isinstance(cwd, str):
            return ToolResult(
                success=False,
                error="Parameter 'cwd' must be a string if provided",
            )

        raw_timeout = kwargs.get("timeout")
        timeout: float | None = None
        if raw_timeout is not None:
            if isinstance(raw_timeout, (int, float)):
                timeout = float(raw_timeout)
            else:
                return ToolResult(
                    success=False,
                    error="Parameter 'timeout' must be a number if provided",
                )

        try:
            result = self.executor.execute(command=command, cwd=cwd, timeout=timeout)
            output_msg = (
                f"Exit Code: {result.exit_code}\n"
                f"Duration: {result.duration_seconds}s\n"
                f"--- STDOUT ---\n{result.stdout}\n"
                f"--- STDERR ---\n{result.stderr}"
            )
            err_msg = (
                None
                if result.success
                else f"Command exited with code {result.exit_code}"
            )
            return ToolResult(
                success=result.success,
                output=output_msg,
                error=err_msg,
            )
        except (ValueError, TimeoutError) as exc:
            return ToolResult(
                success=False,
                error=str(exc),
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"Unexpected execution failure: {exc}",
            )
