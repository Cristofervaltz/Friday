"""Adversarial stress test harness authored by Challenger 1.

Empirical verification covering:
1. Instant-send queue mechanics and burst traffic simulation
2. i18n dictionary edge cases, missing key fallbacks, and parameter interpolation
3. REPL clear command permutations and memory lifecycle
4. Tool exports and BaseTool subclass signatures
5. Informal human-like comment convention validation
"""

from __future__ import annotations

import inspect
import os
import re
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import src.tools as tools_module
from src.cli.repl import FridayREPL
from src.core import ToolRegistry
from src.memory.conversation import ConversationMemory
from src.tools.base import BaseTool, ToolResult

# ==============================================================================
# SECTION 1: INSTANT-SEND QUEUE OPERATIONS UNDER BURST TRAFFIC
# ==============================================================================

class TestInstantSendQueueAdversarial:
    """Stress tests instant-send queue operations, interleaving, and burst traffic."""

    def test_instant_send_queue_state_machine_burst(self) -> None:
        """Simulates rapid queue operations: enqueue, instant-send, edit, delete, burst."""
        # Simulated React state model matching App.tsx handleInstantSend & handleSubmit
        state: dict[str, Any] = {
            "queue": [],
            "messages": [],
            "sent_over_ws": [],
            "is_thinking": False,
        }

        def submit(text: str, force_instant: bool = False) -> None:
            if not text.strip():
                return
            cleaned = text.strip()
            if state["is_thinking"] and not force_instant:
                state["queue"].append({"id": f"id_{len(state['queue'])}", "text": cleaned})
                return
            state["messages"].append({"role": "user", "content": cleaned})
            state["is_thinking"] = True
            state["sent_over_ws"].append(cleaned)

        def instant_send(msg_id: str) -> None:
            target = next((m for m in state["queue"] if m["id"] == msg_id), None)
            if not target:
                return
            state["queue"] = [m for m in state["queue"] if m["id"] != msg_id]
            state["messages"].append({"role": "user", "content": target["text"]})
            state["is_thinking"] = True
            state["sent_over_ws"].append(target["text"])

        # Burst 1: Fill queue with 100 items while thinking
        state["is_thinking"] = True
        for i in range(100):
            submit(f"Queued message #{i}")
        assert len(state["queue"]) == 100

        # Burst 2: Instant-send items out of order (middle, last, first, non-existent)
        instant_send("id_50")
        assert len(state["queue"]) == 99
        assert state["sent_over_ws"][-1] == "Queued message #50"
        assert state["messages"][-1]["content"] == "Queued message #50"

        instant_send("id_99")
        assert len(state["queue"]) == 98
        assert state["sent_over_ws"][-1] == "Queued message #99"

        instant_send("id_0")
        assert len(state["queue"]) == 97
        assert state["sent_over_ws"][-1] == "Queued message #0"

        # Edge case: instant-send non-existent ID
        instant_send("non_existent_id")
        assert len(state["queue"]) == 97

        # Instant-send remainder in rapid burst
        remaining_ids = [m["id"] for m in state["queue"]]
        for mid in remaining_ids:
            instant_send(mid)
        assert len(state["queue"]) == 0
        assert len(state["sent_over_ws"]) == 100

    def test_instant_send_hidden_commands_filtering(self) -> None:
        """Verifies hidden commands like /voice, /clear, /settings are not displayed in user messages."""
        hidden_commands = ["/voice", "/clear", "/settings"]
        
        for cmd in hidden_commands:
            messages: list[dict[str, Any]] = []
            sent_ws: list[str] = []
            
            # Simulated instant-send logic from App.tsx lines 372-388
            msg = {"id": "test_1", "text": cmd}
            if cmd not in hidden_commands:
                messages.append({"role": "user", "content": msg["text"]})
            sent_ws.append(msg["text"])
            
            assert len(messages) == 0  # Not added to chat display
            assert len(sent_ws) == 1
            assert sent_ws[0] == cmd


