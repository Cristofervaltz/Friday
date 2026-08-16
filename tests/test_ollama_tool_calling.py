"""Mock-based automated tests for Ollama native tool calling support."""

from __future__ import annotations

import json
from email.message import Message
from typing import Any, Literal, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

from src.config import LLMConfig
from src.core.agent import Agent
from src.core.tool_registry import ToolRegistry
from src.llm import (
    ConfigurationError,
    ConnectionError,
    InvalidResponseError,
    OllamaProvider,
    TimeoutError,
)
from src.tools.base import BaseTool, ToolResult


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

    def __exit__(
        self,
        exc_type: object,
        exc: object,
        tb: object,
    ) -> Literal[False]:
        return False


class WeatherTool(BaseTool):
    """Sample weather tool for testing tool execution."""

    @property
    def name(self) -> str:
        return "get_weather"

    @property
    def description(self) -> str:
        return "Get current weather information for a given location."

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "City or location name",
                },
                "unit": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                    "description": "Temperature unit",
                },
            },
            "required": ["location"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        location = kwargs.get("location", "Unknown")
        unit = kwargs.get("unit", "celsius")
        return ToolResult(
            success=True,
            output=f"The weather in {location} is 22° {unit} and sunny.",
        )


def test_ollama_tools_schema_conversion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that Friday tool schemas are correctly converted to Ollama's schema format."""
    provider = OllamaProvider(
        model="llama3.1",
        base_url="http://localhost:11434",
        timeout=10.0,
    )

    captured_request: dict[str, Any] = {}

    def fake_urlopen(request: Request, timeout: float) -> MockHTTPResponse:
        assert timeout == 10.0
        assert request.full_url == "http://localhost:11434/api/chat"
        assert request.get_method() == "POST"
        request_body = cast(bytes, request.data)
        captured_request.update(json.loads(request_body.decode("utf-8")))

        response_payload = {
            "model": "llama3.1",
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "get_weather",
                            "arguments": {
                                "location": "Tokyo",
                                "unit": "celsius",
                            },
                        }
                    }
                ],
            },
            "done_reason": "stop",
            "done": True,
        }
        return MockHTTPResponse(response_payload)

    monkeypatch.setattr("src.llm.ollama_provider.urlopen", fake_urlopen)

    tool = WeatherTool()
    response = provider.generate_with_tools(
        messages=[{"role": "user", "content": "What is the weather in Tokyo?"}],
        tools=[tool.to_openai_schema()],
    )

    # Verify outgoing payload structure for Ollama /api/chat
    assert captured_request["model"] == "llama3.1"
    assert captured_request["stream"] is False
    assert captured_request["messages"] == [
        {"role": "user", "content": "What is the weather in Tokyo?"}
    ]
    assert len(captured_request["tools"]) == 1
    tool_schema = captured_request["tools"][0]
    assert tool_schema["type"] == "function"
    assert tool_schema["function"]["name"] == "get_weather"
    assert (
        tool_schema["function"]["description"]
        == "Get current weather information for a given location."
    )
    assert tool_schema["function"]["parameters"]["type"] == "object"
    assert "location" in tool_schema["function"]["parameters"]["properties"]
    assert tool_schema["function"]["parameters"]["required"] == ["location"]

    # Verify parsed LLMResponse
    assert response.content is None
    assert response.tool_calls is not None
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0]["name"] == "get_weather"
    assert response.tool_calls[0]["arguments"] == {
        "location": "Tokyo",
        "unit": "celsius",
    }
    assert response.finish_reason == "tool_calls"


def test_ollama_tool_call_response_parsing_dict_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test parsing an Ollama response with dictionary arguments."""
    provider = OllamaProvider(model="llama3.1")

    def fake_urlopen(request: Request, timeout: float) -> MockHTTPResponse:
        return MockHTTPResponse(
            {
                "model": "llama3.1",
                "message": {
                    "role": "assistant",
                    "content": "Looking up weather...",
                    "tool_calls": [
                        {
                            "id": "call_weather_1",
                            "function": {
                                "name": "get_weather",
                                "arguments": {"location": "San Francisco, CA"},
                            },
                        }
                    ],
                },
                "done_reason": "stop",
                "done": True,
            }
        )

    monkeypatch.setattr("src.llm.ollama_provider.urlopen", fake_urlopen)

    response = provider.generate_with_tools(
        messages=[{"role": "user", "content": "Check weather in San Francisco"}],
        tools=[WeatherTool().to_openai_schema()],
    )

    assert response.tool_calls is not None
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0] == {
        "id": "call_weather_1",
        "name": "get_weather",
        "arguments": {"location": "San Francisco, CA"},
    }


def test_ollama_tool_call_response_parsing_string_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test parsing an Ollama response with JSON-encoded string arguments."""
    provider = OllamaProvider(model="llama3.1")

    def fake_urlopen(request: Request, timeout: float) -> MockHTTPResponse:
        return MockHTTPResponse(
            {
                "model": "llama3.1",
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "get_weather",
                                "arguments": '{"location": "London", "unit": "celsius"}',
                            }
                        }
                    ],
                },
                "done_reason": "stop",
                "done": True,
            }
        )

    monkeypatch.setattr("src.llm.ollama_provider.urlopen", fake_urlopen)

    response = provider.generate_with_tools(
        messages=[{"role": "user", "content": "Check London weather"}],
        tools=[WeatherTool().to_openai_schema()],
    )

    assert response.tool_calls is not None
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0]["id"] == "call_1"
    assert response.tool_calls[0]["name"] == "get_weather"
    assert response.tool_calls[0]["arguments"] == {
        "location": "London",
        "unit": "celsius",
    }


