"""Base interfaces for Friday's Plugin subsystem."""

from abc import ABC, abstractmethod
from typing import Any


class BasePluginManager(ABC):
    """Abstract interface for managing dynamic plugins and external tools."""

    @abstractmethod
    def discover_tools(self) -> list[dict[str, Any]]:
        """Discover tools provided by the plugin.

        Returns:
            A list of tool schemas (OpenAI format) that can be registered.
        """
        pass

    @abstractmethod
    def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Call a specific tool by name.

        Args:
            name: The name of the tool to execute.
            arguments: The arguments to pass to the tool.

        Returns:
            The execution result as a string.
        """
        pass
