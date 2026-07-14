"""Base classes and interfaces for Friday tools."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolResult:
    """Result of tool execution.

    Attributes:
        success: Whether the tool executed successfully.
        output: Tool output (file content, command result, etc.).
        error: Error message if execution failed.
    """

    success: bool
    output: str | None = None
    error: str | None = None


class BaseTool(ABC):
    """Base class for all Friday tools.

    Tools are actions that Friday can perform:
    - Read/write files
    - Execute commands
    - Search content
    - Interact with APIs

    Each tool must implement execute() and provide metadata.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the tool name (used in LLM function calling)."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Return a description of what the tool does."""
        ...

    @property
    @abstractmethod
    def parameters_schema(self) -> dict[str, Any]:
        """Return JSON schema for tool parameters.

        Used by LLM function calling to know what parameters to pass.

        Example:
            {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"}
                },
                "required": ["path"]
            }
        """
        ...

    @abstractmethod
    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with given parameters.

        Args:
            **kwargs: Tool-specific parameters.

        Returns:
            ToolResult with success status, output, and optional error.
        """
        ...

    def to_openai_schema(self) -> dict[str, Any]:
        """Convert tool to OpenAI function calling schema.

        Returns:
            Dictionary compatible with OpenAI function calling format.
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }

    def to_function_schema(self) -> dict[str, Any]:
        """Convert tool to function calling schema (legacy alias).

        Returns:
            Dictionary compatible with OpenAI function calling format.
        """
        schema = self.to_openai_schema()
        function_part = schema.get("function")
        if not isinstance(function_part, dict):
            raise ValueError("Invalid OpenAI schema format")
        return function_part
