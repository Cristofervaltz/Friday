"""Tool registry for managing and executing tools."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.tools.base import BaseTool, ToolResult


class ToolRegistry:
    """Registry for managing available tools.

    Provides centralized tool registration, schema generation,
    and execution for the agent system.
    """

    def __init__(self) -> None:
        """Initialize an empty tool registry."""
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool in the registry.

        Args:
            tool: Tool instance to register.

        Raises:
            ValueError: If a tool with the same name is already registered.
        """
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        """Unregister a tool from the registry.

        Args:
            name: Name of the tool to unregister.

        Raises:
            KeyError: If the tool is not registered.
        """
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' is not registered")
        del self._tools[name]

    def get_tool(self, name: str) -> BaseTool:
        """Get a tool by name.

        Args:
            name: Name of the tool to retrieve.

        Returns:
            The requested tool instance.

        Raises:
            KeyError: If the tool is not registered.
        """
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' is not registered")
        return self._tools[name]

    def list_tools(self) -> list[str]:
        """List all registered tool names.

        Returns:
            List of registered tool names.
        """
        return list(self._tools.keys())

    def get_tools_schema(self) -> list[dict[str, object]]:
        """Generate OpenAI function calling schema for all tools.

        Returns:
            List of tool schemas in OpenAI format.
        """
        return [tool.to_openai_schema() for tool in self._tools.values()]

    def execute(self, name: str, **kwargs: object) -> ToolResult:
        """Execute a tool by name with the given arguments.

        Args:
            name: Name of the tool to execute.
            **kwargs: Arguments to pass to the tool.

        Returns:
            Result of the tool execution.

        Raises:
            KeyError: If the tool is not registered.
        """
        tool = self.get_tool(name)
        return tool.execute(**kwargs)

    def __len__(self) -> int:
        """Return the number of registered tools."""
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools
