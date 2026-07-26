"""Tests for Friday's LLM abstraction layer."""

from __future__ import annotations

import builtins
import json
from email.message import Message
from typing import Any, Literal, cast
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

from src.config import LLMConfig
from src.llm import (
    AuthenticationError,
    ConfigurationError,
    ConnectionError,
    InvalidResponseError,
    OpenAIProvider,
    TimeoutError,
)


class MockHTTPResponse:
    """Minimal context-manager response stub for urllib tests."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self) -> MockHTTPResponse:
        return self

    def __exit__(
        self,
        exc_type: object,
        exc: object,
        tb: object,
    ) -> Literal[False]:
        return False


def test_provider_initialization_uses_constructor_values() -> None:
    provider = OpenAIProvider(
        api_key="test-key",
        model="gpt-4.1-mini",
        base_url="https://example.com/v1/",
        timeout=15.0,
    )

    assert provider.model_name() == "gpt-4.1-mini"
    assert provider.is_available() is True


def test_provider_initialization_supports_app_config_model() -> None:
    provider = OpenAIProvider.from_config(
        LLMConfig(
            api_key="test-key",
            model="gpt-4.1-mini",
            base_url="https://example.com/v1",
            timeout=12.5,
        )
    )

    assert provider.model_name() == "gpt-4.1-mini"
    assert provider.is_available() is True


def test_successful_generation(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = OpenAIProvider(
        api_key="test-key",
        model="gpt-4.1-mini",
        base_url="https://example.com/v1",
        timeout=15.0,
    )

    def fake_urlopen(request: Request, timeout: float) -> MockHTTPResponse:
        assert timeout == 15.0
        assert request.full_url == "https://example.com/v1/chat/completions"
        assert request.get_method() == "POST"
        assert request.headers["Authorization"] == "Bearer test-key"
        request_body = cast(bytes, request.data)
        payload = json.loads(request_body.decode("utf-8"))
        assert payload == {
            "model": "gpt-4.1-mini",
            "messages": [{"role": "user", "content": "Say hello."}],
        }
        return MockHTTPResponse(
            {"choices": [{"message": {"content": " Hello from Friday. "}}]}
        )

    monkeypatch.setattr("src.llm.openai_provider.urlopen", fake_urlopen)

    response = provider.generate("Say hello.")

    assert response.content == "Hello from Friday."


def test_invalid_configuration_raises_configuration_error() -> None:
    with pytest.raises(ConfigurationError):
        OpenAIProvider(
            api_key="",
            model="gpt-4.1-mini",
            base_url="https://example.com/v1",
        )

    with pytest.raises(ConfigurationError):
        OpenAIProvider(
            api_key="test-key",
            model="gpt-4.1-mini",
            base_url="not-a-url",
        )

    with pytest.raises(ConfigurationError):
        OpenAIProvider(
            api_key="test-key",
            model="gpt-4.1-mini",
            base_url="https://example.com/v1",
            timeout=0,
        )


def test_authentication_failure_raises_authentication_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OpenAIProvider(
        api_key="bad-key",
        model="gpt-4.1-mini",
        base_url="https://example.com/v1",
    )

    def fake_urlopen(request: Request, timeout: float) -> MockHTTPResponse:
        raise HTTPError(
            request.full_url,
            401,
            "Unauthorized",
            hdrs=Message(),
            fp=None,
        )

    monkeypatch.setattr("src.llm.openai_provider.urlopen", fake_urlopen)

    with pytest.raises(AuthenticationError):
        provider.generate("Hello")


def test_network_failure_raises_connection_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OpenAIProvider(
        api_key="test-key",
        model="gpt-4.1-mini",
        base_url="https://example.com/v1",
    )

    def fake_urlopen(request: Request, timeout: float) -> MockHTTPResponse:
        raise URLError("network down")

    monkeypatch.setattr("src.llm.openai_provider.urlopen", fake_urlopen)

    with pytest.raises(ConnectionError):
        provider.generate("Hello")


@pytest.mark.parametrize(
    ("payload", "expected_exception"),
    [
        ({}, InvalidResponseError),
        ({"choices": []}, InvalidResponseError),
        ({"choices": [{"message": {"content": "   "}}]}, InvalidResponseError),
    ],
)
def test_invalid_responses_raise_meaningful_exceptions(
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, Any],
    expected_exception: type[Exception],
) -> None:
    provider = OpenAIProvider(
        api_key="test-key",
        model="gpt-4.1-mini",
        base_url="https://example.com/v1",
    )

    def fake_urlopen(request: Request, timeout: float) -> MockHTTPResponse:
        return MockHTTPResponse(payload)

    monkeypatch.setattr("src.llm.openai_provider.urlopen", fake_urlopen)

    with pytest.raises(expected_exception):
        provider.generate("Hello")


def test_timeout_handling_raises_timeout_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OpenAIProvider(
        api_key="test-key",
        model="gpt-4.1-mini",
        base_url="https://example.com/v1",
        timeout=0.5,
    )

    def fake_urlopen(request: Request, timeout: float) -> MockHTTPResponse:
        raise builtins.TimeoutError("timed out")

    monkeypatch.setattr("src.llm.openai_provider.urlopen", fake_urlopen)

    with pytest.raises(TimeoutError):
        provider.generate("Hello")


def test_exception_propagation_preserves_llm_exception_type() -> None:
    provider = OpenAIProvider(
        api_key="test-key",
        model="gpt-4.1-mini",
        base_url="https://example.com/v1",
    )

    with patch.object(
        provider,
        "_send_request",
        side_effect=InvalidResponseError("invalid payload"),
    ):
        with pytest.raises(InvalidResponseError, match="invalid payload"):
            provider.generate("Hello")
