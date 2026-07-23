"""Tests for the plugin subsystem and MCP integration."""

from unittest.mock import MagicMock, patch

from src.core.tool_registry import ToolRegistry
from src.plugins.base import BasePluginManager
from src.plugins.proxy import PluginToolProxy


class DummyPluginManager(BasePluginManager):
    """Dummy plugin manager for testing proxy and registry."""

    def discover_tools(self) -> list[dict[str, object]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "dummy_tool",
                    "description": "A dummy tool",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]

    def call_tool(self, name: str, arguments: dict[str, object]) -> str:
        if name == "dummy_tool":
            return "dummy result"
        raise ValueError("Unknown tool")


def test_plugin_tool_proxy_execution() -> None:
    """Test that PluginToolProxy correctly forwards calls to the manager."""
    manager = DummyPluginManager()
    schema = manager.discover_tools()[0]

    proxy = PluginToolProxy(manager, schema)

    assert proxy.name == "dummy_tool"
    assert proxy.description == "A dummy tool"

    result = proxy.execute()
    assert result.success is True
    assert result.output == "dummy result"


def test_tool_registry_register_plugin() -> None:
    """Test that ToolRegistry correctly registers tools from a plugin manager."""
    registry = ToolRegistry()
    manager = DummyPluginManager()

    registry.register_plugin(manager)

    assert "dummy_tool" in registry
    assert len(registry) == 1

    result = registry.execute("dummy_tool")
    assert result.success is True
    assert result.output == "dummy result"


# Note: Testing MCPClientManager directly requires mocking complex async
# context managers or running a real MCP server. For now, we mock the
# behavior of discover_tools and call_tool.
@patch("src.plugins.mcp_client.asyncio")
@patch("src.plugins.mcp_client.threading")
def test_mcp_client_manager_initialization(
    mock_threading: MagicMock, mock_asyncio: MagicMock
) -> None:
    """Test that MCPClientManager starts the background thread."""
    from src.plugins.mcp_client import MCPClientManager

    mock_event = MagicMock()
    mock_event.wait.return_value = True
    mock_threading.Event.return_value = mock_event

    manager = MCPClientManager("dummy_cmd", ["arg"])

    assert manager.command == "dummy_cmd"
    assert manager.args == ["arg"]
    mock_threading.Thread.assert_called_once()
    mock_event.wait.assert_called_once_with(timeout=10.0)