def test_ollama_multiple_tool_calls_parsing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test parsing multiple parallel tool calls from Ollama."""
    provider = OllamaProvider(model="llama3.1")

    def fake_urlopen(request: Request, timeout: float) -> MockHTTPResponse:
        return MockHTTPResponse(
            {
                "model": "llama3.1",
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "get_weather",
                                "arguments": {"location": "Tokyo"},
                            }
                        },
                        {
                            "function": {
                                "name": "get_weather",
                                "arguments": {"location": "Paris"},
                            }
                        },
                    ],
                },
                "done_reason": "stop",
                "done": True,
            }
        )

    monkeypatch.setattr("src.llm.ollama_provider.urlopen", fake_urlopen)

    response = provider.generate_with_tools(
        messages=[{"role": "user", "content": "Compare Tokyo and Paris"}],
        tools=[WeatherTool().to_openai_schema()],
    )

    assert response.tool_calls is not None
    assert len(response.tool_calls) == 2
    assert response.tool_calls[0]["id"] == "call_1"
    assert response.tool_calls[0]["name"] == "get_weather"
    assert response.tool_calls[0]["arguments"] == {"location": "Tokyo"}
    assert response.tool_calls[1]["id"] == "call_2"
    assert response.tool_calls[1]["name"] == "get_weather"
    assert response.tool_calls[1]["arguments"] == {"location": "Paris"}


def test_ollama_regular_chat_response_without_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test regular text response when model does not request tool calls."""
    provider = OllamaProvider(model="llama3.1")

    def fake_urlopen(request: Request, timeout: float) -> MockHTTPResponse:
        return MockHTTPResponse(
            {
                "model": "llama3.1",
                "message": {
                    "role": "assistant",
                    "content": "Hello! How can I assist you today?",
                },
                "done_reason": "stop",
                "done": True,
            }
        )

    monkeypatch.setattr("src.llm.ollama_provider.urlopen", fake_urlopen)

    response = provider.generate_with_tools(
        messages=[{"role": "user", "content": "Hello"}],
        tools=[WeatherTool().to_openai_schema()],
    )

    assert response.content == "Hello! How can I assist you today?"
    assert response.tool_calls is None
    assert response.finish_reason == "stop"


def test_ollama_multi_turn_tool_execution_with_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test full multi-turn tool execution loop with Agent, ToolRegistry, and OllamaProvider."""
    provider = OllamaProvider(model="llama3.1")
    registry = ToolRegistry()
    registry.register(WeatherTool())

    requests_sent: list[dict[str, Any]] = []

    def fake_urlopen(request: Request, timeout: float) -> MockHTTPResponse:
        request_body = cast(bytes, request.data)
        data = json.loads(request_body.decode("utf-8"))
        requests_sent.append(data)

        if len(requests_sent) == 1:
            # First turn: model requests tool call
            return MockHTTPResponse(
                {
                    "model": "llama3.1",
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call_tokyo_123",
                                "function": {
                                    "name": "get_weather",
                                    "arguments": {
                                        "location": "Tokyo",
                                        "unit": "celsius",
                                    },
                                },
                            }
                        ],
                    },
                    "done_reason": "stop",
                    "done": True,
                }
            )
        else:
            # Second turn: model receives tool result and provides final text
            return MockHTTPResponse(
                {
                    "model": "llama3.1",
                    "message": {
                        "role": "assistant",
                        "content": "The weather in Tokyo is currently 22° celsius and sunny.",
                    },
                    "done_reason": "stop",
                    "done": True,
                }
            )

    monkeypatch.setattr("src.llm.ollama_provider.urlopen", fake_urlopen)

    agent = Agent(llm_provider=provider, tool_registry=registry)
    result = agent.run("What's the weather in Tokyo?")

    assert result == "The weather in Tokyo is currently 22° celsius and sunny."
    assert len(requests_sent) == 2

    # Verify second turn request formatted messages correctly for Ollama
    second_request_messages = requests_sent[1]["messages"]
    assert len(second_request_messages) == 3

    # Turn 1: User message
    assert second_request_messages[0]["role"] == "user"
    assert second_request_messages[0]["content"] == "What's the weather in Tokyo?"

    # Turn 2: Assistant tool call formatted for Ollama
    assert second_request_messages[1]["role"] == "assistant"
    assert "tool_calls" in second_request_messages[1]
    assert len(second_request_messages[1]["tool_calls"]) == 1
    assert second_request_messages[1]["tool_calls"][0]["function"]["name"] == (
        "get_weather"
    )
    assert second_request_messages[1]["tool_calls"][0]["function"]["arguments"] == {
        "location": "Tokyo",
        "unit": "celsius",
    }

    # Turn 3: Tool result formatted for Ollama
    assert second_request_messages[2]["role"] == "tool"
    assert "22° celsius and sunny" in second_request_messages[2]["content"]


def test_ollama_malformed_arguments_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test recovery from unquoted or malformed JSON in tool call arguments."""
    provider = OllamaProvider(model="llama3.1")

    def fake_urlopen(request: Request, timeout: float) -> MockHTTPResponse:
        return MockHTTPResponse(
            {
                "model": "llama3.1",
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "get_weather",
                                "arguments": "{location: 'Berlin', unit: 'celsius'}",
                            }
                        }
                    ],
                },
                "done_reason": "stop",
                "done": True,
            }
        )

    monkeypatch.setattr("src.llm.ollama_provider.urlopen", fake_urlopen)

    response = provider.generate_with_tools(
        messages=[{"role": "user", "content": "Weather in Berlin"}],
        tools=[WeatherTool().to_openai_schema()],
    )

    assert response.tool_calls is not None
    assert response.tool_calls[0]["name"] == "get_weather"
    assert response.tool_calls[0]["arguments"] == {
        "location": "Berlin",
        "unit": "celsius",
    }