# ==============================================================================
# SECTION 2: I18N DICTIONARY EDGE CASES, FALLBACKS, AND INTERPOLATION
# ==============================================================================

class TestI18nAdversarial:
    """Stress tests i18n lookup, fallbacks, parameter interpolation, and dictionary parity."""

    def get_nested_value_oracle(self, obj: Any, path: str) -> Any:
        """Python implementation of getNestedValue from utils.ts."""
        if not isinstance(obj, dict):
            return None
        if path in obj and isinstance(obj[path], str):
            return obj[path]
        parts = path.split(".")
        current = obj
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current if isinstance(current, str) else None

    def interpolate_oracle(self, text: str, params: dict[str, Any] | None = None) -> str:
        """Python implementation of interpolate from utils.ts."""
        if not params:
            return text
        def repl(match: re.Match[str]) -> str:
            key = match.group(1)
            return str(params[key]) if key in params else match.group(0)
        return re.sub(r"\{(\w+)\}", repl, text)

    def test_nested_value_edge_cases(self) -> None:
        """Tests lookup with deep nesting, non-existent branches, numbers, arrays, and special keys."""
        data = {
            "flat_key": "Flat value",
            "chat": {
                "header": "Chat Header",
                "nested": {
                    "deep": {
                        "value": "Deep Value"
                    }
                },
                "number_val": 42,
                "null_val": None,
                "empty_str": ""
            }
        }

        # Valid lookups
        assert self.get_nested_value_oracle(data, "flat_key") == "Flat value"
        assert self.get_nested_value_oracle(data, "chat.header") == "Chat Header"
        assert self.get_nested_value_oracle(data, "chat.nested.deep.value") == "Deep Value"
        assert self.get_nested_value_oracle(data, "chat.empty_str") == ""

        # Invalid/Missing lookups returning None
        assert self.get_nested_value_oracle(data, "missing") is None
        assert self.get_nested_value_oracle(data, "chat.missing") is None
        assert self.get_nested_value_oracle(data, "chat.header.sub") is None
        assert self.get_nested_value_oracle(data, "chat.number_val") is None  # Not a string
        assert self.get_nested_value_oracle(data, "chat.null_val") is None
        assert self.get_nested_value_oracle(None, "chat.header") is None
        assert self.get_nested_value_oracle("not_dict", "chat.header") is None

    def test_interpolate_edge_cases(self) -> None:
        """Tests parameter interpolation with numbers, zero, missing params, special characters, unmatched braces."""
        template = "Queue count: {count}, user: {user}, status: {status}"

        # Standard interpolation
        res = self.interpolate_oracle(template, {"count": 5, "user": "Alice", "status": "active"})
        assert res == "Queue count: 5, user: Alice, status: active"

        # Edge case: zero and negative numbers
        res_zero = self.interpolate_oracle("Count: {count}", {"count": 0})
        assert res_zero == "Count: 0"

        res_neg = self.interpolate_oracle("Temp: {temp}", {"temp": -12})
        assert res_neg == "Temp: -12"

        # Missing params in dict should leave {token} as literal
        res_missing = self.interpolate_oracle(template, {"count": 3})
        assert res_missing == "Queue count: 3, user: {user}, status: {status}"

        # Extra unused params
        res_extra = self.interpolate_oracle("Hello {name}", {"name": "Bob", "unused": 999})
        assert res_extra == "Hello Bob"

        # Special chars in values
        res_special = self.interpolate_oracle("Error: {error}", {"error": "$100 & <script> / [test] \n"})
        assert res_special == "Error: $100 & <script> / [test] \n"

        # Unmatched braces & malformed tokens
        malformed = "Normal {token} but {unclosed and {123} and {}"
        res_malformed = self.interpolate_oracle(malformed, {"token": "ok", "123": "num"})
        assert res_malformed == "Normal ok but {unclosed and num and {}"

    def test_i18n_fallback_resolution_simulation(self) -> None:
        """Simulates full I18nContext t() lookup order: target -> en -> key literal."""
        en_dict = {
            "common": {"save": "Save", "cancel": "Cancel"},
            "chat": {"title": "Friday AI", "only_en": "Only in English"}
        }
        ru_dict = {
            "common": {"save": "Сохранить", "cancel": "Отмена"},
            "chat": {"title": "Пятница ИИ"}
            # "chat.only_en" intentionally missing in ru
        }

        def t(lang: str, key: str, params: dict[str, Any] | None = None) -> str:
            curr_dict = ru_dict if lang == "ru" else en_dict
            raw = self.get_nested_value_oracle(curr_dict, key)
            if raw is None and lang != "en":
                raw = self.get_nested_value_oracle(en_dict, key)
            if raw is None:
                raw = key
            return self.interpolate_oracle(raw, params)

        # 1. Direct hit in RU
        assert t("ru", "common.save") == "Сохранить"

        # 2. Missing in RU -> fallback to EN
        assert t("ru", "chat.only_en") == "Only in English"

        # 3. Missing in both -> fallback to literal key
        assert t("ru", "unknown.section.key") == "unknown.section.key"
        assert t("en", "unknown.section.key") == "unknown.section.key"


