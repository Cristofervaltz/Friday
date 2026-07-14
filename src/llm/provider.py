"""Compatibility alias for the generic LLM provider interface."""

from .base import BaseLLMProvider

LLMProvider = BaseLLMProvider

__all__ = ["LLMProvider"]