def test_ollama_fallback_to_generate_on_unsupported_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test fallback to text generation when model doesn't support chat tools."""
    provider = OllamaProvider(model="old-model")

    def fake_urlopen(request: Request, timeout: float) -> MockHTTPResponse:
        if "/api/chat" in request.full_url:
            # Model does not support tools
            raise HTTPError(
                request.full_url,
                400,
                "Bad Request: model 'old-model' does not support tools",
                hdrs=Message(),
                fp=None,
            )
        # Fallback to /api/generate
        assert "/api/generate" in request.full_url
        return MockHTTPResponse(
            {
                "model": "old-model",
                "response": "Fallback response from old model.",
                "done": True,
            }
        )

    monkeypatch.setattr("src.llm.ollama_provider.urlopen", fake_urlopen)

    response = provider.generate_with_tools(
        messages=[{"role": "user", "content": "Hi"}],
        tools=[WeatherTool().to_openai_schema()],
    )

    assert response.content == "Fallback response from old model."
    assert response.tool_calls is None


def test_ollama_network_and_timeout_errors_propagated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that ConnectionError and TimeoutError are not swallowed."""
    provider = OllamaProvider(model="llama3.1")

    def fake_timeout(request: Request, timeout: float) -> MockHTTPResponse:
        raise TimeoutError("Request timed out")

    monkeypatch.setattr("src.llm.ollama_provider.urlopen", fake_timeout)

    with pytest.raises(TimeoutError):
        provider.generate_with_tools(
            messages=[{"role": "user", "content": "Hi"}],
            tools=[],
        )

    def fake_conn_error(request: Request, timeout: float) -> MockHTTPResponse:
        raise URLError("Connection refused")

    monkeypatch.setattr("src.llm.ollama_provider.urlopen", fake_conn_error)

    with pytest.raises(ConnectionError):
        provider.generate_with_tools(
            messages=[{"role": "user", "content": "Hi"}],
            tools=[],
        )


def test_ollama_invalid_chat_response_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that invalid payload structures raise InvalidResponseError."""
    provider = OllamaProvider(model="llama3.1")

    # Missing message object
    monkeypatch.setattr(
        "src.llm.ollama_provider.urlopen",
        lambda req, timeout: MockHTTPResponse({"model": "llama3.1"}),
    )
    with pytest.raises(InvalidResponseError):
        provider.generate_with_tools(
            messages=[{"role": "user", "content": "Hi"}],
            tools=[],
        )

    # Empty body
    monkeypatch.setattr(
        "src.llm.ollama_provider.urlopen",
        lambda req, timeout: MockHTTPResponse(""),
    )
    with pytest.raises(InvalidResponseError):
        provider.generate_with_tools(
            messages=[{"role": "user", "content": "Hi"}],
            tools=[],
        )


