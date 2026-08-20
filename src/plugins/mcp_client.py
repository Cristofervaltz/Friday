"""MCP (Model Context Protocol) Client Manager."""

import asyncio
import logging
import threading
from typing import Any

from .base import BasePluginManager

try:
    from mcp.client.session import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    _MCP_AVAILABLE = True
except ImportError:
    _MCP_AVAILABLE = False

logger = logging.getLogger("friday.plugins.mcp")


class MCPClientManager(BasePluginManager):
    """Synchronous wrapper around an asynchronous MCP Stdio client."""

    def __init__(self, command: str, args: list[str]) -> None:
        """Initialize the MCP client manager.

        Args:
            command: The executable command (e.g., 'npx', 'python', 'docker').
            args: Arguments for the command.
        """
        if not _MCP_AVAILABLE:
            raise RuntimeError("mcp package is not installed.")

        self.command = command
        self.args = args
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)

        self._session: ClientSession | None = None
        self._ready_event = threading.Event()
        self._error: Exception | None = None

        self._thread.start()

        # Wait for initialization
        if not self._ready_event.wait(timeout=10.0):
            raise TimeoutError("MCP Server failed to initialize within 10 seconds.")
        if self._error:
            raise RuntimeError(f"MCP Server failed to start: {self._error}")

    def _run_loop(self) -> None:
        """Run the async event loop in a background thread."""
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._async_lifecycle())
        except Exception as exc:
            logger.debug("MCP lifecycle ended: %s", exc)
        finally:
            try:
                pending = asyncio.all_tasks(self._loop)
                for task in pending:
                    task.cancel()
                if pending:
                    self._loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
                self._loop.run_until_complete(self._loop.shutdown_asyncgens())
            except Exception:
                pass
            finally:
                if not self._loop.is_closed():
                    self._loop.close()

    async def _async_lifecycle(self) -> None:
        """Manage the asynchronous lifecycle of the MCP connection."""
        server_params = StdioServerParameters(command=self.command, args=self.args)

        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    self._session = session
                    self._ready_event.set()

                    # Keep the connection alive until loop stops
                    while self._loop.is_running():
                        await asyncio.sleep(0.1)
        except Exception as exc:
            self._error = exc
            self._ready_event.set()

    def discover_tools(self) -> list[dict[str, Any]]:
        """Discover tools exposed by the MCP server."""
        if not self._session:
            raise RuntimeError("MCP Session is not initialized.")

        future = asyncio.run_coroutine_threadsafe(
            self._session.list_tools(), self._loop
        )
        try:
            result = future.result(timeout=5.0)
        except Exception as exc:
            logger.exception("Failed to list tools.")
            raise RuntimeError(f"Failed to list tools: {exc}") from exc

        tools = []
        for tool in result.tools:
            # Convert MCP Tool to OpenAI schema
            schema = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": getattr(
                        tool, "input_schema", getattr(tool, "inputSchema", {})
                    ),
                },
            }
            tools.append(schema)

        return tools

    def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Call a specific tool on the MCP server."""
        if not self._session:
            raise RuntimeError("MCP Session is not initialized.")

        future = asyncio.run_coroutine_threadsafe(
            self._session.call_tool(name, arguments=arguments), self._loop
        )
        try:
            result = future.result(timeout=30.0)
        except Exception as exc:
            logger.exception("Failed to call tool.")
            raise RuntimeError(f"Failed to call tool: {exc}") from exc

        if getattr(result, "is_error", getattr(result, "isError", False)):
            return f"Error: {result.content}"

        # Extract text content
        output = []
        for content in result.content:
            if content.type == "text":
                output.append(content.text)

        return "\n".join(output)

    def shutdown(self, timeout: float = 2.0) -> None:
        """Shutdown the background event loop and MCP child process."""
        try:
            if hasattr(self, "_loop") and self._loop.is_running():
                self._loop.call_soon_threadsafe(self._loop.stop)
        except Exception:
            pass
        try:
            if hasattr(self, "_thread") and self._thread.is_alive():
                self._thread.join(timeout=timeout)
        except Exception:
            pass
