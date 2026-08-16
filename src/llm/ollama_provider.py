"""Ollama-compatible LLM provider implementation for Friday."""

from __future__ import annotations

import builtins
import json
import logging
import time
from json import JSONDecodeError
from time import perf_counter
from typing import Any, Self
from urllib.error import HTTPError, URLError
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

_DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
_DEFAULT_OLLAMA_MODEL = "llama2"


class OllamaProvider(BaseLLMProvider):
    """Provider for Ollama local LLM endpoints.

    Ollama provides local LLM hosting with a simple HTTP API.
    Supports native tool calling via the /api/chat endpoint for compatible
    models (e.g. Llama 3.1, Mistral, Qwen, etc.).
    """

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        retry_delay: float | None = None,
        options: dict[str, Any] | None = None,
        config: LLMConfig | None = None,
    ) -> None:
        """Create a new Ollama provider.

        Args:
            model: Model identifier (e.g., "llama3.1", "mistral").
            base_url: Ollama API base URL (defaults to http://localhost:11434).
            timeout: Request timeout in seconds.
            max_retries: Maximum number of retry attempts.
            retry_delay: Delay in seconds between retries.
            options: Optional model options (e.g. temperature, num_predict).
            config: Optional Friday LLMConfig to load settings from.

        Note:
            Ollama does not require an API key for local instances.
        """
        resolved_config = config or LLMConfig()
        self._model = self._require_non_empty(
            model if model is not None else resolved_config.model,
            field_name="model",
            default=_DEFAULT_OLLAMA_MODEL,
        )
        base_url_val = base_url if base_url is not None else resolved_config.base_url
        self._base_url = (
            base_url_val.strip().rstrip("/")
            if base_url_val and base_url_val.strip()
            else _DEFAULT_OLLAMA_BASE_URL
        )
        raw_timeout = (
            timeout if timeout is not None else resolved_config.timeout or 30.0
        )
        self._timeout = self._validate_timeout(raw_timeout)
        self._max_retries = max(
            0,
            (
                max_retries
                if max_retries is not None
                else getattr(resolved_config, "max_retries", 3)
            ),
        )
        self._retry_delay = max(
            0.0,
            (
                retry_delay
                if retry_delay is not None
                else getattr(resolved_config, "retry_delay", 0.5)
            ),
        )
        resolved_options = (
            options
            if options is not None
            else getattr(resolved_config, "options", None)
        )
        self._options: dict[str, Any] | None = (
            dict(resolved_options)
            if isinstance(resolved_options, dict) and resolved_options
            else None
        )
        self._logger = _get_logger("llm.ollama_provider")

        self._logger.info(
            "Initialized OllamaProvider model=%s base_url=%s timeout=%s retries=%s options=%s",
            self._model,
            self._base_url,
            self._timeout,
            self._max_retries,
            self._options,
        )

    @classmethod
    def from_config(cls, config: LLMConfig) -> Self:
        """Construct a provider directly from Friday's configuration model."""
        return cls(config=config)

    def generate(self, prompt: str) -> str:
        """Generate a single response using the Ollama API."""
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
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """Generate response with function calling support using Ollama /api/chat.

        Args:
            messages: Conversation history in OpenAI/Friday format.
            tools: Available tools in OpenAI function calling format.

        Returns:
            LLMResponse with content or tool calls.
        """
        started_at = perf_counter()
        normalized_messages = messages or []
        normalized_tools = tools or []

        self._logger.info(
            "LLM request with tools started model=%s tools_count=%d messages_count=%d",
            self._model,
            len(normalized_tools),
            len(normalized_messages),
        )

        try:
            payload = self._send_chat_request(normalized_messages, normalized_tools)
            response = self._extract_chat_response(payload)
        except (AuthenticationError, TimeoutError):
            duration_ms = (perf_counter() - started_at) * 1000
            self._logger.exception(
                "LLM request with tools failed with network/auth error model=%s duration_ms=%.2f",
                self._model,
                duration_ms,
            )
            raise
        except ConnectionError as exc:
            # Fast fail on network connection/socket failures (e.g. refused connection)
            if "connection failed" in str(exc).lower():
                duration_ms = (perf_counter() - started_at) * 1000
                self._logger.exception(
                    "LLM request with tools failed with connection error model=%s duration_ms=%.2f",
                    self._model,
                    duration_ms,
                )
                raise

            response = self._fallback_generate(normalized_messages, started_at, exc)
        except LLMError as exc:
            response = self._fallback_generate(normalized_messages, started_at, exc)
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

    def _fallback_generate(
        self,
        messages: list[dict[str, Any]] | None,
        started_at: float,
        exc: Exception,
    ) -> LLMResponse:
        """Fallback to text generation when chat tool calling fails."""
        self._logger.warning(
            f"LLM request with tools failed ({exc}). "
            "Retrying with fallback text generation."
        )
        prompt_parts = []
        for m in messages or []:
            if not isinstance(m, dict):
                continue
            role = m.get("role", "user")
            content = m.get("content")
            if content is not None:
                if isinstance(content, (dict, list)):
                    prompt_parts.append(
                        f"{role}: {json.dumps(content, ensure_ascii=False)}"
                    )
                else:
                    prompt_parts.append(f"{role}: {content}")
        prompt = "\n".join(prompt_parts) if prompt_parts else "Please proceed."
        try:
            fallback_payload = self._send_request(prompt)
            fallback_text = self._extract_text(fallback_payload)
            return LLMResponse(content=fallback_text)
        except LLMError:
            duration_ms = (perf_counter() - started_at) * 1000
            self._logger.exception(
                "LLM fallback request failed model=%s duration_ms=%.2f",
                self._model,
                duration_ms,
            )
            raise

    def is_available(self) -> bool:
        """Return whether the provider is configured and ready to use."""
        return bool(self._model and self._base_url and self._timeout > 0)

    def model_name(self) -> str:
        """Return the configured model name."""
        return self._model

    def _send_http_with_retry(self, request: Request) -> str:
        """Send HTTP request to Ollama endpoint with retry support."""
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
                        f"Ollama authentication failed: {error_body}"
                    ) from None

                # Non-retryable 4xx client errors (e.g., 404 model not found, 400 bad request)
                if 400 <= exc.code < 500 and exc.code != 429:
                    raise ConnectionError(
                        f"Ollama request failed with status code {exc.code}. Body: {error_body}"
                    ) from None

                last_exception = ConnectionError(
                    f"Ollama request failed with status code {exc.code}. Body: {error_body}"
                )
                if attempt < max_attempts:
                    self._logger.warning(
                        "Ollama HTTP error %d (attempt %d/%d). Retrying in %.2fs...",
                        exc.code,
                        attempt,
                        max_attempts,
                        self._retry_delay,
                    )
                    time.sleep(self._retry_delay)
                else:
                    raise last_exception from None

            except builtins.TimeoutError:
                last_exception = TimeoutError("Ollama request timed out.")
                if attempt < max_attempts:
                    self._logger.warning(
                        "Ollama request timed out (attempt %d/%d). Retrying in %.2fs...",
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
                        "Ollama request timed out (attempt %d/%d). Retrying in %.2fs...",
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
                    last_exception = TimeoutError("Ollama request timed out.")
                else:
                    last_exception = ConnectionError(
                        f"Ollama connection failed: {exc.reason}"
                    )

                if attempt < max_attempts:
                    self._logger.warning(
                        "Ollama connection error: %s (attempt %d/%d). Retrying in %.2fs...",
                        exc.reason,
                        attempt,
                        max_attempts,
                        self._retry_delay,
                    )
                    time.sleep(self._retry_delay)
                else:
                    raise last_exception from None

            except OSError as exc:
                last_exception = ConnectionError(f"Ollama connection failed: {exc}")
                if attempt < max_attempts:
                    self._logger.warning(
                        "Ollama socket error: %s (attempt %d/%d). Retrying in %.2fs...",
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
        raise ConnectionError("Ollama request failed after retries.")

    def _send_request(self, prompt: str) -> dict[str, Any]:
        """Send a single generation request to /api/generate."""
        request = self._build_request(prompt)
        raw_response = self._send_http_with_retry(request)
        return self._parse_payload(raw_response)

    def _build_request(self, prompt: str) -> Request:
        """Build HTTP Request object for /api/generate."""
        payload: dict[str, Any] = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
        }
        if self._options:
            payload["options"] = self._options

        request_body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request_headers = {
            "Content-Type": "application/json",
        }
        return Request(
            url=f"{self._base_url}/api/generate",
            data=request_body,
            headers=request_headers,
            method="POST",
        )

    def _send_chat_request(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Send chat completion request with tools to /api/chat."""
        request = self._build_chat_request(messages, tools)
        raw_response = self._send_http_with_retry(request)
        return self._parse_payload(raw_response)

    def _build_chat_request(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> Request:
        """Build HTTP Request object for /api/chat with tool calling support."""
        formatted_messages = self._format_messages(messages)
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": formatted_messages,
            "stream": False,
        }
        if self._options:
            payload["options"] = self._options
        if tools:
            formatted_tools = self._format_tools(tools)
            if formatted_tools:
                payload["tools"] = formatted_tools

        request_body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request_headers = {
            "Content-Type": "application/json",
        }
        return Request(
            url=f"{self._base_url}/api/chat",
            data=request_body,
            headers=request_headers,
            method="POST",
        )

    def _format_tools(self, tools: list[Any] | None) -> list[dict[str, Any]]:
        """Format Friday/OpenAI tools schema into Ollama /api/chat tool schema."""
        if not tools:
            return []
        formatted: list[dict[str, Any]] = []
        for tool in tools:
            if hasattr(tool, "to_openai_schema"):
                tool_dict = tool.to_openai_schema()
            elif isinstance(tool, dict):
                tool_dict = tool
            else:
                continue

            if not isinstance(tool_dict, dict):
                continue

            name = ""
            description = ""
            raw_params = None

            if tool_dict.get("type") == "function" and isinstance(
                tool_dict.get("function"), dict
            ):
                func = tool_dict["function"]
                name = str(func.get("name") or "").strip()
                description = str(func.get("description") or "")
                raw_params = func.get("parameters")
            elif "function" in tool_dict and isinstance(tool_dict["function"], dict):
                func = tool_dict["function"]
                name = str(func.get("name") or "").strip()
                description = str(func.get("description") or "")
                raw_params = func.get("parameters")
            elif "name" in tool_dict:
                name = str(tool_dict.get("name") or "").strip()
                description = str(tool_dict.get("description") or "")
                raw_params = tool_dict.get("parameters") or tool_dict.get(
                    "parameters_schema"
                )

            if not name:
                continue

            parameters: dict[str, Any] = (
                dict(raw_params)
                if isinstance(raw_params, dict)
                else {"type": "object", "properties": {}}
            )

            if "type" not in parameters or not isinstance(parameters.get("type"), str):
                parameters["type"] = "object"

            if not isinstance(parameters.get("properties"), dict):
                parameters["properties"] = {}

            if "required" in parameters and not isinstance(
                parameters["required"], list
            ):
                parameters.pop("required", None)

            formatted.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": description,
                        "parameters": parameters,
                    },
                }
            )
        return formatted

    def _format_messages(
        self, messages: list[dict[str, Any]] | None
    ) -> list[dict[str, Any]]:
        """Format conversation messages for Ollama /api/chat endpoint."""
        if not messages:
            return []
        formatted_messages: list[dict[str, Any]] = []
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            raw_role = msg.get("role", "user")
            role = "tool" if raw_role == "function" else str(raw_role)
            content = msg.get("content")
            if isinstance(content, (dict, list)):
                formatted_content = json.dumps(content, ensure_ascii=False)
            elif content is not None:
                formatted_content = str(content)
            else:
                formatted_content = ""

            formatted_msg: dict[str, Any] = {
                "role": role,
                "content": formatted_content,
            }

            images = msg.get("images")
            if isinstance(images, list):
                formatted_msg["images"] = images

            # Check for tool_calls in assistant messages
            tool_calls_raw = msg.get("tool_calls")
            if tool_calls_raw and isinstance(tool_calls_raw, list):
                ollama_tool_calls: list[dict[str, Any]] = []
                for tc in tool_calls_raw:
                    if not isinstance(tc, dict):
                        continue
                    func = tc.get("function")
                    if isinstance(func, dict):
                        name = func.get("name")
                        raw_args = func.get("arguments", {})
                    else:
                        name = tc.get("name")
                        raw_args = tc.get("arguments", {})

                    if not name or not isinstance(name, str):
                        continue
                    name = name.strip()
                    if not name:
                        continue

                    if isinstance(raw_args, dict):
                        args = raw_args
                    elif isinstance(raw_args, str):
                        try:
                            parsed = json.loads(raw_args)
                            args = parsed if isinstance(parsed, dict) else {}
                        except (JSONDecodeError, TypeError):
                            try:
                                repaired = repair_json(raw_args)
                                args = repaired if isinstance(repaired, dict) else {}
                            except Exception:
                                args = {}
                    else:
                        args = {}

                    ollama_tool_calls.append(
                        {
                            "function": {
                                "name": name,
                                "arguments": args,
                            }
                        }
                    )
                if ollama_tool_calls:
                    formatted_msg["tool_calls"] = ollama_tool_calls

            formatted_messages.append(formatted_msg)
        return formatted_messages

    def _extract_chat_response(self, payload: dict[str, Any]) -> LLMResponse:
        """Extract LLMResponse from Ollama /api/chat response payload.

        Handles both standard message content and native tool calls.
        """
        message = payload.get("message")
        if not isinstance(message, dict):
            raise InvalidResponseError(
                "Ollama chat response message payload was invalid."
            )

        done_reason = str(payload.get("done_reason") or "stop")
        tool_calls_raw = message.get("tool_calls")

        if tool_calls_raw and isinstance(tool_calls_raw, list):
            tool_calls: list[dict[str, Any]] = []
            for idx, tc in enumerate(tool_calls_raw):
                if not isinstance(tc, dict):
                    continue
                func = tc.get("function")
                if isinstance(func, dict):
                    name = func.get("name")
                    raw_args = func.get("arguments", {})
                else:
                    name = tc.get("name")
                    raw_args = tc.get("arguments", {})

                if not name or not isinstance(name, str):
                    continue
                name = name.strip()
                if not name:
                    continue

                if isinstance(raw_args, dict):
                    arguments = raw_args
                elif isinstance(raw_args, str):
                    try:
                        parsed = json.loads(raw_args)
                        arguments = parsed if isinstance(parsed, dict) else {}
                    except (JSONDecodeError, TypeError):
                        try:
                            repaired = repair_json(raw_args)
                            arguments = repaired if isinstance(repaired, dict) else {}
                        except Exception:
                            arguments = {}
                else:
                    arguments = {}

                call_id = str(tc.get("id") or f"call_{idx + 1}")
                tool_calls.append(
                    {
                        "id": call_id,
                        "name": name,
                        "arguments": arguments,
                    }
                )

            if tool_calls:
                return LLMResponse(
                    content=message.get("content") or None,
                    tool_calls=tool_calls,
                    finish_reason=(
                        "tool_calls" if done_reason == "stop" else done_reason
                    ),
                )

        content = message.get("content")
        if content is None:
            raise InvalidResponseError("Ollama response had no content or tool calls.")

        if not isinstance(content, str):
            raise InvalidResponseError("Ollama response content was invalid.")

        normalized_content = content.strip()
        if not normalized_content:
            raise InvalidResponseError("Ollama response had no content or tool calls.")

        return LLMResponse(
            content=normalized_content,
            tool_calls=None,
            finish_reason=done_reason,
        )

    def _parse_payload(self, raw_response: str) -> dict[str, Any]:
        """Parse raw JSON or NDJSON/SSE string response from Ollama API."""
        stripped = raw_response.strip()
        if not stripped:
            raise InvalidResponseError("Ollama response body was empty.")

        try:
            payload = json.loads(stripped)
            if isinstance(payload, dict) and payload:
                return payload
        except JSONDecodeError as exc:
            # Check for NDJSON / SSE stream responses
            if "\n" in stripped or stripped.startswith("data:"):
                try:
                    return self._parse_ndjson_or_sse(stripped)
                except Exception as sse_exc:
                    self._logger.debug("Failed parsing NDJSON/SSE stream: %s", sse_exc)

            # Local JSON repair attempt
            try:
                repaired = repair_json(stripped)
                if isinstance(repaired, dict) and repaired:
                    return repaired
            except Exception:
                pass

            raise InvalidResponseError("Ollama response was not valid JSON.") from exc

        if not isinstance(payload, dict) or not payload:
            raise InvalidResponseError("Ollama response payload was invalid.")
        return payload

    def _parse_ndjson_or_sse(self, raw_response: str) -> dict[str, Any]:
        """Parse multi-line NDJSON or SSE stream response into unified payload."""
        lines = [line.strip() for line in raw_response.splitlines() if line.strip()]
        if not lines:
            raise InvalidResponseError("Ollama response stream was empty.")

        chunks: list[dict[str, Any]] = []
        for line in lines:
            if line.startswith("data:"):
                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    break
            else:
                data_str = line

            try:
                chunk = json.loads(data_str)
                if isinstance(chunk, dict):
                    chunks.append(chunk)
            except JSONDecodeError:
                try:
                    repaired = repair_json(data_str)
                    if isinstance(repaired, dict):
                        chunks.append(repaired)
                except Exception:
                    continue

        if not chunks:
            raise InvalidResponseError(
                "Ollama response stream had no valid JSON chunks."
            )

        # Determine whether this is a chat response or generate response
        has_message = any("message" in c for c in chunks)
        has_response = any("response" in c for c in chunks)

        model = chunks[-1].get("model") or chunks[0].get("model") or self._model
        done_reason = "stop"
        for c in reversed(chunks):
            if c.get("done_reason"):
                done_reason = c["done_reason"]
                break

        if has_message:
            full_content_parts: list[str] = []
            tool_calls_list: list[dict[str, Any]] = []

            for c in chunks:
                msg = c.get("message")
                if isinstance(msg, dict):
                    content = msg.get("content")
                    if content:
                        full_content_parts.append(str(content))
                    tc = msg.get("tool_calls")
                    if tc and isinstance(tc, list):
                        tool_calls_list.extend(tc)

            return {
                "model": model,
                "message": {
                    "role": "assistant",
                    "content": "".join(full_content_parts),
                    "tool_calls": tool_calls_list if tool_calls_list else None,
                },
                "done_reason": done_reason,
                "done": True,
            }

        if has_response:
            full_response_parts: list[str] = []
            for c in chunks:
                resp = c.get("response")
                if resp:
                    full_response_parts.append(str(resp))

            return {
                "model": model,
                "response": "".join(full_response_parts),
                "done": True,
            }

        # Fallback to the last chunk if neither pattern was recognized
        return chunks[-1]

    def _extract_text(self, payload: dict[str, Any]) -> str:
        """Extract text from /api/generate response payload."""
        response_text = payload.get("response")
        if not isinstance(response_text, str):
            raise InvalidResponseError("Ollama response did not include valid text.")

        normalized_content = response_text.strip()
        if not normalized_content:
            raise InvalidResponseError("Ollama response content was empty.")
        return normalized_content

    @staticmethod
    def _validate_timeout(timeout: float) -> float:
        if timeout <= 0:
            raise ConfigurationError(
                "OllamaProvider timeout must be greater than zero."
            )
        return timeout

    @staticmethod
    def _require_non_empty(
        value: str | None, *, field_name: str, default: str | None = None
    ) -> str:
        if value is None:
            if default is not None:
                return default
            raise ConfigurationError(f"OllamaProvider requires {field_name}.")
        normalized_value = value.strip()
        if not normalized_value:
            if default is not None:
                return default
            raise ConfigurationError(
                f"OllamaProvider requires a non-empty {field_name}."
            )
        return normalized_value


def _get_logger(name: str) -> logging.Logger:
    """Return Friday's configured logger when available, otherwise a safe fallback."""
    try:
        return LoggerFactory().get_logger(name)
    except RuntimeError:
        return logging.getLogger(f"{APP_NAME}.{name}")