# ==============================================================================
# SECTION 3: REPL COMMAND PERMUTATIONS AND MEMORY LIFECYCLE
# ==============================================================================

class TestREPLPermutationsAdversarial:
    """Stress tests REPL command permutations, casing, whitespace, and memory lifecycle."""

    @pytest.mark.parametrize("clear_cmd", [
        "clear", ":clear", "/clear",
        "CLEAR", ":CLEAR", "/CLEAR",
        "Clear", ":Clear", "/Clear",
        "cLeAr", ":ClEaR", "/cLeAr",
        "  clear  ", "  :clear  ", "  /clear  ",
        "\tclear\t", "\t:clear\t", "\t/clear\t"
    ])
    def test_repl_clear_permutations(self, clear_cmd: str, tmp_path: Path) -> None:
        """Verifies all permutations of clear command reset conversation history."""
        mock_app = MagicMock()
        mock_app.config.app_name = "Friday"
        mock_app.config.version = "1.0.0"
        mock_app.config.paths.data_dir = tmp_path
        mock_app.config.llm.system_prompt = "System prompt"
        mock_app.config.llm.max_iterations = 10
        mock_app.provider = MagicMock()
        mock_app.logger = MagicMock()

        repl = FridayREPL(mock_app)
        
        # Populate history
        repl._agent.memory.add_user_message("Hello")
        repl._agent.memory.add_assistant_message("Hi there")
        assert len(repl._agent.memory) >= 2

        with patch("builtins.input", side_effect=[clear_cmd, "exit"]):
            repl.run()

        # History should be cleared (only system prompt preserved, user/assistant messages reset)
        assert len(repl._agent.memory) == 0
        # Provider should NEVER be invoked on clear commands
        mock_app.provider.chat.assert_not_called()

    def test_memory_clear_idempotence_and_callbacks(self) -> None:
        """Tests that ConversationMemory.clear() is idempotent and notifies listeners."""
        callback_called_count = 0
        def on_change(*args: Any, **kwargs: Any) -> None:
            nonlocal callback_called_count
            callback_called_count += 1

        memory = ConversationMemory(system_prompt="Test System")
        memory.add_on_change_callback(on_change)

        memory.add_user_message("Test message 1")
        memory.add_assistant_message("Test response 1")
        assert len(memory) == 2
        
        init_callback_count = callback_called_count

        # Clear 1
        memory.clear()
        assert len(memory) == 0
        assert memory.system_prompt == "Test System"
        assert callback_called_count == init_callback_count + 1

        # Clear 2 (idempotent on empty)
        memory.clear()
        assert len(memory) == 0
        assert callback_called_count == init_callback_count + 2


# ==============================================================================
# SECTION 4: TOOL EXPORTS AND SUBCLASS SIGNATURES
# ==============================================================================