def test_ollama_streaming_ndjson_tool_calling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test parsing streaming NDJSON response containing tool calls."""
    provider = OllamaProvider(model="llama3.1")

    ndjson_stream = (
        '{"model":"llama3.1","message":{"role":"assistant","content":""},"done":false}\n'
        '{"model":"llama3.1","message":{"role":"assistant","content":"","tool_calls":[{"function":{"name":"get_weather","arguments":{"location":"Berlin"}}}]},"done_reason":"stop","done":true}\n'
    )

    monkeypatch.setattr(
        "src.llm.ollama_provider.urlopen",
        lambda req, timeout: MockHTTPResponse(ndjson_stream),
    )

    response = provider.generate_with_tools(
        messages=[{"role": "user", "content": "Weather in Berlin"}],
        tools=[WeatherTool().to_openai_schema()],
    )

    assert response.tool_calls is not None
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0]["name"] == "get_weather"
    assert response.tool_calls[0]["arguments"] == {"location": "Berlin"}
    assert response.finish_reason == "tool_calls"


def test_ollama_streaming_ndjson_text_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test parsing streaming NDJSON response from text generation."""
    provider = OllamaProvider(model="llama2")

    ndjson_stream = (
        '{"model":"llama2","response":"Hello ","done":false}\n'
        '{"model":"llama2","response":"world!","done":true}\n'
    )

    monkeypatch.setattr(
        "src.llm.ollama_provider.urlopen",
        lambda req, timeout: MockHTTPResponse(ndjson_stream),
    )

    result = provider.generate("Hi")
    assert result == "Hello world!"


def test_ollama_streaming_sse_tool_calling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test parsing SSE stream responses (e.g. from reverse proxies or gateways)."""
    provider = OllamaProvider(model="llama3.1")

    sse_stream = (
        'data: {"model":"llama3.1","message":{"role":"assistant","content":""},"done":false}\n'
        'data: {"model":"llama3.1","message":{"role":"assistant","content":"","tool_calls":[{"id":"call_99","function":{"name":"get_weather","arguments":"{\\"location\\": \\"Rome\\"}"}}]},"done_reason":"stop","done":true}\n'
        "data: [DONE]\n"
    )

    monkeypatch.setattr(
        "src.llm.ollama_provider.urlopen",
        lambda req, timeout: MockHTTPResponse(sse_stream),
    )

    response = provider.generate_with_tools(
        messages=[{"role": "user", "content": "Weather in Rome"}],
        tools=[WeatherTool().to_openai_schema()],
    )

    assert response.tool_calls is not None
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0]["id"] == "call_99"
    assert response.tool_calls[0]["name"] == "get_weather"
    assert response.tool_calls[0]["arguments"] == {"location": "Rome"}


def test_ollama_primitive_string_arguments_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that primitive JSON string arguments (not dicts) safely fallback to empty dict."""
    provider = OllamaProvider(model="llama3.1")

    monkeypatch.setattr(
        "src.llm.ollama_provider.urlopen",
        lambda req, timeout: MockHTTPResponse(
            {
                "model": "llama3.1",
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "get_weather",
                                "arguments": '"just a string primitive"',
                            }
                        }
                    ],
                },
                "done_reason": "stop",
                "done": True,
            }
        ),
    )

    response = provider.generate_with_tools(
        messages=[{"role": "user", "content": "Weather"}],
        tools=[WeatherTool().to_openai_schema()],
    )

    assert response.tool_calls is not None
    assert response.tool_calls[0]["arguments"] == {}


