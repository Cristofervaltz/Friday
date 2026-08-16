"""Fault tolerance and resilience tests for Friday agent and LLM subsystem."""

from __future__ import annotations

import io
import json
import logging
import threading
from email.message import Message
from typing import Any, Literal
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

from src.core.agent import Agent
from src.core.tool_registry import ToolRegistry
from src.executor.command_executor import CommandExecutor
from src.llm.base import BaseLLMProvider, LLMResponse
from src.llm.exceptions import (
    AuthenticationError,
    ConnectionError,
    LLMError,
    TimeoutError,
)
from src.llm.ollama_provider import OllamaProvider
from src.llm.openai_provider import OpenAIProvider
from src.llm.openrouter_provider import OpenRouterProvider
from src.logger import SafeStreamHandler
from src.memory.conversation import ConversationMemory
from src.planner.models import Plan
from src.planner.planner import TaskPlanner
from src.tools.base import BaseTool, ToolResult
from src.utils.json_repair import repair_json, safe_json_loads
from src.utils.safe_print import safe_print


class MockHTTPResponse:
    """Minimal context-manager response stub for urllib tests."""

    def __init__(self, payload: dict[str, Any] | str) -> None:
        if isinstance(payload, str):
            self._data = payload.encode("utf-8")
        else:
            self._data = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._data

    def __enter__(self) -> MockHTTPResponse:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> Literal[False]:
        return False


