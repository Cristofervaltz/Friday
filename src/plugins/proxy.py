"""Proxy tool for MCP integration."""

from typing import Any

from src.plugins.base import BasePluginManager
from src.tools.base import BaseTool, ToolResult


class PluginToolProxy(BaseTool):
    """A proxy tool that forwards execution to a plugin manager."""

    def __init__(self, manager: BasePluginManager, schema: dict[str, Any]) -> None:
        """Initialize the proxy tool.

        Args:
            manager: The plugin manager responsible for this tool.
            schema: The OpenAI function schema for this tool.
        """
        self.manager = manager
        self._schema = schema

        func_schema = schema.get("function", {})
        if not isinstance(func_schema, dict):
            func_schema = {}

        self._name: str = str(func_schema.get("name", "unknown_tool"))
        self._description: str = str(func_schema.get("description", ""))

        params = func_schema.get("parameters", {})
        self._parameters_schema: dict[str, Any] = (
            params if isinstance(params, dict) else {}
        )

    @property
    def name(self) -> str:
        """Return the tool name."""
        return self._name

    @property
    def description(self) -> str:
        """Return the tool description."""
        return self._description

    @property
    def parameters_schema(self) -> dict[str, Any]:
        """Return the tool parameters schema."""
        return self._parameters_schema

    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool via the plugin manager."""
        try:
            result = self.manager.call_tool(self.name, kwargs)
            return ToolResult(success=True, output=result)
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))

    def to_openai_schema(self) -> dict[str, Any]:
        """Return the pre-computed schema."""
        return self._schema