def test_ollama_format_messages_role_and_images(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that role 'function' is mapped to 'tool' and images are preserved."""
    provider = OllamaProvider(model="llama3.1")

    captured_payload: dict[str, Any] = {}

    def fake_urlopen(request: Request, timeout: float) -> MockHTTPResponse:
        request_body = cast(bytes, request.data)
        captured_payload.update(json.loads(request_body.decode("utf-8")))
        return MockHTTPResponse(
            {
                "model": "llama3.1",
                "message": {
                    "role": "assistant",
                    "content": "All messages received.",
                },
                "done_reason": "stop",
                "done": True,
            }
        )

    monkeypatch.setattr("src.llm.ollama_provider.urlopen", fake_urlopen)

    input_messages: list[dict[str, Any]] = [
        {"role": "system", "content": "You are Friday."},
        {
            "role": "user",
            "content": "Look at this image",
            "images": ["base64_encoded_image_data"],
        },
        {"role": "function", "content": "Function result from legacy caller"},
    ]

    response = provider.generate_with_tools(messages=input_messages, tools=[])
    assert response.content == "All messages received."

    messages = captured_payload.get("messages", [])
    assert len(messages) == 3
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert messages[1]["images"] == ["base64_encoded_image_data"]
    assert messages[2]["role"] == "tool"
    assert messages[2]["content"] == "Function result from legacy caller"


def test_ollama_format_tools_edge_cases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test tool formatting with None parameters and diverse schema shapes."""
    provider = OllamaProvider(model="llama3.1")

    captured_payload: dict[str, Any] = {}

    def fake_urlopen(request: Request, timeout: float) -> MockHTTPResponse:
        request_body = cast(bytes, request.data)
        captured_payload.update(json.loads(request_body.decode("utf-8")))
        return MockHTTPResponse(
            {
                "model": "llama3.1",
                "message": {
                    "role": "assistant",
                    "content": "Tools received.",
                },
                "done_reason": "stop",
                "done": True,
            }
        )

    monkeypatch.setattr("src.llm.ollama_provider.urlopen", fake_urlopen)

    tools: list[Any] = [
        # Tool with None parameters
        {
            "type": "function",
            "function": {
                "name": "tool_with_none_params",
                "description": "None params test",
                "parameters": None,
            },
        },
        # Flat dict tool
        {
            "name": "flat_tool",
            "description": "Flat tool test",
            "parameters": {"properties": {"arg": {"type": "string"}}},
        },
        # Invalid tool without name (should be skipped)
        {"type": "function", "function": {"name": "", "description": "No name"}},
        # Non-dict item (should be skipped)
        "invalid_tool_string",
    ]

    provider.generate_with_tools(
        messages=[{"role": "user", "content": "Hi"}],
        tools=cast(list[dict[str, Any]], tools),
    )

    formatted_tools = captured_payload.get("tools", [])
    assert len(formatted_tools) == 2

    assert formatted_tools[0]["function"]["name"] == "tool_with_none_params"
    assert formatted_tools[0]["function"]["parameters"] == {
        "type": "object",
        "properties": {},
    }

    assert formatted_tools[1]["function"]["name"] == "flat_tool"
    assert formatted_tools[1]["function"]["parameters"]["type"] == "object"
    assert "arg" in formatted_tools[1]["function"]["parameters"]["properties"]


def test_ollama_multi_turn_conversation_with_followup_and_prior_tool_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test multi-turn user conversation preserving prior assistant tool calls and results."""
    provider = OllamaProvider(model="llama3.1")
    registry = ToolRegistry()
    registry.register(WeatherTool())

    requests_sent: list[dict[str, Any]] = []

    def fake_urlopen(request: Request, timeout: float) -> MockHTTPResponse:
        data = json.loads(cast(bytes, request.data).decode("utf-8"))
        requests_sent.append(data)

        turn_count = len(requests_sent)
        if turn_count == 1:
            # Turn 1: model calls get_weather for Tokyo
            return MockHTTPResponse(
                {
                    "model": "llama3.1",
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "get_weather",
                                    "arguments": {"location": "Tokyo"},
                                }
                            }
                        ],
                    },
                    "done_reason": "stop",
                    "done": True,
                }
            )
        elif turn_count == 2:
            # Turn 1 final answer
            return MockHTTPResponse(
                {
                    "model": "llama3.1",
                    "message": {
                        "role": "assistant",
                        "content": "The weather in Tokyo is 22° celsius and sunny.",
                    },
                    "done_reason": "stop",
                    "done": True,
                }
            )
        elif turn_count == 3:
            # Turn 2: user follow up -> model calls get_weather for Paris
            return MockHTTPResponse(
                {
                    "model": "llama3.1",
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "get_weather",
                                    "arguments": {"location": "Paris"},
                                }
                            }
                        ],
                    },
                    "done_reason": "stop",
                    "done": True,
                }
            )
        else:
            # Turn 2 final answer
            return MockHTTPResponse(
                {
                    "model": "llama3.1",
                    "message": {
                        "role": "assistant",
                        "content": "The weather in Paris is 22° celsius and sunny.",
                    },
                    "done_reason": "stop",
                    "done": True,
                }
            )

    monkeypatch.setattr("src.llm.ollama_provider.urlopen", fake_urlopen)

    agent = Agent(llm_provider=provider, tool_registry=registry)

    # First user message
    res1 = agent.run("Weather in Tokyo?")
    assert res1 == "The weather in Tokyo is 22° celsius and sunny."

    # Second user message in same conversation
    res2 = agent.run("What about Paris?")
    assert res2 == "The weather in Paris is 22° celsius and sunny."

    assert len(requests_sent) == 4

    # Verify message structure in the 4th request (Turn 2 final answer)
    turn_4_msgs = requests_sent[3]["messages"]
    assert len(turn_4_msgs) == 7
    assert turn_4_msgs[0] == {"role": "user", "content": "Weather in Tokyo?"}
    assert turn_4_msgs[1]["role"] == "assistant"
    assert turn_4_msgs[1]["tool_calls"][0]["function"]["name"] == "get_weather"
    assert turn_4_msgs[2]["role"] == "tool"
    assert "Tokyo" in turn_4_msgs[2]["content"]
    assert turn_4_msgs[3]["role"] == "assistant"
    assert "Tokyo is 22° celsius" in turn_4_msgs[3]["content"]
    assert turn_4_msgs[4] == {"role": "user", "content": "What about Paris?"}
    assert turn_4_msgs[5]["role"] == "assistant"
    assert turn_4_msgs[5]["tool_calls"][0]["function"]["name"] == "get_weather"
    assert turn_4_msgs[6]["role"] == "tool"
    assert "Paris" in turn_4_msgs[6]["content"]


def test_ollama_thinking_tags_handling_with_tool_calls_and_final_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test handling thinking tags from reasoning models (e.g. DeepSeek-R1, Qwen-2.5)."""
    provider = OllamaProvider(model="deepseek-r1:8b")

    # Step 1: Tool call accompanied by thinking process content
    thinking_tool_response = {
        "model": "deepseek-r1:8b",
        "message": {
            "role": "assistant",
            "content": "<think>\nUser asked about Tokyo weather.\nI must invoke get_weather.\n</think>",
            "tool_calls": [
                {
                    "function": {
                        "name": "get_weather",
                        "arguments": {"location": "Tokyo"},
                    }
                }
            ],
        },
        "done_reason": "stop",
        "done": True,
    }

    monkeypatch.setattr(
        "src.llm.ollama_provider.urlopen",
        lambda req, timeout: MockHTTPResponse(thinking_tool_response),
    )

    resp = provider.generate_with_tools(
        messages=[{"role": "user", "content": "Check Tokyo weather"}],
        tools=[WeatherTool().to_openai_schema()],
    )

    assert resp.tool_calls is not None
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0]["name"] == "get_weather"
    assert "<think>" in str(resp.content)
    assert resp.finish_reason == "tool_calls"

    # Step 2: Final response containing thinking process content
    final_thinking_response = {
        "model": "deepseek-r1:8b",
        "message": {
            "role": "assistant",
            "content": "<think>\nTool output received: 22C.\nFormatting response.\n</think>\nTokyo is currently 22°C.",
        },
        "done_reason": "stop",
        "done": True,
    }

    monkeypatch.setattr(
        "src.llm.ollama_provider.urlopen",
        lambda req, timeout: MockHTTPResponse(final_thinking_response),
    )

    resp_final = provider.generate_with_tools(
        messages=[
            {"role": "user", "content": "Check Tokyo weather"},
            {"role": "tool", "content": "22C"},
        ],
        tools=[],
    )

    assert resp_final.tool_calls is None
    assert "Tokyo is currently 22°C." in (resp_final.content or "")


