"""OpenAI-compatible LLM provider implementation for Friday."""

from __future__ import annotations

import builtins
import json
import logging
import time
from json import JSONDecodeError
from time import perf_counter
from typing import Any, Self
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from src.config import LLMConfig
from src.constants import APP_NAME
from src.logger import LoggerFactory
from src.utils.json_repair import repair_json

from .base import BaseLLMProvider, LLMResponse
from .exceptions import (
    AuthenticationError,
    ConfigurationError,
    ConnectionError,
    InvalidResponseError,
    LLMError,
    TimeoutError,
)

_JSON_HEADERS = {
    "Authorization": "Bearer {api_key}",
    "Content-Type": "application/json",
    "User-Agent": "Friday-Agent/1.0",
    "HTTP-Referer": "https://github.com/friday-ai",
    "X-Title": "Friday AI Agent",
}


class OpenAIProvider(BaseLLMProvider):
    """Provider for OpenAI-compatible chat completion endpoints."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        retry_delay: float | None = None,
        config: LLMConfig | None = None,
    ) -> None:
        resolved_config = config or LLMConfig()
        self._api_key = self._require_non_empty(
            api_key if api_key is not None else resolved_config.api_key,
            field_name="api_key",
        )
        self._model = self._require_non_empty(
            model if model is not None else resolved_config.model,
            field_name="model",
        )
        self._base_url = self._normalize_base_url(
            base_url if base_url is not None else resolved_config.base_url,
        )
        self._timeout = self._validate_timeout(
            timeout if timeout is not None else resolved_config.timeout,
        )
        self._max_retries = (
            max_retries
            if max_retries is not None
            else getattr(resolved_config, "max_retries", 3)
        )
        self._retry_delay = (
            retry_delay
            if retry_delay is not None
            else getattr(resolved_config, "retry_delay", 0.5)
        )
        self._logger = _get_logger("llm.openai_provider")

        self._logger.info(
            "Initialized OpenAIProvider model=%s base_url=%s timeout=%s retries=%s",
            self._model,
            self._base_url,
            self._timeout,
            self._max_retries,
        )

    @classmethod
    def from_config(cls, config: LLMConfig) -> Self:
        """Construct a provider directly from Friday's configuration model."""
        return cls(config=config)

    def generate(self, prompt: str) -> str:
        """Generate a single response using the configured chat completions API."""
        normalized_prompt = self.validate_prompt(prompt)
        started_at = perf_counter()

        self._logger.info(
            "LLM request started model=%s prompt_length=%d",
            self._model,
            len(normalized_prompt),
        )

        try:
            payload = self._send_request(normalized_prompt)
            response_text = self._extract_text(payload)
        except LLMError:
            duration_ms = (perf_counter() - started_at) * 1000
            self._logger.exception(
                "LLM request failed model=%s duration_ms=%.2f",
                self._model,
                duration_ms,
            )
            raise

        duration_ms = (perf_counter() - started_at) * 1000
        self._logger.info(
            "LLM request finished model=%s duration_ms=%.2f",
            self._model,
            duration_ms,
        )
        return response_text

    def generate_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        """Generate response with function calling support.

        Args:
            messages: Conversation history in OpenAI format.
            tools: Available tools in OpenAI function calling format.

        Returns:
            LLMResponse with content or tool calls.
        """
        started_at = perf_counter()

        self._logger.info(
            "LLM request with tools started model=%s tools_count=%d",
            self._model,
            len(tools),
        )

        try:
            payload = self._send_request_with_tools(messages, tools)
            response = self._extract_response(payload)
        except (AuthenticationError, ConnectionError, TimeoutError):
            # Fast fail without redundant fallback when credentials or network fail
            duration_ms = (perf_counter() - started_at) * 1000
            self._logger.exception(
                "LLM request with tools failed with network/auth error model=%s duration_ms=%.2f",
                self._model,
                duration_ms,
            )
            raise
        except LLMError as exc:
            self._logger.warning(
                f"LLM request with tools failed ({exc}). "
                "Retrying without tools (useful for local models)."
            )
            # Fallback to text generation
            prompt_parts = []
            for m in messages:
                role = m.get("role", "user")
                content = m.get("content")
                if content:
                    prompt_parts.append(f"{role}: {content}")
            prompt = "\n".join(prompt_parts) if prompt_parts else "Please proceed."
            try:
                fallback_payload = self._send_request(prompt)
                fallback_text = self._extract_text(fallback_payload)
                response = LLMResponse(content=fallback_text)
            except LLMError:
                duration_ms = (perf_counter() - started_at) * 1000
                self._logger.exception(
                    "LLM fallback request failed model=%s duration_ms=%.2f",
                    self._model,
                    duration_ms,
                )
                raise
        except Exception:
            duration_ms = (perf_counter() - started_at) * 1000
            self._logger.exception(
                "LLM request with tools failed unexpectedly model=%s duration_ms=%.2f",
                self._model,
                duration_ms,
            )
            raise

        duration_ms = (perf_counter() - started_at) * 1000
        self._logger.info(
            "LLM request with tools finished model=%s duration_ms=%.2f",
            self._model,
            duration_ms,
        )
        return response

    def is_available(self) -> bool:
        """Return whether the provider has a valid configuration."""
        return all((self._api_key, self._model, self._base_url)) and self._timeout > 0

    def model_name(self) -> str:
        """Return the configured upstream model name."""
        return self._model

    def _send_http_with_retry(self, request: Request) -> str:
        """Send HTTP request with retry mechanism for transient network errors."""
        last_exception: Exception | None = None
        max_attempts = max(1, self._max_retries)

        for attempt in range(1, max_attempts + 1):
            try:
                with urlopen(request, timeout=self._timeout) as response:
                    raw_bytes: bytes = response.read()
                    return raw_bytes.decode("utf-8", errors="replace")
            except HTTPError as exc:
                error_body = ""
                try:
                    error_body = exc.read().decode("utf-8", errors="replace")
                except Exception:
                    pass

                # Non-retryable auth failures
                if exc.code in {401, 403}:
                    raise AuthenticationError(
                        f"LLM authentication failed. {error_body}"
                    ) from None

                # Non-retryable 4xx client errors (except 429 rate limit)
                if 400 <= exc.code < 500 and exc.code != 429:
                    raise ConnectionError(
                        f"LLM request failed with status code {exc.code}. Body: {error_body}"
                    ) from None

                last_exception = ConnectionError(
                    f"LLM request failed with status code {exc.code}. Body: {error_body}"
                )

                if attempt < max_attempts:
                    self._logger.warning(
                        "LLM HTTP error %d (attempt %d/%d). Retrying in %.2fs...",
                        exc.code,
                        attempt,
                        max_attempts,
                        self._retry_delay,
                    )
                    time.sleep(self._retry_delay)
                else:
                    raise last_exception from None

            except builtins.TimeoutError:
                last_exception = TimeoutError("LLM request timed out.")
                if attempt < max_attempts:
                    self._logger.warning(
                        "LLM request timed out (attempt %d/%d). Retrying in %.2fs...",
                        attempt,
                        max_attempts,
                        self._retry_delay,
                    )
                    time.sleep(self._retry_delay)
                else:
                    raise last_exception from None

            except TimeoutError as exc:
                last_exception = exc
                if attempt < max_attempts:
                    self._logger.warning(
                        "LLM request timed out (attempt %d/%d). Retrying in %.2fs...",
                        attempt,
                        max_attempts,
                        self._retry_delay,
                    )
                    time.sleep(self._retry_delay)
                else:
                    raise last_exception from None

            except URLError as exc:
                if (
                    isinstance(exc.reason, builtins.TimeoutError)
                    or "timed out" in str(exc.reason).lower()
                ):
                    last_exception = TimeoutError("LLM request timed out.")
                else:
                    last_exception = ConnectionError(
                        f"LLM connection failed: {exc.reason}"
                    )

                if attempt < max_attempts:
                    self._logger.warning(
                        "LLM connection error: %s (attempt %d/%d). Retrying in %.2fs...",
                        exc.reason,
                        attempt,
                        max_attempts,
                        self._retry_delay,
                    )
                    time.sleep(self._retry_delay)
                else:
                    raise last_exception from None

            except OSError as exc:
                last_exception = ConnectionError(f"LLM connection failed: {exc}")
                if attempt < max_attempts:
                    self._logger.warning(
                        "LLM socket error: %s (attempt %d/%d). Retrying in %.2fs...",
                        exc,
                        attempt,
                        max_attempts,
                        self._retry_delay,
                    )
                    time.sleep(self._retry_delay)
                else:
                    raise last_exception from None

        if last_exception is not None:
            raise last_exception
        raise ConnectionError("LLM request failed after retries.")

    def _build_safe_headers(self) -> dict[str, str]:
        """Build HTTP headers with safe encoding to prevent UnicodeEncodeError."""
        headers = {}
        for key, value in _JSON_HEADERS.items():
            rendered = value.format(api_key=self._api_key)
            safe_key = key.encode("latin-1", errors="ignore").decode("latin-1")
            safe_val = rendered.encode("latin-1", errors="replace").decode("latin-1")
            headers[safe_key] = safe_val
        return headers

    def _send_request(self, prompt: str) -> dict[str, Any]:
        request = self._build_request(prompt)
        raw_response = self._send_http_with_retry(request)
        return self._parse_payload(raw_response)

    def _send_request_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Send request with tools to the API."""
        payload = {
            "model": self._model,
            "messages": messages,
            "tools": tools,
            "stream": False,
        }
        request_body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request_headers = self._build_safe_headers()
        request = Request(
            url=f"{self._base_url}/chat/completions",
            data=request_body,
            headers=request_headers,
            method="POST",
        )

        raw_response = self._send_http_with_retry(request)
        return self._parse_payload(raw_response)

    def _build_request(self, prompt: str) -> Request:
        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
        request_body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request_headers = self._build_safe_headers()

        return Request(
            url=f"{self._base_url}/chat/completions",
            data=request_body,
            headers=request_headers,
            method="POST",
        )

    def _parse_payload(self, raw_response: str) -> dict[str, Any]:
        if not raw_response.strip():
            raise InvalidResponseError("LLM response body was empty.")

        try:
            payload = json.loads(raw_response)
        except json.JSONDecodeError as exc:
            # Fallback for OmniRoute / proxies that force SSE (stream: true)
            # even when stream: false is requested.
            if "data:" in raw_response:
                try:
                    return self._parse_sse_to_payload(raw_response)
                except Exception as sse_exc:
                    self._logger.error(f"Failed to parse SSE fallback: {sse_exc}")
                    pass

            # Local JSON repair attempt
            try:
                repaired = repair_json(raw_response)
                if isinstance(repaired, dict) and repaired:
                    return repaired
            except Exception:
                pass

            preview = raw_response[:200]
            raise InvalidResponseError(
                f"LLM response was not valid JSON. Response starts with:\n```\n{preview}\n```"
            ) from exc

        if not isinstance(payload, dict) or not payload:
            raise InvalidResponseError("LLM response payload was invalid.")
        return payload

    def _parse_sse_to_payload(self, raw_response: str) -> dict[str, Any]:
        """Convert an SSE stream response into a single unified JSON payload."""
        full_content = ""
        tool_calls: dict[int, dict[str, Any]] = {}
        finish_reason = "stop"

        for line in raw_response.splitlines():
            line = line.strip()
            if not line.startswith("data:"):
                continue
            data_str = line[5:].strip()
            if data_str == "[DONE]":
                break

            try:
                chunk = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            choices = chunk.get("choices", [])
            if not choices:
                continue
            delta = choices[0].get("delta", {})

            if "content" in delta and delta["content"]:
                full_content += delta["content"]

            if "tool_calls" in delta and isinstance(delta["tool_calls"], list):
                for tc in delta["tool_calls"]:
                    if not isinstance(tc, dict):
                        continue
                    raw_idx = tc.get("index")
                    idx = 0 if raw_idx is None else int(raw_idx)
                    if idx not in tool_calls:
                        tool_calls[idx] = {
                            "index": idx,
                            "id": tc.get("id") or f"call_{idx}",
                            "type": tc.get("type", "function"),
                            "function": {
                                "name": tc.get("function", {}).get("name", ""),
                                "arguments": tc.get("function", {}).get(
                                    "arguments", ""
                                ),
                            },
                        }
                    else:
                        if "id" in tc and tc["id"]:
                            tool_calls[idx]["id"] = tc["id"]
                        if "type" in tc and tc["type"]:
                            tool_calls[idx]["type"] = tc["type"]
                        if "function" in tc and isinstance(tc["function"], dict):
                            fn = tc["function"]
                            if "name" in fn and fn["name"]:
                                tool_calls[idx]["function"]["name"] = (
                                    tool_calls[idx]["function"]["name"] or ""
                                ) + fn["name"]
                            if "arguments" in fn and fn["arguments"]:
                                tool_calls[idx]["function"]["arguments"] = (
                                    tool_calls[idx]["function"]["arguments"] or ""
                                ) + fn["arguments"]

            if choices[0].get("finish_reason"):
                finish_reason = choices[0]["finish_reason"]

        message: dict[str, Any] = {"role": "assistant"}
        if full_content:
            message["content"] = full_content

        if tool_calls:
            message["tool_calls"] = [tool_calls[k] for k in sorted(tool_calls.keys())]

        return {"choices": [{"message": message, "finish_reason": finish_reason}]}

    def _extract_text(self, payload: dict[str, Any]) -> str:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise InvalidResponseError(
                f"LLM response did not include choices. Payload: {payload}"
            )

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise InvalidResponseError("LLM response choice payload was invalid.")

        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise InvalidResponseError("LLM response message payload was invalid.")

        content = message.get("content")
        if not isinstance(content, str):
            raise InvalidResponseError("LLM response content was invalid.")

        normalized_content = content.strip()
        if not normalized_content:
            raise InvalidResponseError("LLM response content was empty.")
        return normalized_content

    def _extract_response(self, payload: dict[str, Any]) -> LLMResponse:
        """Extract LLMResponse from API payload.

        Handles both regular content and tool calls.
        """
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise InvalidResponseError("LLM response did not include choices.")

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise InvalidResponseError("LLM response choice payload was invalid.")

        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise InvalidResponseError("LLM response message payload was invalid.")

        finish_reason = first_choice.get("finish_reason", "stop")

        # Check for tool calls
        tool_calls_raw = message.get("tool_calls")
        if tool_calls_raw:
            # Parse tool calls
            tool_calls = []
            for tc in tool_calls_raw:
                if not isinstance(tc, dict):
                    continue

                function = tc.get("function", {})
                if not isinstance(function, dict):
                    continue

                name = function.get("name")
                arguments_str = function.get("arguments", "{}")

                if isinstance(arguments_str, dict):
                    arguments = arguments_str
                else:
                    try:
                        arguments = json.loads(arguments_str)
                    except (JSONDecodeError, TypeError):
                        try:
                            repaired = repair_json(str(arguments_str))
                            arguments = repaired if isinstance(repaired, dict) else {}
                        except Exception:
                            arguments = {}

                tool_calls.append(
                    {
                        "id": tc.get("id", "call_1"),
                        "name": name,
                        "arguments": arguments,
                    }
                )

            return LLMResponse(
                content=None,
                tool_calls=tool_calls,
                finish_reason=finish_reason,
            )

        # Regular content response
        content = message.get("content")
        if content is None:
            raise InvalidResponseError("LLM response had no content or tool calls.")

        if not isinstance(content, str):
            raise InvalidResponseError("LLM response content was invalid.")

        return LLMResponse(
            content=content.strip() or None,
            tool_calls=None,
            finish_reason=finish_reason,
        )

    @staticmethod
    def _require_non_empty(value: str | None, *, field_name: str) -> str:
        if value is None:
            raise ConfigurationError(f"OpenAIProvider requires {field_name}.")
        normalized_value = value.strip()
        if not normalized_value:
            raise ConfigurationError(
                f"OpenAIProvider requires a non-empty {field_name}."
            )
        return normalized_value

    @staticmethod
    def _normalize_base_url(base_url: str | None) -> str:
        normalized_base_url = OpenAIProvider._require_non_empty(
            base_url,
            field_name="base_url",
        ).rstrip("/")
        parsed_url = urlparse(normalized_base_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ConfigurationError("OpenAIProvider base_url must be a valid URL.")
        return normalized_base_url

    @staticmethod
    def _validate_timeout(timeout: float) -> float:
        if timeout <= 0:
            raise ConfigurationError(
                "OpenAIProvider timeout must be greater than zero."
            )
        return timeout


def _get_logger(name: str) -> logging.Logger:
    """Return Friday's configured logger when available, otherwise a safe fallback."""
    try:
        return LoggerFactory().get_logger(name)
    except RuntimeError:
        return logging.getLogger(f"{APP_NAME}.{name}")
