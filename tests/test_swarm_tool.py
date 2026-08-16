"""Tests for the swarm_tool (DelegateTaskTool)."""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.core.tool_registry import ToolRegistry
from src.tools.swarm_tool import DelegateTaskTool


class MockApp:
    def __init__(self) -> None:
        self.provider = MagicMock()
        self.config = MagicMock()
        self.config.paths.data_dir = MagicMock()
        self.config.llm.max_iterations = 10


@pytest.fixture
def registry() -> ToolRegistry:
    return ToolRegistry()


@pytest.fixture
def app() -> MockApp:
    return MockApp()


@pytest.fixture
def tool(app: MockApp, registry: ToolRegistry) -> DelegateTaskTool:
    return DelegateTaskTool(app=app, registry=registry)


def test_swarm_tool_sync(tool: DelegateTaskTool, registry: ToolRegistry) -> None:
    """Test that tool runs synchronously and returns output."""
    mock_run = MagicMock(return_value="Task complete")

    with patch("src.tools.swarm_tool.Agent.run", mock_run):
        result = tool.execute(role="Coder", task="Write a function")

        assert result.success is True
        assert "Sub-agent 'Coder' done. Response:\nTask complete" in str(result.output)
        mock_run.assert_called_once_with("Write a function")


def test_swarm_tool_background(tool: DelegateTaskTool, registry: ToolRegistry) -> None:
    """Test that tool runs in background and returns immediately."""

    # Use a flag to verify background execution
    run_called = False

    def fake_run(self_agent: Any, task: str) -> str:
        nonlocal run_called
        run_called = True
        return "Background task complete"

    # We patch Agent.run, note that side_effect for a method takes (self, *args)
    # Actually wait, mock side_effect for method patch can just take *args depending on autospec
    # We'll just patch it with a regular function but since it's a method on the class,
    # the first argument will be the instance 'self'.
    def fake_run_method(self_agent: Any, task: str) -> str:
        nonlocal run_called
        run_called = True
        return "Background task complete"

    with patch("src.tools.swarm_tool.Agent.run", new=fake_run_method):
        result = tool.execute(role="Coder", task="Do work", run_in_background=True)

        assert result.success is True
        assert "spawned in the background" in str(result.output)

        # Wait a bit for thread to execute
        time.sleep(0.1)
        assert run_called is True


def test_swarm_tool_missing_params(tool: DelegateTaskTool) -> None:
    """Test error on missing params."""
    result = tool.execute(role="Coder")
    assert result.success is False
    assert "Missing required parameters" in str(result.error)
