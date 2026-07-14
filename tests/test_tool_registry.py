"""Tests for tool registry."""

from __future__ import annotations

import pytest

from src.core.tool_registry import ToolRegistry
from src.tools import ReadFileTool, WriteFileTool


def test_registry_starts_empty() -> None:
    """Test that a new registry has no tools."""
    registry = ToolRegistry()
    assert len(registry) == 0
    assert registry.list_tools() == []


def test_registry_can_register_tool() -> None:
    """Test registering a tool."""
    registry = ToolRegistry()
    tool = ReadFileTool()

    registry.register(tool)

    assert len(registry) == 1
    assert "read_file" in registry
    assert registry.list_tools() == ["read_file"]


def test_registry_can_register_multiple_tools() -> None:
    """Test registering multiple tools."""
    registry = ToolRegistry()
    read_tool = ReadFileTool()
    write_tool = WriteFileTool()

    registry.register(read_tool)
    registry.register(write_tool)

    assert len(registry) == 2
    assert "read_file" in registry
    assert "write_file" in registry
    assert set(registry.list_tools()) == {"read_file", "write_file"}


def test_registry_prevents_duplicate_registration() -> None:
    """Test that registering the same tool twice raises ValueError."""
    registry = ToolRegistry()
    tool = ReadFileTool()

    registry.register(tool)

    with pytest.raises(ValueError, match="already registered"):
        registry.register(tool)


def test_registry_can_get_tool_by_name() -> None:
    """Test retrieving a tool by name."""
    registry = ToolRegistry()
    tool = ReadFileTool()
    registry.register(tool)

    retrieved_tool = registry.get_tool("read_file")

    assert retrieved_tool is tool
    assert retrieved_tool.name == "read_file"


def test_registry_get_tool_raises_for_unknown_name() -> None:
    """Test that getting an unknown tool raises KeyError."""
    registry = ToolRegistry()

    with pytest.raises(KeyError, match="not registered"):
        registry.get_tool("unknown_tool")


def test_registry_can_unregister_tool() -> None:
    """Test unregistering a tool."""
    registry = ToolRegistry()
    tool = ReadFileTool()
    registry.register(tool)

    registry.unregister("read_file")

    assert len(registry) == 0
    assert "read_file" not in registry


def test_registry_unregister_raises_for_unknown_name() -> None:
    """Test that unregistering an unknown tool raises KeyError."""
    registry = ToolRegistry()

    with pytest.raises(KeyError, match="not registered"):
        registry.unregister("unknown_tool")


def test_registry_generates_tools_schema() -> None:
    """Test generating OpenAI function calling schema."""
    registry = ToolRegistry()
    tool = ReadFileTool()
    registry.register(tool)

    schema = registry.get_tools_schema()

    assert isinstance(schema, list)
    assert len(schema) == 1

    # Type narrowing for mypy
    first_schema = schema[0]
    assert isinstance(first_schema, dict)
    assert first_schema["type"] == "function"

    function_part = first_schema["function"]
    assert isinstance(function_part, dict)
    assert function_part["name"] == "read_file"
    assert "description" in function_part
    assert "parameters" in function_part


def test_registry_execute_calls_tool() -> None:
    """Test executing a tool through the registry."""
    registry = ToolRegistry()
    tool = ReadFileTool()
    registry.register(tool)

    # Try to read a non-existent file (should fail gracefully)
    result = registry.execute("read_file", path="/nonexistent/file.txt")

    assert result.success is False
    assert result.error is not None


def test_registry_execute_raises_for_unknown_tool() -> None:
    """Test that executing an unknown tool raises KeyError."""
    registry = ToolRegistry()

    with pytest.raises(KeyError, match="not registered"):
        registry.execute("unknown_tool", some_param="value")
