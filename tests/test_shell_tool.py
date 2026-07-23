"""Tests for ShellCommandTool in src/tools/shell_tool.py."""

from __future__ import annotations

from src.tools.shell_tool import ShellCommandTool


def test_shell_tool_metadata() -> None:
    """Test ShellCommandTool properties and schema."""
    tool = ShellCommandTool()
    assert tool.name == "execute_command"
    assert "Execute a shell command" in tool.description

    schema = tool.parameters_schema
    assert schema["type"] == "object"
    assert "command" in schema["properties"]
    assert "command" in schema["required"]

    openai_schema = tool.to_openai_schema()
    assert openai_schema["type"] == "function"
    assert openai_schema["function"]["name"] == "execute_command"


def test_shell_tool_successful_execution() -> None:
    """Test ShellCommandTool executing a valid command."""
    tool = ShellCommandTool()
    res = tool.execute(command="python -c \"print('shell tool test')\"")
    assert res.success is True
    assert res.output is not None
    assert "Exit Code: 0" in res.output
    assert "shell tool test" in res.output
    assert res.error is None


def test_shell_tool_invalid_parameters() -> None:
    """Test ShellCommandTool validation of inputs."""
    tool = ShellCommandTool()
    res_no_cmd = tool.execute()
    assert res_no_cmd.success is False
    assert "Parameter 'command' is required" in (res_no_cmd.error or "")

    res_bad_cwd = tool.execute(command="echo 1", cwd=123)
    assert res_bad_cwd.success is False
    assert "Parameter 'cwd' must be a string" in (res_bad_cwd.error or "")

    res_bad_timeout = tool.execute(command="echo 1", timeout="invalid")
    assert res_bad_timeout.success is False
    assert "Parameter 'timeout' must be a number" in (res_bad_timeout.error or "")


def test_shell_tool_command_failure() -> None:
    """Test ShellCommandTool handling failed execution."""
    tool = ShellCommandTool()
    res = tool.execute(command='python -c "import sys; sys.exit(1)"')
    assert res.success is False
    assert res.error == "Command exited with code 1"
    assert res.output is not None
    assert "Exit Code: 1" in res.output


def test_shell_tool_blocked_command() -> None:
    """Test ShellCommandTool when command is blocked by safety policy."""
    tool = ShellCommandTool()
    res = tool.execute(command="rm -rf /")
    assert res.success is False
    assert "blocked by safety policy" in (res.error or "")