def test_ollama_nested_arguments_and_json_structures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test tool call parsing with deeply nested dictionaries and list arguments."""
    provider = OllamaProvider(model="llama3.1")

    payload = {
        "model": "llama3.1",
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "function": {
                        "name": "complex_query",
                        "arguments": {
                            "filters": {
                                "tags": ["prod", "db"],
                                "metadata": {"region": "us-east-1", "active": True},
                            },
                            "limit": 50,
                        },
                    }
                }
            ],
        },
        "done_reason": "stop",
        "done": True,
    }

    monkeypatch.setattr(
        "src.llm.ollama_provider.urlopen",
        lambda req, timeout: MockHTTPResponse(payload),
    )

    response = provider.generate_with_tools(
        messages=[{"role": "user", "content": "Run query"}],
        tools=[],
    )

    assert response.tool_calls is not None
    args = response.tool_calls[0]["arguments"]
    assert args["filters"]["tags"] == ["prod", "db"]
    assert args["filters"]["metadata"]["region"] == "us-east-1"
    assert args["limit"] == 50


def test_ollama_empty_or_whitespace_chat_response_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that pure whitespace or empty chat response raises InvalidResponseError."""
    provider = OllamaProvider(model="llama3.1")

    # Whitespace message with no tool calls
    monkeypatch.setattr(
        "src.llm.ollama_provider.urlopen",
        lambda req, timeout: MockHTTPResponse(
            {
                "model": "llama3.1",
                "message": {"role": "assistant", "content": "    \n\t   "},
                "done_reason": "stop",
                "done": True,
            }
        ),
    )

    # When tools are provided, it will attempt fallback to /api/generate
    # We make urlopen also return whitespace on fallback to test InvalidResponseError
    with pytest.raises(InvalidResponseError):
        provider.generate_with_tools(
            messages=[{"role": "user", "content": "Hello"}],
            tools=[],
        )


def test_ollama_configuration_validation() -> None:
    """Test configuration validation and edge cases for OllamaProvider."""
    # Valid default config
    p1 = OllamaProvider()
    assert p1.is_available() is True
    assert p1.model_name() == "llama2"

    # From LLMConfig
    config = LLMConfig(model="mistral", base_url="http://127.0.0.1:11434", timeout=15.0)
    p2 = OllamaProvider.from_config(config)
    assert p2.model_name() == "mistral"
    assert p2._base_url == "http://127.0.0.1:11434"
    assert p2._timeout == 15.0

    # Invalid timeout
    with pytest.raises(ConfigurationError):
        OllamaProvider(timeout=0)

    with pytest.raises(ConfigurationError):
        OllamaProvider(timeout=-10.0)

    # Base URL with trailing slash or whitespace
    p3 = OllamaProvider(base_url="  http://localhost:11434///  ")
    assert p3._base_url == "http://localhost:11434"

    # Empty base URL safely defaults
    p4 = OllamaProvider(base_url="   ")
    assert p4._base_url == "http://localhost:11434"


