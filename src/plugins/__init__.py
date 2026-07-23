"""Plugin subsystem for Friday, providing MCP standard support."""

from .base import BasePluginManager
from .mcp_client import MCPClientManager
from .proxy import PluginToolProxy

__all__ = ["BasePluginManager", "MCPClientManager", "PluginToolProxy"]
