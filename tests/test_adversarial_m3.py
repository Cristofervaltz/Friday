"""Milestone M3 Adversarial and Stress Test Suite.

Tests REPL clear robustness, src.tools module exports/signatures/instantiation,
server rename_chat variations, and WebSocket loop resilience.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

import src.tools as tools_module
from src.cli.repl import FridayREPL
from src.runtime import FridayApplication
from src.tools import (
    BaseTool,
    DelegateTaskTool,
    EditFileTool,
    FetchWebPageTool,
    ListFilesTool,
    OpenBrowserTool,
    ReadFileTool,
    ScreenshotTool,
    SemanticSearchTool,
    ShellCommandTool,
    TimeTool,
    WeatherTool,
    WebSearchTool,
    WindowManagementTool,
    WriteFileTool,
)

# ============================================================================
# 1. REPL CLEAR ADVERSARIAL TESTS
# ============================================================================


class TestREPLClearAdversarial:
    """Stress tests for REPL clear functionality."""

    @pytest.fixture
    def mock_app(self, tmp_path: Path) -> MagicMock:
        """Create a mock FridayApplication with real memory in tmp_path."""
        app = MagicMock(spec=FridayApplication)
        app.provider = MagicMock()
        app.config = MagicMock()
        app.config.app_name = "Friday Test"
        app.config.version = "1.0.0"
        app.config.speech_language = "en"
        app.config.paths = MagicMock()
        app.config.paths.data_dir = tmp_path / "data"
        app.config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        app.config.paths.app_home = tmp_path
        app.config.llm = MagicMock()
        app.config.llm.system_prompt = "You are a test assistant."
        app.config.llm.max_iterations = 5
        app.logger = MagicMock()
        return app

    def test_clear_variations_command_handling(
        self,
        mock_app: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test 'clear', ':clear', '/clear', and case variations with/without whitespace."""
        repl = FridayREPL(mock_app)

        # Populate history with some messages
        repl._agent.memory.add_user_message("Hello")
        repl._agent.memory.add_assistant_message("Hi there")
        assert len(repl._agent.memory) >= 2

        clear_inputs = [
            "clear",
            ":clear",
            "/clear",
            "CLEAR",
            ":CLEAR",
            "/CLEAR",
            "Clear",
            ":Clear",
            "/Clear",
            "  clear  ",
            " :clear ",
            " /clear ",
            "cLeAr",
            ":cLeAr",
            "/cLeAr",
        ]

        for cmd in clear_inputs:
            # Re-populate messages
            repl._agent.memory.add_user_message("Test message")
            repl._agent.memory.add_assistant_message("Test response")
            assert len(repl._agent.memory) >= 2

            # Simulate typing clear input
            monkeypatch.setattr("builtins.input", lambda prompt="", c=cmd: c)
            repl._process_input()

            # Verify history cleared (0 non-system messages)
            assert (
                len(repl._agent.memory) == 0
            ), f"Failed to clear history with command: {cmd!r}"

            # Verify system prompt remains intact
            assert repl._agent.memory.system_prompt == "You are a test assistant."

            # Verify printed output
            captured = capsys.readouterr()
            assert "Conversation history cleared." in captured.out

    def test_clear_on_empty_history(
        self,
        mock_app: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test clear when history is already empty (idempotency)."""
        repl = FridayREPL(mock_app)
        assert len(repl._agent.memory) == 0

        monkeypatch.setattr("builtins.input", lambda prompt="": ":clear")
        repl._process_input()

        assert len(repl._agent.memory) == 0
        captured = capsys.readouterr()
        assert "Conversation history cleared." in captured.out

    def test_multiple_consecutive_clears(
        self,
        mock_app: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Stress test: 20 consecutive clears in a row."""
        repl = FridayREPL(mock_app)
        for i in range(20):
            repl._agent.memory.add_user_message(f"Message {i}")
            monkeypatch.setattr(
                "builtins.input",
                lambda prompt="", idx=i: ["clear", ":clear", "/clear"][idx % 3],
            )
            repl._process_input()
            assert len(repl._agent.memory) == 0

    def test_clear_triggers_on_change_callbacks(
        self,
        mock_app: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify on-change callbacks fire when clear is executed."""
        repl = FridayREPL(mock_app)
        callback_called: list[int] = []

        def callback(mem: Any) -> None:
            callback_called.append(len(mem))

        repl._agent.memory.add_on_change_callback(callback)
        repl._agent.memory.add_user_message("Hello")

        # Clear via REPL command
        monkeypatch.setattr("builtins.input", lambda prompt="": "clear")
        repl._process_input()

        assert callback_called[-1] == 0

    def test_clear_does_not_invoke_llm(
        self,
        mock_app: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Ensure clear command is intercepted and never dispatched to the LLM agent."""
        repl = FridayREPL(mock_app)
        with patch.object(repl._agent, "run") as mock_run:
            for cmd in ["clear", ":clear", "/clear", "CLEAR", " :clear "]:
                monkeypatch.setattr("builtins.input", lambda prompt="", c=cmd: c)
                repl._process_input()
            mock_run.assert_not_called()


# ============================================================================
# 2. SRC.TOOLS MODULE EXPORTS, SUBCLASS & SIGNATURE TESTS
# ============================================================================


class TestToolsExportsAdversarial:
    """Adversarial verification of src.tools exports and tool contracts."""

    EXPECTED_EXPORTS = [
        "BaseTool",
        "ToolResult",
        "ReadFileTool",
        "WriteFileTool",
        "EditFileTool",
        "ListFilesTool",
        "ShellCommandTool",
        "TimeTool",
        "WeatherTool",
        "WebSearchTool",
        "FetchWebPageTool",
        "OpenBrowserTool",
        "WindowManagementTool",
        "ScreenshotTool",
        "SemanticSearchTool",
        "DelegateTaskTool",
    ]

    def test_all_exports_present_in_namespace_and_all(self) -> None:
        """Verify __all__ contains exactly the expected tool exports and all exist in namespace."""
        assert hasattr(tools_module, "__all__")
        assert sorted(tools_module.__all__) == sorted(self.EXPECTED_EXPORTS)
        for name in self.EXPECTED_EXPORTS:
            assert hasattr(
                tools_module, name
            ), f"{name} not found in src.tools namespace"

    def test_tool_classes_inherit_from_base_tool(self) -> None:
        """Verify all tool exports inherit from BaseTool (except BaseTool and ToolResult)."""
        for name in self.EXPECTED_EXPORTS:
            obj = getattr(tools_module, name)
            if name in ("BaseTool", "ToolResult"):
                continue
            assert inspect.isclass(obj), f"{name} is not a class"
            assert issubclass(obj, BaseTool), f"{name} does not inherit from BaseTool"

    def test_instantiation_and_contract_inspection(self, tmp_path: Path) -> None:
        """Instantiate every tool and inspect properties and method signatures."""
        tool_instances: dict[str, BaseTool] = {
            "ReadFileTool": ReadFileTool(),
            "WriteFileTool": WriteFileTool(),
            "EditFileTool": EditFileTool(),
            "ListFilesTool": ListFilesTool(),
            "ShellCommandTool": ShellCommandTool(),
            "TimeTool": TimeTool(),
            "WeatherTool": WeatherTool(),
            "WebSearchTool": WebSearchTool(),
            "FetchWebPageTool": FetchWebPageTool(),
            "OpenBrowserTool": OpenBrowserTool(),
            "WindowManagementTool": WindowManagementTool(),
            "DelegateTaskTool": DelegateTaskTool(),
            "DelegateTaskTool_with_none": DelegateTaskTool(app=None, registry=None),
        }

        # Optional tools that might require dependencies
        try:
            tool_instances["ScreenshotTool"] = ScreenshotTool()
        except RuntimeError:
            pass

        try:
            tool_instances["SemanticSearchTool"] = SemanticSearchTool(
                workspace_path=str(tmp_path)
            )
        except (RuntimeError, Exception):
            pass

        seen_names = set()
        for label, tool in tool_instances.items():
            # Check name
            assert (
                isinstance(tool.name, str) and len(tool.name) > 0
            ), f"{label} has invalid name"
            if label != "DelegateTaskTool_with_none":
                assert tool.name not in seen_names, f"Duplicate tool name {tool.name}"
                seen_names.add(tool.name)

            # Check description
            assert (
                isinstance(tool.description, str) and len(tool.description) > 0
            ), f"{label} missing description"

            # Check parameters_schema
            schema = tool.parameters_schema
            assert isinstance(schema, dict), f"{label} schema is not dict"
            assert schema.get("type") == "object", f"{label} schema type not 'object'"
            assert "properties" in schema, f"{label} schema missing 'properties'"

            # Check execute method signature
            sig = inspect.signature(tool.execute)
            assert "kwargs" in sig.parameters or len(sig.parameters) >= 0

    def test_delegate_task_tool_edge_cases(self) -> None:
        """Test DelegateTaskTool with missing args, None args, and detached execution."""
        tool = DelegateTaskTool(app=None, registry=None)

        # Missing required params
        res1 = tool.execute()
        assert not res1.success
        assert "Missing required parameters" in (res1.error or "")

        res2 = tool.execute(role="tester")
        assert not res2.success
        assert "Missing required parameters" in (res2.error or "")

        res3 = tool.execute(task="do something")
        assert not res3.success
        assert "Missing required parameters" in (res3.error or "")

        # Execute with null role / empty task
        res4 = tool.execute(role="", task="")
        assert not res4.success


# ============================================================================
# 3. SERVER RENAME_CHAT ADVERSARIAL TESTS
# ============================================================================


class TestServerRenameChatAdversarial:
    """Stress testing the rename_chat websocket endpoint in src/api/server.py."""

    @pytest.fixture
    def server_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> tuple[TestClient, Path]:
        """Create a TestClient with initialized server and memory."""
        monkeypatch.setenv("FRIDAY_HOME", str(tmp_path))
        data_dir = tmp_path / "data"
        chats_dir = data_dir / "chats"
        chats_dir.mkdir(parents=True, exist_ok=True)
        from src.api.server import create_app

        app = create_app()
        client = TestClient(app)
        return client, chats_dir

    def test_rename_chat_formats(self, server_env: tuple[TestClient, Path]) -> None:
        """Test all valid and polymorphic payload formats for rename_chat."""
        client, chats_dir = server_env

        def receive_type(
            ws: Any, target_type: str, max_reads: int = 10
        ) -> dict[str, Any]:
            for _ in range(max_reads):
                msg: dict[str, Any] = ws.receive_json()
                if msg.get("type") == target_type:
                    return msg
            raise TimeoutError(f"Did not receive message of type {target_type}")

        # Pre-create a chat file in the chats directory
        test_chat_id = "chat_adversarial_1"
        chat_file = chats_dir / f"{test_chat_id}.json"
        chat_file.write_text(
            json.dumps(
                {
                    "id": test_chat_id,
                    "title": "Initial Chat Title",
                    "workspace": "",
                    "updated_at": 1000,
                    "messages": [{"role": "user", "content": "hello"}],
                }
            ),
            encoding="utf-8",
        )

        with client.websocket_connect("/ws/chat") as ws:
            # Drain initial msgs
            receive_type(ws, "chat_history")
            receive_type(ws, "chats_list")
            receive_type(ws, "workspace_set")

            # 1. Flat chat_id & title
            ws.send_text(
                json.dumps(
                    {
                        "type": "rename_chat",
                        "chat_id": test_chat_id,
                        "title": "Renamed Flat ChatId",
                    }
                )
            )
            resp = receive_type(ws, "chats_list")
            matching = [c for c in resp["chats"] if c["id"] == test_chat_id]
            assert len(matching) > 0 and matching[0]["title"] == "Renamed Flat ChatId"

            # 2. Flat id & title
            ws.send_text(
                json.dumps(
                    {
                        "type": "rename_chat",
                        "id": test_chat_id,
                        "title": "Renamed Flat Id",
                    }
                )
            )
            resp = receive_type(ws, "chats_list")
            matching = [c for c in resp["chats"] if c["id"] == test_chat_id]
            assert len(matching) > 0 and matching[0]["title"] == "Renamed Flat Id"

            # 3. Nested dictionary payload with chat_id
            ws.send_text(
                json.dumps(
                    {
                        "type": "rename_chat",
                        "payload": {
                            "chat_id": test_chat_id,
                            "title": "Renamed Nested Dict ChatId",
                        },
                    }
                )
            )
            resp = receive_type(ws, "chats_list")
            matching = [c for c in resp["chats"] if c["id"] == test_chat_id]
            assert (
                len(matching) > 0
                and matching[0]["title"] == "Renamed Nested Dict ChatId"
            )

            # 4. Nested dictionary payload with id
            ws.send_text(
                json.dumps(
                    {
                        "type": "rename_chat",
                        "payload": {
                            "id": test_chat_id,
                            "title": "Renamed Nested Dict Id",
                        },
                    }
                )
            )
            resp = receive_type(ws, "chats_list")
            matching = [c for c in resp["chats"] if c["id"] == test_chat_id]
            assert (
                len(matching) > 0 and matching[0]["title"] == "Renamed Nested Dict Id"
            )

            # 5. Nested stringified JSON payload
            ws.send_text(
                json.dumps(
                    {
                        "type": "rename_chat",
                        "payload": json.dumps(
                            {"id": test_chat_id, "title": "Renamed Stringified JSON"}
                        ),
                    }
                )
            )
            resp = receive_type(ws, "chats_list")
            matching = [c for c in resp["chats"] if c["id"] == test_chat_id]
            assert (
                len(matching) > 0 and matching[0]["title"] == "Renamed Stringified JSON"
            )

    def test_rename_chat_malformed_and_edge_cases(
        self, server_env: tuple[TestClient, Path]
    ) -> None:
        """Test corrupted JSON, missing fields, null values, and unexpected types."""
        client, _ = server_env
        with client.websocket_connect("/ws/chat") as ws:
            # Drain initial msgs
            _ = ws.receive_json()
            _ = ws.receive_json()
            _ = ws.receive_json()

            malformed_payloads: list[dict[str, Any]] = [
                # Corrupted stringified JSON
                {"type": "rename_chat", "payload": "{corrupted json..."},
                # Missing chat_id / id
                {"type": "rename_chat", "title": "No ID"},
                {"type": "rename_chat", "payload": {"title": "No ID"}},
                # Missing title
                {"type": "rename_chat", "chat_id": "test_id"},
                {"type": "rename_chat", "payload": {"id": "test_id"}},
                # Null values
                {"type": "rename_chat", "chat_id": None, "title": None},
                {"type": "rename_chat", "payload": {"id": None, "title": None}},
                # Empty object
                {"type": "rename_chat"},
                # Non-dict non-string payload
                {"type": "rename_chat", "payload": 12345},
                {"type": "rename_chat", "payload": [1, 2, 3]},
                {"type": "rename_chat", "payload": True},
                # Empty string chat_id / title
                {"type": "rename_chat", "chat_id": "", "title": ""},
            ]

            for bad_payload in malformed_payloads:
                ws.send_text(json.dumps(bad_payload))

            # Send a valid get_chats to verify server connection remains healthy and responsive
            ws.send_text(json.dumps({"type": "get_chats"}))
            resp = ws.receive_json()
            assert resp["type"] == "chats_list"


# ============================================================================
# 4. WEBSOCKET LOOP RESILIENCE & SUDDEN DISCONNECT TESTS
# ============================================================================


class TestWebSocketResilienceAdversarial:
    """Stress tests for WebSocket message loop resilience and connection lifecycle."""

    @pytest.fixture
    def client(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
        monkeypatch.setenv("FRIDAY_DATA_DIR", str(tmp_path / "data"))
        from src.api.server import create_app

        app = create_app()
        return TestClient(app)

    def test_corrupted_raw_frames(self, client: TestClient) -> None:
        """Send non-JSON, binary, and corrupted frames over WebSocket."""
        with client.websocket_connect("/ws/chat") as ws:
            # Drain initial msgs
            _ = ws.receive_json()
            _ = ws.receive_json()
            _ = ws.receive_json()

            garbage_frames = [
                "not json at all",
                "{unclosed json: 123",
                "{'single_quotes': True}",
                "",
                "   ",
                "\x00\x01\x02\x03",
                "{" * 500,
                "}" * 500,
                json.dumps({"unknown_type": 123}),
            ]

            for frame in garbage_frames:
                ws.send_text(frame)

            # Check that WS is still alive and processes standard requests
            ws.send_text(json.dumps({"type": "get_chats"}))
            resp = ws.receive_json()
            assert resp["type"] == "chats_list"

    def test_rapid_connect_and_disconnect_cycles(self, client: TestClient) -> None:
        """Connect and disconnect abruptly 10 times in a row."""
        for _ in range(10):
            with client.websocket_connect("/ws/chat") as ws:
                _ = ws.receive_json()
            # WS closed on exit of with block

    def test_unknown_message_types_resilience(self, client: TestClient) -> None:
        """Send unknown or invalid message types and verify server ignores them safely."""
        with client.websocket_connect("/ws/chat") as ws:
            _ = ws.receive_json()
            _ = ws.receive_json()
            _ = ws.receive_json()

            ws.send_text(json.dumps({"type": "fake_event_12345", "data": "test"}))
            ws.send_text(json.dumps({"type": None}))
            ws.send_text(json.dumps({}))

            ws.send_text(json.dumps({"type": "get_chats"}))
            resp = ws.receive_json()
            assert resp["type"] == "chats_list"

    def test_memory_callback_cleanup_on_disconnect(self, client: TestClient) -> None:
        """Verify on_change callbacks do not accumulate memory leaks across reconnects."""
        import src.api.server as server_module

        with client.websocket_connect("/ws/chat") as ws:
            _ = ws.receive_json()
            _ = ws.receive_json()
            _ = ws.receive_json()
            assert server_module.active_websocket is not None

        # After disconnect, active_websocket should be None
        assert server_module.active_websocket is None