def test_ollama_dict_and_list_message_content_formatting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that dictionary or list content in messages is serialized as valid JSON."""
    provider = OllamaProvider(model="llama3.1")

    captured_payload: dict[str, Any] = {}

    def fake_urlopen(request: Request, timeout: float) -> MockHTTPResponse:
        captured_payload.update(json.loads(cast(bytes, request.data).decode("utf-8")))
        return MockHTTPResponse(
            {
                "model": "llama3.1",
                "message": {"role": "assistant", "content": "Done."},
                "done_reason": "stop",
                "done": True,
            }
        )

    monkeypatch.setattr("src.llm.ollama_provider.urlopen", fake_urlopen)

    input_messages: list[dict[str, Any]] = [
        {"role": "user", "content": "Analyze data"},
        {
            "role": "tool",
            "content": {"status": "success", "count": 42},  # type: ignore[dict-item]
        },
        {
            "role": "tool",
            "content": ["item1", "item2"],  # type: ignore[dict-item]
        },
    ]

    provider.generate_with_tools(messages=input_messages, tools=[])

    msgs = captured_payload.get("messages", [])
    assert len(msgs) == 3
    # Check valid JSON serialization
    parsed_content1 = json.loads(msgs[1]["content"])
    assert parsed_content1 == {"status": "success", "count": 42}
    parsed_content2 = json.loads(msgs[2]["content"])
    assert parsed_content2 == ["item1", "item2"]


def test_ollama_tool_schema_sanitization_immutability() -> None:
    """Test that _format_tools does not mutate caller's original tool dictionary."""
    provider = OllamaProvider(model="llama3.1")

    original_params = {"properties": {"city": {"type": "string"}}}
    original_tool = {
        "type": "function",
        "function": {
            "name": "search_city",
            "description": "Search city",
            "parameters": original_params,
        },
    }

    formatted = provider._format_tools([original_tool])
    assert len(formatted) == 1
    # Formatted output has type: object
    assert formatted[0]["function"]["parameters"]["type"] == "object"
    # Original params dict was NOT mutated in-place
    assert "type" not in original_params


def test_ollama_parallel_tool_calls_multi_turn_with_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test Agent execution loop with parallel tool calls from Ollama."""
    provider = OllamaProvider(model="llama3.1")
    registry = ToolRegistry()
    registry.register(WeatherTool())

    requests_sent: list[dict[str, Any]] = []

    def fake_urlopen(request: Request, timeout: float) -> MockHTTPResponse:
        data = json.loads(cast(bytes, request.data).decode("utf-8"))
        requests_sent.append(data)

        if len(requests_sent) == 1:
            # First turn: 2 parallel tool calls
            return MockHTTPResponse(
                {
                    "model": "llama3.1",
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call_tokyo",
                                "function": {
                                    "name": "get_weather",
                                    "arguments": {"location": "Tokyo"},
                                },
                            },
                            {
                                "id": "call_paris",
                                "function": {
                                    "name": "get_weather",
                                    "arguments": {"location": "Paris"},
                                },
                            },
                        ],
                    },
                    "done_reason": "stop",
                    "done": True,
                }
            )
        else:
            # Second turn: final answer combining both results
            return MockHTTPResponse(
                {
                    "model": "llama3.1",
                    "message": {
                        "role": "assistant",
                        "content": "Tokyo is 22° and Paris is 22°.",
                    },
                    "done_reason": "stop",
                    "done": True,
                }
            )

    monkeypatch.setattr("src.llm.ollama_provider.urlopen", fake_urlopen)

    agent = Agent(llm_provider=provider, tool_registry=registry)
    result = agent.run("Compare Tokyo and Paris weather")

    assert result == "Tokyo is 22° and Paris is 22°."
    assert len(requests_sent) == 2

    second_turn_msgs = requests_sent[1]["messages"]
    # User message + Assistant tool calls + Tool result 1 + Tool result 2
    assert len(second_turn_msgs) == 4
    assert second_turn_msgs[0]["role"] == "user"
    assert second_turn_msgs[1]["role"] == "assistant"
    assert len(second_turn_msgs[1]["tool_calls"]) == 2
    assert second_turn_msgs[2]["role"] == "tool"
    assert "Tokyo" in second_turn_msgs[2]["content"]
    assert second_turn_msgs[3]["role"] == "tool"
    assert "Paris" in second_turn_msgs[3]["content"]


def test_ollama_generate_vs_generate_with_tools_empty_and_none_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test behavior comparison between generate, generate_with_tools(tools=[]), and generate_with_tools(tools=None)."""
    provider = OllamaProvider(model="llama3.1")
    captured_requests: list[dict[str, Any]] = []

    def fake_urlopen(request: Request, timeout: float) -> MockHTTPResponse:
        data = json.loads(cast(bytes, request.data).decode("utf-8"))
        data["_endpoint"] = request.full_url
        captured_requests.append(data)

        if "/api/generate" in request.full_url:
            return MockHTTPResponse(
                {"model": "llama3.1", "response": "Generate output", "done": True}
            )
        else:
            return MockHTTPResponse(
                {
                    "model": "llama3.1",
                    "message": {
                        "role": "assistant",
                        "content": "Chat output",
                    },
                    "done_reason": "stop",
                    "done": True,
                }
            )

    monkeypatch.setattr("src.llm.ollama_provider.urlopen", fake_urlopen)

    # 1. Plain generate
    resp_gen = provider.generate("Tell me a fact")
    assert resp_gen == "Generate output"
    assert "/api/generate" in captured_requests[0]["_endpoint"]
    assert captured_requests[0]["prompt"] == "Tell me a fact"
    assert "tools" not in captured_requests[0]
    assert "messages" not in captured_requests[0]

    # 2. generate_with_tools with tools=[]
    resp_empty = provider.generate_with_tools(
        messages=[{"role": "user", "content": "Hello"}],
        tools=[],
    )
    assert resp_empty.content == "Chat output"
    assert "/api/chat" in captured_requests[1]["_endpoint"]
    assert captured_requests[1]["messages"] == [{"role": "user", "content": "Hello"}]
    assert "tools" not in captured_requests[1]

    # 3. generate_with_tools with tools=None
    resp_none = provider.generate_with_tools(
        messages=[{"role": "user", "content": "Hello again"}],
        tools=None,
    )
    assert resp_none.content == "Chat output"
    assert "/api/chat" in captured_requests[2]["_endpoint"]
    assert captured_requests[2]["messages"] == [
        {"role": "user", "content": "Hello again"}
    ]
    assert "tools" not in captured_requests[2]

    # 4. generate_with_tools with messages=None and tools=None
    resp_null_all = provider.generate_with_tools(
        messages=cast(Any, None),
        tools=None,
    )
    assert resp_null_all.content == "Chat output"
    assert captured_requests[3]["messages"] == []
    assert "tools" not in captured_requests[3]