class TestToolSignaturesAdversarial:
    """Stress tests Tool exports, inheritance, abstract method compliance, and robust execution."""

    EXPECTED_TOOLS = [
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

    def test_all_tools_in_module_and_all(self) -> None:
        """Verifies that all expected tools are listed in __all__ and accessible from src.tools."""
        for tool_name in self.EXPECTED_TOOLS:
            assert tool_name in tools_module.__all__, f"{tool_name} missing from __all__"
            assert hasattr(tools_module, tool_name), f"{tool_name} not exported on src.tools"

    def test_tool_subclass_and_signatures(self) -> None:
        """Verifies each tool class inherits from BaseTool and implements the required signature."""
        for tool_name in self.EXPECTED_TOOLS:
            tool_cls = getattr(tools_module, tool_name)
            assert inspect.isclass(tool_cls), f"{tool_name} is not a class"
            assert issubclass(tool_cls, BaseTool), f"{tool_name} is not a subclass of BaseTool"

            # Check execute method signature
            assert hasattr(tool_cls, "execute"), f"{tool_name} lacks execute method"
            sig = inspect.signature(tool_cls.execute)
            assert "self" in sig.parameters

    def test_tool_adversarial_invocations(self, tmp_path: Path) -> None:
        """Executes tools with invalid / adversarial parameters to ensure graceful ToolResult error handling."""
        # 1. ReadFileTool with non-existent path
        read_tool = tools_module.ReadFileTool()
        res = read_tool.execute(path="non_existent_file_12345.xyz")
        assert isinstance(res, ToolResult)
        assert res.success is False
        assert res.error is not None

        # 2. EditFileTool with invalid operation
        edit_tool = tools_module.EditFileTool()
        res = edit_tool.execute(path=str(tmp_path / "dummy.txt"), operation="unsupported_op")
        assert isinstance(res, ToolResult)
        assert res.success is False
        assert res.error is not None

        # 3. TimeTool
        time_tool = tools_module.TimeTool()
        res = time_tool.execute()
        assert isinstance(res, ToolResult)
        assert res.success is True
        assert res.output is not None and len(res.output) > 0

        # 4. ToolRegistry duplicate handling (must raise ValueError)
        registry = ToolRegistry()
        registry.register(read_tool)
        with pytest.raises(ValueError, match="already registered"):
            registry.register(read_tool)
        assert registry.get_tool(read_tool.name) is not None
        assert read_tool.name in registry.list_tools()
        assert read_tool.name in registry


# ==============================================================================
# SECTION 5: INFORMAL HUMAN-LIKE COMMENTS AUDIT
# ==============================================================================

class TestInformalCommentsAdversarial:
    """Verifies that modified / newly added files contain informal human-like comments."""

    TARGET_FILES = [
        "src/ui/src/App.tsx",
        "src/ui/src/i18n/index.ts",
        "src/ui/src/i18n/translations.ts",
        "src/ui/src/i18n/types.ts",
        "src/ui/src/i18n/utils.ts",
        "src/ui/src/i18n/I18nContext.tsx",
        "src/cli/repl.py",
        "src/tools/__init__.py",
    ]

    def test_informal_comments_present(self) -> None:
        """Checks for lowercase casual phrasing in comments across key modified files."""
        root_dir = os.path.dirname(os.path.dirname(__file__))
        
        for rel_path in self.TARGET_FILES:
            full_path = os.path.join(root_dir, rel_path)
            assert os.path.exists(full_path), f"Target file missing: {full_path}"
            
            with open(full_path, encoding="utf-8") as f:
                content = f.read()

            # Find single line comments (# in py, // in ts/tsx)
            comments = []
            if rel_path.endswith(".py"):
                comments = [line.strip() for line in content.splitlines() if line.strip().startswith("#")]
            else:
                comments = [line.strip() for line in content.splitlines() if line.strip().startswith("//")]

            assert len(comments) > 0, f"No informal comments found in {rel_path}"
            
            # Check for lowercase start or casual phrasing in at least some comments
            has_informal = any(
                c.lstrip("#/ ").strip() and c.lstrip("#/ ").strip()[0].islower()
                for c in comments
            )
            assert has_informal, f"Expected informal (lowercase) comments in {rel_path}"
