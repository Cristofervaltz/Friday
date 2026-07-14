"""Tests for AI agent with function calling."""

from __future__ import annotations

from typing import Any

import pytest

from src.core.agent import Agent
from src.core.tool_registry import ToolRegistry
from src.llm.base import BaseLLMProvider, LLMResponse
from src.tools import ReadFileTool


class MockLLMProvider(BaseLLMProvider):
    """Mock LLM provider for testing."""

    def __init__(self) -> None:
        """Initialize mock provider."""
        self._responses: list[LLMResponse] = []
        self._call_count = 0

    def generate(self, prompt: str) -> str:
        """Generate mock response."""
        return "Mock response"

    def generate_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        """Generate mock response with tools."""
        if self._call_count < len(self._responses):
            response = self._responses[self._call_count]
            self._call_count += 1
            return response
        return LLMResponse(content="Default response", finish_reason="stop")

    def model_name(self) -> str:
        """Return mock model name."""
        return "mock-model"

    def add_response(self, response: LLMResponse) -> None:
        """Add a mock response to the queue."""
        self._responses.append(response)


def test_agent_initialization() -> None:
    """Test agent initializes correctly."""
    llm = MockLLMProvider()
    registry = ToolRegistry()

    agent = Agent(llm_provider=llm, tool_registry=registry)

    assert agent.llm is llm
    assert agent.tools is registry
    assert agent.max_iterations == 10
    assert len(agent.get_history()) == 0


def test_agent_handles_simple_message_without_tools() -> None:
    """Test agent handles a simple message without tool calls."""
    llm = MockLLMProvider()
    llm.add_response(
        LLMResponse(content="Hello! How can I help?", finish_reason="stop")
    )

    registry = ToolRegistry()
    agent = Agent(llm_provider=llm, tool_registry=registry)

    response = agent.run("Hello")

    assert response == "Hello! How can I help?"
    assert len(agent.get_history()) == 2  # User message + assistant response


def test_agent_calls_tool_when_requested() -> None:
    """Test agent calls a tool when LLM requests it."""
    llm = MockLLMProvider()

    # First response: LLM wants to call a tool
    llm.add_response(
        LLMResponse(
            content=None,
            tool_calls=[
                {
                    "id": "call_1",
                    "name": "read_file",
                    "arguments": {"path": "/tmp/test.txt"},
                }
            ],
            finish_reason="tool_calls",
        )
    )

    # Second response: LLM provides final answer after tool result
    llm.add_response(
        LLMResponse(
            content="The file doesn't exist.",
            finish_reason="stop",
        )
    )

    registry = ToolRegistry()
    registry.register(ReadFileTool())

    agent = Agent(llm_provider=llm, tool_registry=registry)

    response = agent.run("Read /tmp/test.txt")

    assert response == "The file doesn't exist."
    assert (
        len(agent.get_history()) == 4
    )  # User + assistant tool call + tool result + final


def test_agent_handles_multiple_tool_calls() -> None:
    """Test agent handles multiple tool calls in sequence."""
    llm = MockLLMProvider()

    # First: call tool 1
    llm.add_response(
        LLMResponse(
            content=None,
            tool_calls=[
                {
                    "id": "call_1",
                    "name": "read_file",
                    "arguments": {"path": "/tmp/file1.txt"},
                }
            ],
            finish_reason="tool_calls",
        )
    )

    # Second: call tool 2
    llm.add_response(
        LLMResponse(
            content=None,
            tool_calls=[
                {
                    "id": "call_2",
                    "name": "read_file",
                    "arguments": {"path": "/tmp/file2.txt"},
                }
            ],
            finish_reason="tool_calls",
        )
    )

    # Third: final response
    llm.add_response(
        LLMResponse(
            content="Both files don't exist.",
            finish_reason="stop",
        )
    )

    registry = ToolRegistry()
    registry.register(ReadFileTool())

    agent = Agent(llm_provider=llm, tool_registry=registry, max_iterations=5)

    response = agent.run("Read both files")

    assert response == "Both files don't exist."


def test_agent_prevents_infinite_loops() -> None:
    """Test agent stops after max iterations to prevent infinite loops."""
    llm = MockLLMProvider()

    # Always return tool calls (infinite loop scenario)
    for _ in range(15):
        llm.add_response(
            LLMResponse(
                content=None,
                tool_calls=[
                    {
                        "id": "call_1",
                        "name": "read_file",
                        "arguments": {"path": "/tmp/test.txt"},
                    }
                ],
                finish_reason="tool_calls",
            )
        )

    registry = ToolRegistry()
    registry.register(ReadFileTool())

    agent = Agent(llm_provider=llm, tool_registry=registry, max_iterations=3)

    with pytest.raises(RuntimeError, match="exceeded max iterations"):
        agent.run("Keep calling tools forever")


def test_agent_handles_tool_execution_errors() -> None:
    """Test agent handles errors during tool execution gracefully."""
    llm = MockLLMProvider()

    # LLM calls a non-existent tool
    llm.add_response(
        LLMResponse(
            content=None,
            tool_calls=[
                {
                    "id": "call_1",
                    "name": "nonexistent_tool",
                    "arguments": {},
                }
            ],
            finish_reason="tool_calls",
        )
    )

    # LLM provides final response after error
    llm.add_response(
        LLMResponse(
            content="Sorry, that tool doesn't exist.",
            finish_reason="stop",
        )
    )

    registry = ToolRegistry()
    agent = Agent(llm_provider=llm, tool_registry=registry)

    response = agent.run("Use a tool that doesn't exist")

    assert response == "Sorry, that tool doesn't exist."
    # Check that error was passed to LLM in conversation
    history = agent.get_history()
    assert any("Error" in str(msg.get("content", "")) for msg in history)


def test_agent_clear_history() -> None:
    """Test clearing conversation history."""
    llm = MockLLMProvider()
    llm.add_response(LLMResponse(content="Response 1", finish_reason="stop"))
    llm.add_response(LLMResponse(content="Response 2", finish_reason="stop"))

    registry = ToolRegistry()
    agent = Agent(llm_provider=llm, tool_registry=registry)

    agent.run("Message 1")
    assert len(agent.get_history()) == 2

    agent.clear_history()
    assert len(agent.get_history()) == 0

    agent.run("Message 2")
    assert len(agent.get_history()) == 2


def test_agent_get_history_returns_copy() -> None:
    """Test that get_history returns a copy, not the original list."""
    llm = MockLLMProvider()
    llm.add_response(LLMResponse(content="Response", finish_reason="stop"))

    registry = ToolRegistry()
    agent = Agent(llm_provider=llm, tool_registry=registry)

    agent.run("Test")
    history1 = agent.get_history()
    history2 = agent.get_history()

    # Should be equal but not the same object
    assert history1 == history2
    assert history1 is not history2
