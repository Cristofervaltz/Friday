"""Dedicated exception hierarchy for Friday LLM providers."""

from __future__ import annotations


class LLMError(Exception):
    """Base exception for LLM provider failures."""


class ConfigurationError(LLMError):
    """Raised when provider configuration is missing or invalid."""


class AuthenticationError(LLMError):
    """Raised when the upstream provider rejects authentication."""


class ConnectionError(LLMError):
    """Raised when the provider cannot be reached successfully."""


class TimeoutError(LLMError):
    """Raised when a provider request exceeds the configured timeout."""


class InvalidResponseError(LLMError):
    """Raised when the provider returns an unexpected or unusable payload."""
