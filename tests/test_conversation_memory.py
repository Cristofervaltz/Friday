"""Tests for ConversationMemory in src/memory/conversation.py."""

from __future__ import annotations

from src.memory.conversation import ConversationMemory


def test_conversation_memory_basic() -> None:
    """Test adding messages and system prompt formatting."""
    memory = ConversationMemory(system_prompt="You are Friday")
    assert len(memory) == 0

    memory.add_user_message("Hello")
    assert len(memory) == 1

    memory.add_assistant_message("Hi there!")
    assert len(memory) == 2

    messages = memory.get_messages()
    assert len(messages) == 3
    assert messages[0]["role"] == "system"
    assert messages[0]["content"].startswith("You are Friday")
    msgs = memory.get_messages()
    assert len(msgs) == 3
    assert msgs[1]["role"] == "user"
    assert msgs[1]["content"] == "Hello"
    assert "id" in msgs[1]
    assert msgs[2]["role"] == "assistant"
    assert msgs[2]["content"] == "Hi there!"
    assert "id" in msgs[2]


def test_conversation_memory_tool_calls() -> None:
    """Test adding tool calls and tool results."""
    memory = ConversationMemory()
    tool_calls = [{"id": "call_123", "type": "function"}]

    memory.add_assistant_message(tool_calls=tool_calls)
    memory.add_tool_result("call_123", "Tool execution output")

    messages = memory.get_messages()
    assert len(messages) == 2
    assert messages[0]["role"] == "assistant"
    assert messages[0]["tool_calls"] == tool_calls
    assert messages[1]["role"] == "tool"
    assert messages[1]["tool_call_id"] == "call_123"
    assert messages[1]["content"] == "Tool execution output"


def test_conversation_memory_max_messages() -> None:
    """Test sliding window message truncation."""
    memory = ConversationMemory(max_messages=3)
    memory.add_user_message("msg 1")
    memory.add_user_message("msg 2")
    memory.add_user_message("msg 3")
    memory.add_user_message("msg 4")

    assert len(memory) == 3
    messages = memory.get_messages()
    assert len(messages) == 3
    assert messages[0]["content"] == "msg 2"
    assert messages[2]["content"] == "msg 4"


def test_conversation_memory_clear() -> None:
    """Test clearing memory keeps system prompt."""
    memory = ConversationMemory(system_prompt="System prompt")
    memory.add_user_message("Hello")
    memory.clear()

    assert len(memory) == 0
    messages = memory.get_messages()
    assert len(messages) == 1
    assert messages[0]["role"] == "system"