class EchoTool(BaseTool):
    """Simple test tool."""

    @property
    def name(self) -> str:
        return "echo_tool"

    @property
    def description(self) -> str:
        return "Echoes back the received message."

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Message to echo"},
            },
            "required": ["message"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        msg = kwargs.get("message", "")
        return ToolResult(success=True, output=f"Echo: {msg}")


class FaultyLLMProvider(BaseLLMProvider):
    """Mock LLM provider designed to test error scenarios."""

    def __init__(self, scenario: str = "normal", response_data: Any = None) -> None:
        self.scenario = scenario
        self.response_data = response_data
        self.call_count = 0

    def generate(self, prompt: str) -> str:
        self.call_count += 1
        if self.scenario == "connection_error":
            raise ConnectionError("Failed to reach LLM server (network down).")
        elif self.scenario == "timeout_error":
            raise TimeoutError("LLM server timed out.")
        elif self.scenario == "malformed_json":
            return "```json\n{'result': 'repaired_text',}\n```"
        elif self.scenario == "unicode_response":
            return "Friday 🚀: Привет мир! こんにちは 🧠 💻"
        return "Normal response"

    def generate_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        self.call_count += 1
        if self.scenario == "connection_error":
            raise ConnectionError("Network unreachable: failed to connect to host.")
        elif self.scenario == "timeout_error":
            raise TimeoutError("Read timeout after 30 seconds.")
        elif self.scenario == "malformed_tool_args_repairable":
            return LLMResponse(
                content=None,
                tool_calls=[
                    {
                        "id": "call_1",
                        "name": "echo_tool",
                        "arguments": "{'message': 'Hello with single quotes & trailing comma',}",
                    }
                ],
                finish_reason="tool_calls",
            )
        elif self.scenario == "malformed_tool_args_unrepairable":
            return LLMResponse(
                content=None,
                tool_calls=[
                    {
                        "id": "call_2",
                        "name": "echo_tool",
                        "arguments": "{{{completely unparseable garbage???",
                    }
                ],
                finish_reason="tool_calls",
            )
        elif self.scenario == "unicode_response":
            return LLMResponse(
                content="Ответ: 🚀 Успешно выполнен запрос! Emojis: 🧠💡🤖 and Japanese: こんにちは",
                finish_reason="stop",
            )
        return LLMResponse(content="Default mock response", finish_reason="stop")

    def model_name(self) -> str:
        return "fault-tolerant-mock"


# ============================================================================
# R1: Graceful Network Error Handling Tests
# ============================================================================


def test_agent_handles_llm_connection_error_gracefully() -> None:
    """R1: Agent must return a textual error without crashing when LLM connection fails."""
    provider = FaultyLLMProvider(scenario="connection_error")
    registry = ToolRegistry()
    agent = Agent(llm_provider=provider, tool_registry=registry)

    # Must NOT raise exception
    response = agent.run("Hello Friday")

    assert isinstance(response, str)
    assert "Error" in response
    assert "Network unreachable" in response

    # Check conversation history has recorded the error
    history = agent.get_history()
    assert len(history) == 2  # user message + assistant error message
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"
    assert "Error" in history[1]["content"]


def test_agent_handles_llm_timeout_gracefully() -> None:
    """R1: Agent must return a textual error without crashing when LLM times out."""
    provider = FaultyLLMProvider(scenario="timeout_error")
    registry = ToolRegistry()
    agent = Agent(llm_provider=provider, tool_registry=registry)

    response = agent.run("Hello Friday")

    assert isinstance(response, str)
    assert "Error" in response
    assert "timeout" in response.lower()


def test_openai_provider_retries_on_transient_network_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R1: Provider should retry on transient network errors and succeed if retry passes."""
    provider = OpenAIProvider(
        api_key="test-key",
        model="gpt-4.1-mini",
        base_url="https://example.com/v1",
        timeout=5.0,
        max_retries=3,
        retry_delay=0.01,
    )

    attempt_count = 0

    def mock_urlopen(request: Request, timeout: float) -> MockHTTPResponse:
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 3:
            raise URLError("Temporary connection reset")
        return MockHTTPResponse(
            {"choices": [{"message": {"content": "Recovered on attempt 3"}}]}
        )

    monkeypatch.setattr("src.llm.openai_provider.urlopen", mock_urlopen)

    result = provider.generate("Test prompt")
    assert result == "Recovered on attempt 3"
    assert attempt_count == 3


def test_openai_provider_fails_after_exhausting_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R1: Provider raises ConnectionError after exhausting all retry attempts."""
    provider = OpenAIProvider(
        api_key="test-key",
        model="gpt-4.1-mini",
        base_url="https://example.com/v1",
        timeout=5.0,
        max_retries=3,
        retry_delay=0.01,
    )

    attempt_count = 0

    def mock_urlopen(request: Request, timeout: float) -> MockHTTPResponse:
        nonlocal attempt_count
        attempt_count += 1
        raise URLError("Persistent network down")

    monkeypatch.setattr("src.llm.openai_provider.urlopen", mock_urlopen)

    with pytest.raises(ConnectionError, match="Persistent network down"):
        provider.generate("Test prompt")

    assert attempt_count == 3


def test_openai_provider_no_retry_on_auth_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R1: Provider should not waste retries on 401/403 authentication failures."""
    provider = OpenAIProvider(
        api_key="invalid-key",
        model="gpt-4.1-mini",
        base_url="https://example.com/v1",
        timeout=5.0,
        max_retries=3,
        retry_delay=0.01,
    )

    attempt_count = 0

    def mock_urlopen(request: Request, timeout: float) -> MockHTTPResponse:
        nonlocal attempt_count
        attempt_count += 1
        raise HTTPError(
            request.full_url,
            401,
            "Unauthorized",
            hdrs=Message(),
            fp=None,
        )

    monkeypatch.setattr("src.llm.openai_provider.urlopen", mock_urlopen)

    with pytest.raises(AuthenticationError):
        provider.generate("Test prompt")

    assert attempt_count == 1  # Failed immediately without retries


def test_ollama_provider_retries_on_connection_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R1: OllamaProvider should also retry on transient errors."""
    provider = OllamaProvider(
        model="llama2",
        base_url="http://localhost:11434",
        timeout=5.0,
        max_retries=3,
        retry_delay=0.01,
    )

    attempt_count = 0

    def mock_urlopen(request: Request, timeout: float) -> MockHTTPResponse:
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 2:
            raise URLError("Connection refused")
        return MockHTTPResponse({"response": "Ollama recovered"})

    monkeypatch.setattr("src.llm.ollama_provider.urlopen", mock_urlopen)

    result = provider.generate("Test prompt")
    assert result == "Ollama recovered"
    assert attempt_count == 2


def test_ollama_provider_fast_fails_on_404_client_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R1: OllamaProvider should fast-fail on 404 (model not found) without wasting retries."""
    provider = OllamaProvider(
        model="nonexistent-model",
        base_url="http://localhost:11434",
        timeout=5.0,
        max_retries=3,
        retry_delay=0.01,
    )

    attempt_count = 0

    def mock_urlopen(request: Request, timeout: float) -> MockHTTPResponse:
        nonlocal attempt_count
        attempt_count += 1
        raise HTTPError(
            request.full_url,
            404,
            "Model not found",
            hdrs=Message(),
            fp=None,
        )

    monkeypatch.setattr("src.llm.ollama_provider.urlopen", mock_urlopen)

    with pytest.raises(ConnectionError, match="status code 404"):
        provider.generate("Test prompt")

    assert attempt_count == 1  # Fast-failed on 404


def test_openrouter_provider_supports_custom_retries_and_delay() -> None:
    """R1: OpenRouterProvider accepts max_retries and retry_delay."""
    provider = OpenRouterProvider(
        api_key="sk-or-test-key",
        model="openai/gpt-4o",
        max_retries=5,
        retry_delay=0.25,
    )

    assert provider._max_retries == 5
    assert provider._retry_delay == 0.25
    assert provider.model_name() == "openai/gpt-4o"


# ============================================================================
# R2: Token-Efficient JSON Error Handling Tests
# ============================================================================


def test_json_repair_utility_handles_markdown_fences() -> None:
    """R2: repair_json strips markdown code block fences."""
    raw = '```json\n{"name": "Friday", "version": "1.0"}\n```'
    parsed = repair_json(raw)
    assert parsed == {"name": "Friday", "version": "1.0"}


def test_json_repair_utility_handles_single_quotes_and_trailing_commas() -> None:
    """R2: repair_json handles single quotes, trailing commas, and python booleans."""
    raw = "{'key': 'value', 'enabled': True, 'count': 42,}"
    parsed = repair_json(raw)
    assert parsed == {"key": "value", "enabled": True, "count": 42}


def test_json_repair_utility_handles_unclosed_structures() -> None:
    """R2: repair_json recovers unclosed braces and brackets."""
    raw = '{"tasks": [{"description": "First step", "expected_outcome": "Pass"'
    parsed = repair_json(raw)
    assert isinstance(parsed, dict)
    assert "tasks" in parsed
    assert parsed["tasks"][0]["description"] == "First step"


def test_json_repair_utility_extracts_outermost_json() -> None:
    """R2: repair_json extracts JSON when surrounded by commentary text."""
    raw = (
        'Sure! Here is the data: {"status": "ok", "items": [1, 2, 3]} Hope this helps!'
    )
    parsed = repair_json(raw)
    assert parsed == {"status": "ok", "items": [1, 2, 3]}


def test_json_repair_unquoted_keys_and_comments_and_control_chars() -> None:
    """R2: repair_json handles unquoted keys, JS/Python comments, and unescaped newlines."""
    raw_unquoted = '{name: "Friday", age: 10, key-dash: "val"}'
    assert repair_json(raw_unquoted) == {
        "name": "Friday",
        "age": 10,
        "key-dash": "val",
    }

    raw_comments = '// Lead comment\n{"status": "ok" /* inline */} # end'
    assert repair_json(raw_comments) == {"status": "ok"}

    raw_control_chars = '{\n  "msg": "line 1\nline 2"\n}'
    assert repair_json(raw_control_chars) == {"msg": "line 1\nline 2"}

    raw_single_quotes_escaped = "{'quote': 'She said \"Hello\" & don\\'t wait'}"
    assert repair_json(raw_single_quotes_escaped) == {
        "quote": 'She said "Hello" & don\'t wait'
    }


def test_safe_json_loads_returns_fallback_on_complete_failure() -> None:
    """R2: safe_json_loads returns fallback value when JSON is unrepairable."""
    res, success = safe_json_loads("not valid json at all", default={"fallback": True})
    assert success is False
    assert res == {"fallback": True}


def test_agent_repairs_malformed_tool_call_arguments_locally() -> None:
    """R2: Agent repairs malformed JSON arguments locally without extra LLM token usage."""
    provider = FaultyLLMProvider(scenario="malformed_tool_args_repairable")
    registry = ToolRegistry()
    registry.register(EchoTool())

    agent = Agent(llm_provider=provider, tool_registry=registry, max_iterations=2)

    def mock_generate_with_tools(messages: list[Any], tools: list[Any]) -> LLMResponse:
        if len(messages) <= 2:
            return LLMResponse(
                content=None,
                tool_calls=[
                    {
                        "id": "call_1",
                        "name": "echo_tool",
                        "arguments": "{'message': 'Repaired local argument!',}",
                    }
                ],
                finish_reason="tool_calls",
            )
        return LLMResponse(content="Tool execution finished.", finish_reason="stop")

    provider.generate_with_tools = mock_generate_with_tools  # type: ignore[method-assign]

    response = agent.run("Run echo tool")
    assert response == "Tool execution finished."

    history = agent.get_history()
    tool_results = [m for m in history if m.get("role") == "tool"]
    assert len(tool_results) == 1
    assert "Echo: Repaired local argument!" in tool_results[0]["content"]


def test_agent_handles_unrepairable_tool_arguments_without_crashing() -> None:
    """R2: Agent handles completely invalid tool arguments without crashing."""
    provider = FaultyLLMProvider(scenario="malformed_tool_args_unrepairable")
    registry = ToolRegistry()
    registry.register(EchoTool())

    agent = Agent(llm_provider=provider, tool_registry=registry, max_iterations=2)

    def mock_generate_with_tools(messages: list[Any], tools: list[Any]) -> LLMResponse:
        if len(messages) <= 2:
            return LLMResponse(
                content=None,
                tool_calls=[
                    {
                        "id": "call_1",
                        "name": "echo_tool",
                        "arguments": "{{{garbage",
                    }
                ],
                finish_reason="tool_calls",
            )
        return LLMResponse(content="Handled error cleanly.", finish_reason="stop")

    provider.generate_with_tools = mock_generate_with_tools  # type: ignore[method-assign]

    response = agent.run("Run with bad arguments")
    assert response == "Handled error cleanly."

    history = agent.get_history()
    tool_results = [m for m in history if m.get("role") == "tool"]
    assert len(tool_results) == 1
    assert "Failed to parse tool arguments" in tool_results[0]["content"]


def test_agent_handles_parallel_tool_calls_in_single_turn() -> None:
    """R2: Agent executes multiple tool calls in a single turn adhering to OpenAI format."""
    registry = ToolRegistry()
    registry.register(EchoTool())

    mock_llm = MagicMock()
    mock_llm.generate_with_tools.side_effect = [
        LLMResponse(
            content=None,
            tool_calls=[
                {
                    "id": "call_a",
                    "name": "echo_tool",
                    "arguments": {"message": "first"},
                },
                {
                    "id": "call_b",
                    "name": "echo_tool",
                    "arguments": "{message: 'second'}",  # unquoted & single quotes
                },
            ],
            finish_reason="tool_calls",
        ),
        LLMResponse(content="Both tools finished.", finish_reason="stop"),
    ]

    agent = Agent(llm_provider=mock_llm, tool_registry=registry)
    response = agent.run("Run both")

    assert response == "Both tools finished."

    history = agent.get_history()
    # Check that assistant message has both tool calls bundled
    assistant_msg = history[1]
    assert assistant_msg["role"] == "assistant"
    assert len(assistant_msg["tool_calls"]) == 2
    assert assistant_msg["tool_calls"][0]["id"] == "call_a"
    assert assistant_msg["tool_calls"][1]["id"] == "call_b"

    # Check both tool result messages follow
    assert history[2]["role"] == "tool"
    assert history[2]["tool_call_id"] == "call_a"
    assert "Echo: first" in history[2]["content"]

    assert history[3]["role"] == "tool"
    assert history[3]["tool_call_id"] == "call_b"
    assert "Echo: second" in history[3]["content"]


def test_openai_provider_sse_tool_calls_multi_chunk_stream() -> None:
    """R2: OpenAIProvider correctly reconstructs tool calls streamed across multiple SSE chunks."""
    provider = OpenAIProvider(
        api_key="test-key",
        model="gpt-4.1-mini",
        base_url="https://example.com/v1",
    )

    chunk1 = json.dumps(
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call_stream_1",
                                "type": "function",
                                "function": {"name": "echo_tool"},
                            }
                        ]
                    }
                }
            ]
        }
    )
    chunk2 = json.dumps(
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "function": {"arguments": '{"message": '},
                            }
                        ]
                    }
                }
            ]
        }
    )
    chunk3 = json.dumps(
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "function": {"arguments": '"streamed_arg"}'},
                            }
                        ]
                    },
                    "finish_reason": "tool_calls",
                }
            ]
        }
    )

    raw_sse = f"data: {chunk1}\n\ndata: {chunk2}\n\ndata: {chunk3}\n\ndata: [DONE]\n\n"

    payload = provider._parse_payload(raw_sse)
    response = provider._extract_response(payload)

    assert response.tool_calls is not None
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0]["id"] == "call_stream_1"
    assert response.tool_calls[0]["name"] == "echo_tool"
    assert response.tool_calls[0]["arguments"] == {"message": "streamed_arg"}


def test_task_planner_repairs_malformed_plan_arguments() -> None:
    """R2: TaskPlanner repairs malformed JSON in create_plan tool call."""
    mock_llm = MagicMock()
    mock_llm.generate_with_tools.return_value = LLMResponse(
        content=None,
        tool_calls=[
            {
                "name": "create_plan",
                "arguments": (
                    "```json\n"
                    "{\n"
                    "  'tasks': [\n"
                    "    {'description': 'Step 1', 'expected_outcome': 'Success'},\n"
                    "  ]\n"
                    "}\n"
                    "```"
                ),
            }
        ],
        finish_reason="tool_calls",
    )

    planner = TaskPlanner(mock_llm)
    plan = planner.generate_plan("Build feature")

    assert len(plan.tasks) == 1
    assert plan.tasks[0].description == "Step 1"
    assert plan.tasks[0].expected_outcome == "Success"


def test_task_planner_handles_direct_list_and_string_tasks() -> None:
    """R2: TaskPlanner handles plans returned as direct task lists or string items."""
    mock_llm = MagicMock()
    mock_llm.generate_with_tools.return_value = LLMResponse(
        content=None,
        tool_calls=[
            {
                "name": "create_plan",
                "arguments": '["Task 1: Initialize repository", "Task 2: Implement feature"]',
            }
        ],
        finish_reason="tool_calls",
    )

    planner = TaskPlanner(mock_llm)
    plan = planner.generate_plan("Direct list tasks")

    assert len(plan.tasks) == 2
    assert plan.tasks[0].description == "Task 1: Initialize repository"
    assert plan.tasks[1].description == "Task 2: Implement feature"


# ============================================================================
# R3: Unicode Error Prevention Tests
# ============================================================================


def test_agent_processes_complex_unicode_and_emojis() -> None:
    """R3: Agent handles complex Unicode (Cyrillic, CJK, emojis) without error."""
    provider = FaultyLLMProvider(scenario="unicode_response")
    registry = ToolRegistry()
    agent = Agent(llm_provider=provider, tool_registry=registry)

    user_query = "Привет, Пятница! 🤖 Помоги с задачей 🚀"
    response = agent.run(user_query)

    assert "🚀" in response
    assert "Успешно" in response
    assert "こんにちは" in response
    assert len(agent.get_history()) == 2
    assert agent.get_history()[0]["content"] == user_query


def test_safe_stream_handler_prevents_unicode_encode_error() -> None:
    """R3: SafeStreamHandler catches UnicodeEncodeError on limited encoding streams."""

    class RestrictedEncodingStream(io.StringIO):
        """Simulates a Windows console stream with ASCII encoding."""

        encoding = "ascii"

        def write(self, s: str) -> int:
            # Simulate what a real ascii / charmap console stream does
            s.encode("ascii")  # Will raise UnicodeEncodeError on emojis
            return super().write(s)

    mock_stream = RestrictedEncodingStream()
    handler = SafeStreamHandler(mock_stream)
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)

    logger = logging.getLogger("test_unicode_logger")
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    # Logging complex emojis, Cyrillic, and Asian characters MUST NOT crash
    logger.info("Test emojis: 🧠 🤖 🚀 and Cyrillic: Привет")


def test_safe_print_handles_unicode_on_charmap_console(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R3: safe_print handles non-encodable characters gracefully."""
    # Test safe_print with emojis
    safe_print("Testing safe print: 🧠 🚀 ✅ ❌ Привет")


def test_openai_provider_handles_unicode_in_headers_and_payload() -> None:
    """R3: OpenAIProvider safely handles Unicode characters in configuration and prompts."""
    provider = OpenAIProvider(
        api_key="sk-test-🔑-key",
        model="gpt-4.1-mini",
        base_url="https://example.com/v1",
        timeout=10.0,
    )

    request = provider._build_request("Prompt with emojis 🧠 and Cyrillic Привет")
    assert isinstance(request.data, bytes)
    # Payload is encoded as valid UTF-8
    decoded_body = json.loads(request.data.decode("utf-8"))
    assert (
        decoded_body["messages"][0]["content"]
        == "Prompt with emojis 🧠 and Cyrillic Привет"
    )

    # Headers must be ASCII/Latin-1 safe
    for header_k, header_v in request.headers.items():
        assert isinstance(header_k, str)
        assert isinstance(header_v, str)
        header_k.encode("latin-1")
        header_v.encode("latin-1")


def test_command_executor_safely_decodes_unicode_output() -> None:
    """R3: CommandExecutor decodes non-ASCII output with errors='replace' without crashing."""
    executor = CommandExecutor(default_timeout=5.0)

    # Run a simple echo command with Unicode on Windows PowerShell / CMD
    result = executor.execute("echo Friday 🤖")
    assert result.exit_code == 0
    assert isinstance(result.stdout, str)


def test_json_repair_unquoted_keys_with_commas_and_colons_inside_strings() -> None:
    """R2: repair_json must not corrupt string literals containing commas and colons."""
    raw = '{desc: "Error: failed, reason: network error", status: "code: 500, detail: timeout"}'
    repaired = repair_json(raw)
    assert repaired == {
        "desc": "Error: failed, reason: network error",
        "status": "code: 500, detail: timeout",
    }


def test_json_repair_embedded_markdown_code_fences() -> None:
    """R2: repair_json preserves code blocks contained inside JSON string fields."""
    raw = '{"code": "```python\\nprint(\'hello\')\\n```", "status": "ok"}'
    repaired = repair_json(raw)
    assert repaired == {
        "code": "```python\nprint('hello')\n```",
        "status": "ok",
    }


def test_json_repair_truncated_mid_token_and_cutoffs() -> None:
    """R2: repair_json recovers mid-token cutoffs and unclosed delimiter stacks."""
    raw_mid_key = '{"tasks": [{"description": "Step 1"}, {"description": "Step 2", "expected_outco'
    repaired_key = repair_json(raw_mid_key)
    assert isinstance(repaired_key, dict)
    assert len(repaired_key["tasks"]) == 2
    assert repaired_key["tasks"][0]["description"] == "Step 1"

    raw_mid_array = '{"status": "ok", "items": [1, 2,'
    assert repair_json(raw_mid_array) == {"status": "ok", "items": [1, 2]}

    raw_mid_colon = '{"status": "ok", "value":'
    assert repair_json(raw_mid_colon) == {"status": "ok", "value": None}


def test_openai_provider_sse_without_space_prefix() -> None:
    """R2: OpenAIProvider correctly parses SSE streams with data: prefix without space."""
    provider = OpenAIProvider(
        api_key="test-key",
        model="gpt-4.1-mini",
        base_url="https://example.com/v1",
    )

    chunk = json.dumps({"choices": [{"delta": {"content": "Hello without space"}}]})
    raw_sse = f"data:{chunk}\n\ndata:[DONE]\n\n"

    payload = provider._parse_payload(raw_sse)
    response = provider._extract_response(payload)
    assert response.content == "Hello without space"


def test_agent_handles_corrupted_tool_call_list_items() -> None:
    """R2: Agent does not crash when response.tool_calls contains non-dict items."""
    provider = MagicMock()
    provider.generate_with_tools.side_effect = [
        LLMResponse(
            content=None,
            tool_calls=["not-a-dict", None, {"name": None, "arguments": "{}"}],  # type: ignore[list-item]
            finish_reason="tool_calls",
        ),
        LLMResponse(content="Done.", finish_reason="stop"),
    ]
    registry = ToolRegistry()
    agent = Agent(llm_provider=provider, tool_registry=registry)

    result = agent.run("Test invalid tool calls")
    assert result == "Done."


def test_safe_stream_handler_ascii_fallback_never_drops_logs() -> None:
    """R3: SafeStreamHandler writes ASCII replacement if stream encoding fails."""

    class StrictAsciiStream(io.StringIO):
        def write(self, s: str) -> int:
            s.encode("ascii")
            return super().write(s)

    mock_stream = StrictAsciiStream()
    handler = SafeStreamHandler(mock_stream)
    handler.setFormatter(logging.Formatter("%(message)s"))

    logger = logging.getLogger("test_strict_ascii_logger")
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    logger.info("Emoji 🚀 and Cyrillic Привет")
    output = mock_stream.getvalue()
    assert "Emoji" in output
    assert "?" in output  # non-ascii replaced with ?


def test_safe_print_custom_file_stream() -> None:
    """R3: safe_print writes to custom file stream safely."""
    custom_stream = io.StringIO()
    safe_print("Test safe print to custom stream: 🚀 Привет", file=custom_stream)
    assert "Test safe print to custom stream:" in custom_stream.getvalue()


def test_json_repair_unquoted_values_and_arrays() -> None:
    """R2: repair_json correctly repairs bare unquoted string literal values and array items."""
    raw_obj = "{status: active, count: 5, enabled: True, desc: 'All ok'}"
    repaired_obj = repair_json(raw_obj)
    assert repaired_obj == {
        "status": "active",
        "count": 5,
        "enabled": True,
        "desc": "All ok",
    }

    raw_arr = "[apple, banana, 42, False, None]"
    repaired_arr = repair_json(raw_arr)
    assert repaired_arr == ["apple", "banana", 42, False, None]


def test_plan_from_json_fault_tolerant_parsing() -> None:
    """R2: Plan.from_json repairs malformed JSON and list structures."""
    raw_plan_malformed = "{goal: 'Deploy service', tasks: [{description: 'Step 1', expected_outcome: 'Pass'},]}"
    plan = Plan.from_json(raw_plan_malformed)
    assert plan.goal == "Deploy service"
    assert len(plan.tasks) == 1
    assert plan.tasks[0].description == "Step 1"

    raw_list_plan = "['Task 1', 'Task 2']"
    plan_list = Plan.from_json(raw_list_plan)
    assert len(plan_list.tasks) == 2
    assert plan_list.tasks[0].description == "Task 1"


def test_conversation_memory_thread_safe_concurrent_access() -> None:
    """R1/R2: ConversationMemory is safe under concurrent reads and writes."""
    memory = ConversationMemory(system_prompt="You are Friday.", max_messages=20)
    errors: list[Exception] = []

    def writer(worker_id: int) -> None:
        try:
            for i in range(25):
                memory.add_user_message(f"Worker {worker_id} msg {i}")
                memory.add_assistant_message(f"Worker {worker_id} reply {i}")
                memory.add_tool_result(f"call_{worker_id}_{i}", f"Result {i}")
        except Exception as exc:
            errors.append(exc)

    def reader() -> None:
        try:
            for _ in range(50):
                _ = memory.get_messages()
                _ = len(memory)
                _ = memory.get_chat("test")
        except Exception as exc:
            errors.append(exc)

    threads = [
        threading.Thread(target=writer, args=(1,)),
        threading.Thread(target=writer, args=(2,)),
        threading.Thread(target=reader),
        threading.Thread(target=reader),
    ]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    assert len(memory.get_messages()) <= 21  # 1 system + max 20 messages


def test_provider_generate_with_tools_empty_or_none_content_fallback() -> None:
    """R1/R2: generate_with_tools handles message histories with None/empty contents cleanly."""
    provider = OpenAIProvider(
        api_key="test-key",
        model="gpt-4.1-mini",
        base_url="https://example.com/v1",
    )

    with patch.object(
        provider,
        "_send_request",
        return_value={"choices": [{"message": {"content": "Fallback ok"}}]},
    ):
        with patch.object(
            provider,
            "_send_request_with_tools",
            side_effect=LLMError("Local model function calling failed"),
        ):
            # Messages with content=None (e.g. initial tool call message)
            messages: list[dict[str, Any]] = [
                {"role": "assistant", "content": None, "tool_calls": [{"id": "c1"}]},
                {"role": "tool", "content": "Tool output", "tool_call_id": "c1"},
            ]
            resp = provider.generate_with_tools(messages=messages, tools=[])
            assert resp.content == "Fallback ok"
