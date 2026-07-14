"""OpenAI-compatible LLM provider implementation for Friday."""

from __future__ import annotations

import builtins
import json
import logging
from json import JSONDecodeError
from time import perf_counter
from typing import Any, Self
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from src.config import LLMConfig
from src.constants import APP_NAME
from src.logger import LoggerFactory

from .base import BaseLLMProvider
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
}


class OpenAIProvider(BaseLLMProvider):
    """Provider for OpenAI-compatible chat completion endpoints."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
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
        self._logger = _get_logger("llm.openai_provider")

        self._logger.info(
            "Initialized OpenAIProvider model=%s base_url=%s timeout=%s",
            self._model,
            self._base_url,
            self._timeout,
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

    def is_available(self) -> bool:
        """Return whether the provider has a valid configuration."""
        return all((self._api_key, self._model, self._base_url)) and self._timeout > 0

    def model_name(self) -> str:
        """Return the configured upstream model name."""
        return self._model

    def _send_request(self, prompt: str) -> dict[str, Any]:
        request = self._build_request(prompt)

        try:
            with urlopen(request, timeout=self._timeout) as response:
                raw_response = response.read().decode("utf-8")
        except HTTPError as exc:
            if exc.code in {401, 403}:
                raise AuthenticationError("LLM authentication failed.") from None
            raise ConnectionError(
                f"LLM request failed with status code {exc.code}."
            ) from None
        except builtins.TimeoutError:
            raise TimeoutError("LLM request timed out.") from None
        except TimeoutError:
            raise
        except URLError as exc:
            if isinstance(exc.reason, builtins.TimeoutError):
                raise TimeoutError("LLM request timed out.") from None
            raise ConnectionError(f"LLM connection failed: {exc.reason}") from None
        except OSError as exc:
            raise ConnectionError(f"LLM connection failed: {exc}") from None

        return self._parse_payload(raw_response)

    def _build_request(self, prompt: str) -> Request:
        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
        }
        request_body = json.dumps(payload).encode("utf-8")
        request_headers = {
            key: value.format(api_key=self._api_key)
            for key, value in _JSON_HEADERS.items()
        }
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
        except JSONDecodeError as exc:
            raise InvalidResponseError("LLM response was not valid JSON.") from exc

        if not isinstance(payload, dict) or not payload:
            raise InvalidResponseError("LLM response payload was invalid.")
        return payload

    def _extract_text(self, payload: dict[str, Any]) -> str:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise InvalidResponseError("LLM response did not include choices.")

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
