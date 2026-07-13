"""Ollama-compatible LLM provider implementation for Friday."""

from __future__ import annotations

import json
import logging
from json import JSONDecodeError
from time import perf_counter
from typing import Any, Self
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from src.config import LLMConfig
from src.constants import APP_NAME
from src.logger import LoggerFactory

from .base import BaseLLMProvider
from .exceptions import (
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
    This provider is also compatible with LM Studio when configured
    with the appropriate base URL.
    """

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        config: LLMConfig | None = None,
    ) -> None:
        """Create a new Ollama provider.

        Args:
            model: Model identifier (e.g., "llama2", "mistral").
            base_url: Ollama API base URL (defaults to localhost:11434).
            timeout: Request timeout in seconds.
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
        self._base_url = (
            base_url
            if base_url is not None
            else (
                resolved_config.base_url
                if resolved_config.base_url
                else _DEFAULT_OLLAMA_BASE_URL
            )
        ).rstrip("/")
        self._timeout = (
            timeout if timeout is not None else resolved_config.timeout or 30.0
        )
        self._logger = _get_logger("llm.ollama_provider")

        self._logger.info(
            "Initialized OllamaProvider model=%s base_url=%s timeout=%s",
            self._model,
            self._base_url,
            self._timeout,
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

    def is_available(self) -> bool:
        """Return whether the provider is configured and ready to use."""
        return bool(self._model and self._base_url and self._timeout > 0)

    def model_name(self) -> str:
        """Return the configured model name."""
        return self._model

    def _send_request(self, prompt: str) -> dict[str, Any]:
        request = self._build_request(prompt)

        try:
            with urlopen(request, timeout=self._timeout) as response:
                raw_response = response.read().decode("utf-8")
        except HTTPError as exc:
            raise ConnectionError(
                f"Ollama request failed with status code {exc.code}."
            ) from None
        except TimeoutError:
            raise
        except URLError as exc:
            if "timed out" in str(exc.reason).lower():
                raise TimeoutError("Ollama request timed out.") from None
            raise ConnectionError(f"Ollama connection failed: {exc.reason}") from None
        except OSError as exc:
            raise ConnectionError(f"Ollama connection failed: {exc}") from None

        return self._parse_payload(raw_response)

    def _build_request(self, prompt: str) -> Request:
        # Ollama uses /api/generate endpoint
        payload = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
        }
        request_body = json.dumps(payload).encode("utf-8")
        request_headers = {
            "Content-Type": "application/json",
        }
        return Request(
            url=f"{self._base_url}/api/generate",
            data=request_body,
            headers=request_headers,
            method="POST",
        )

    def _parse_payload(self, raw_response: str) -> dict[str, Any]:
        if not raw_response.strip():
            raise InvalidResponseError("Ollama response body was empty.")

        try:
            payload = json.loads(raw_response)
        except JSONDecodeError as exc:
            raise InvalidResponseError("Ollama response was not valid JSON.") from exc

        if not isinstance(payload, dict) or not payload:
            raise InvalidResponseError("Ollama response payload was invalid.")
        return payload

    def _extract_text(self, payload: dict[str, Any]) -> str:
        # Ollama returns {"response": "text", "done": true}
        response_text = payload.get("response")
        if not isinstance(response_text, str):
            raise InvalidResponseError("Ollama response did not include valid text.")

        normalized_content = response_text.strip()
        if not normalized_content:
            raise InvalidResponseError("Ollama response content was empty.")
        return normalized_content

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