def test_ollama_model_options_passed_to_chat_and_generate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that model options (temperature, num_predict, top_p, etc.) are passed to payloads."""
    options = {
        "temperature": 0.2,
        "num_predict": 128,
        "top_p": 0.9,
        "stop": ["\n\n"],
    }
    provider = OllamaProvider(
        model="llama3.1",
        options=options,
    )

    captured_requests: list[dict[str, Any]] = []

    def fake_urlopen(request: Request, timeout: float) -> MockHTTPResponse:
        data = json.loads(cast(bytes, request.data).decode("utf-8"))
        captured_requests.append(data)
        if "/api/generate" in request.full_url:
            return MockHTTPResponse(
                {"model": "llama3.1", "response": "Generated text", "done": True}
            )
        return MockHTTPResponse(
            {
                "model": "llama3.1",
                "message": {
                    "role": "assistant",
                    "content": "Chat text",
                },
                "done_reason": "stop",
                "done": True,
            }
        )

    monkeypatch.setattr("src.llm.ollama_provider.urlopen", fake_urlopen)

    # Check generate payload
    provider.generate("Test prompt")
    assert len(captured_requests) == 1
    assert captured_requests[0]["options"] == {
        "temperature": 0.2,
        "num_predict": 128,
        "top_p": 0.9,
        "stop": ["\n\n"],
    }

    # Check generate_with_tools payload
    provider.generate_with_tools(
        messages=[{"role": "user", "content": "Hi"}],
        tools=[WeatherTool().to_openai_schema()],
    )
    assert len(captured_requests) == 2
    assert captured_requests[1]["options"] == {
        "temperature": 0.2,
        "num_predict": 128,
        "top_p": 0.9,
        "stop": ["\n\n"],
    }


def test_ollama_model_options_immutability() -> None:
    """Test that mutating the caller's options dict does not alter provider internal options."""
    caller_options = {"temperature": 0.7, "num_predict": 256}
    provider = OllamaProvider(options=caller_options)

    # Mutate original caller dictionary
    caller_options["temperature"] = 0.0
    caller_options["new_param"] = 42

    assert provider._options == {"temperature": 0.7, "num_predict": 256}
    assert "new_param" not in provider._options


def test_ollama_fallback_with_none_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test fallback generation with None messages list."""
    provider = OllamaProvider(model="fallback-model")

    captured_requests: list[dict[str, Any]] = []

    def fake_urlopen(request: Request, timeout: float) -> MockHTTPResponse:
        captured_requests.append(json.loads(cast(bytes, request.data).decode("utf-8")))
        return MockHTTPResponse(
            {
                "model": "fallback-model",
                "response": "Recovered fallback answer.",
                "done": True,
            }
        )

    monkeypatch.setattr("src.llm.ollama_provider.urlopen", fake_urlopen)

    result = provider._fallback_generate(
        messages=None,
        started_at=0.0,
        exc=RuntimeError("simulated error"),
    )
    assert result.content == "Recovered fallback answer."
    assert captured_requests[0]["prompt"] == "Please proceed."
