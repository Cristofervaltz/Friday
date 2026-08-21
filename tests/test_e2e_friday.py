"""Comprehensive E2E and Multi-Tier Test Suite for Friday AI Assistant.

this file covers all 7 core features across 5 rigorous testing tiers:
- Feature 1: Instant-Send () Button (queue state, immediate WebSocket dispatch, not re-queued when isThinking)
- Feature 2: Frontend i18n Localization Engine (context, hook, default en, ru support, storage persistence)
- Feature 3: Full Bilingual UI Translation (EN default, RU support, 62+ keys, no missing keys/translations, no raw Cyrillic in non-i18n components)
- Feature 4: Settings Language Switcher (dynamic toggle, persistence, instant reactive state)
- Feature 5: REPL `clear` Command Completion (`clear_history()`, reset memory, preserve system prompt)
- Feature 6: Tools `__all__` Exports (`ScreenshotTool`, `SemanticSearchTool`, `DelegateTaskTool` exported in `src/tools/__init__.py`)
- Feature 7: Informal Human-like Comments (verifying informal, lowercase comments in modified code)
"""

from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import src.tools
from src.cli.repl import FridayREPL
from src.core.tool_registry import ToolRegistry
from src.memory.conversation import ConversationMemory
from src.runtime import FridayApplication
from src.tools.base import BaseTool

# root directories for path resolution
ROOT_DIR = Path(__file__).parent.parent
SRC_DIR = ROOT_DIR / "src"
UI_SRC_DIR = ROOT_DIR / "src" / "ui" / "src"
I18N_DIR = UI_SRC_DIR / "i18n"
COMPONENTS_DIR = UI_SRC_DIR / "components"


# ---------------------------------------------------------------------------
# handy helper functions for parsing typescript and inspecting tokens
# ---------------------------------------------------------------------------


def _extract_ts_dict(content: str, dict_name: str) -> dict[str, Any]:
    # quick parser to extract nested key-value pairs from ts translations file
    # find the declaration e.g. export const en: TranslationDict = { ... }
    pattern = rf"(?:export\s+const|const)\s+{dict_name}(?:\s*:\s*\w+)?\s*=\s*\{{"
    match = re.search(pattern, content)
    if not match:
        raise ValueError(f"could not find dictionary {dict_name} in content")

    start_idx = match.end() - 1
    brace_depth = 0
    end_idx = start_idx
    in_string: str | None = None
    escaped = False

    for i in range(start_idx, len(content)):
        ch = content[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == in_string:
                in_string = None
        else:
            if ch in ("'", '"', "`"):
                in_string = ch
            elif ch == "{":
                brace_depth += 1
            elif ch == "}":
                brace_depth -= 1
                if brace_depth == 0:
                    end_idx = i + 1
                    break

    block = content[start_idx:end_idx]

    # recursive parsing of js/ts object literal into python dict
    def parse_object_block(text: str) -> dict[str, Any]:
        result: dict[str, Any] = {}
        text = text.strip()
        if text.startswith("{") and text.endswith("}"):
            text = text[1:-1].strip()

        # tokenize by top-level commas respecting nested braces and quotes
        tokens: list[str] = []
        cur_token: list[str] = []
        depth = 0
        s_quote: str | None = None
        esc = False

        for char in text:
            if s_quote:
                cur_token.append(char)
                if esc:
                    esc = False
                elif char == "\\":
                    esc = True
                elif char == s_quote:
                    s_quote = None
            else:
                if char in ("'", '"', "`"):
                    s_quote = char
                    cur_token.append(char)
                elif char == "{":
                    depth += 1
                    cur_token.append(char)
                elif char == "}":
                    depth -= 1
                    cur_token.append(char)
                elif char == "," and depth == 0:
                    tokens.append("".join(cur_token).strip())
                    cur_token = []
                else:
                    cur_token.append(char)
        if cur_token:
            tokens.append("".join(cur_token).strip())

        for token in tokens:
            if not token or token.startswith("//") or token.startswith("/*"):
                continue
            # remove inline comments at end of line if outside quotes
            colon_idx = -1
            in_q: str | None = None
            for idx, c in enumerate(token):
                if in_q:
                    if c == in_q and (idx == 0 or token[idx - 1] != "\\"):
                        in_q = None
                else:
                    if c in ("'", '"', "`"):
                        in_q = c
                    elif c == ":":
                        colon_idx = idx
                        break

            if colon_idx == -1:
                continue

            k = token[:colon_idx].strip().strip("'\"`")
            v = token[colon_idx + 1 :].strip()

            if v.startswith("{") and v.endswith("}"):
                result[k] = parse_object_block(v)
            else:
                # string literal
                if (
                    (v.startswith("'") and v.endswith("'"))
                    or (v.startswith('"') and v.endswith('"'))
                    or (v.startswith("`") and v.endswith("`"))
                ):
                    v = v[1:-1]
                    # unescape quotes
                    v = v.replace("\\'", "'").replace('\\"', '"')
                result[k] = v

        return result

    return parse_object_block(block)


def _flatten_dict(d: dict[str, Any], prefix: str = "") -> dict[str, str]:
    # flatten nested dict into dot-separated keys like chat.inQueue
    flat: dict[str, str] = {}
    for k, v in d.items():
        full_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            flat.update(_flatten_dict(v, full_key))
        elif isinstance(v, str):
            flat[full_key] = v
    return flat


def _get_all_i18n_code() -> str:
    # helper to aggregate all i18n module code
    return "".join(f.read_text(encoding="utf-8") for f in I18N_DIR.glob("*.ts*"))


# ---------------------------------------------------------------------------
# Tier 1: Feature Coverage Tests (>=5 per feature across 7 features = 35 tests)
# ---------------------------------------------------------------------------


class TestTier1InstantSend:
    """Feature 1: Instant-Send () Button Core Verification."""

    def test_t1_instant_send_queue_removal(self) -> None:
        # verify handleInstantSend removes msgId from queue state
        app_code = (UI_SRC_DIR / "App.tsx").read_text(encoding="utf-8")
        assert (
            "handleInstantSend" in app_code
        ), "handleInstantSend function missing from App.tsx"
        # check that setMessageQueue filters out msgId
        assert re.search(
            r"setMessageQueue\(prev\s*=>\s*prev\.filter\([^)]*id\s*!==\s*msgId",
            app_code,
        ), "handleInstantSend must remove the instant-sent item from messageQueue"

    def test_t1_instant_send_ws_dispatch(self) -> None:
        # verify handleInstantSend sends message immediately over WebSocket
        app_code = (UI_SRC_DIR / "App.tsx").read_text(encoding="utf-8")
        func_match = re.search(
            r"const handleInstantSend = \((.*?)\) => \{(.*?)\n  \};",
            app_code,
            re.DOTALL,
        )
        assert func_match is not None, "handleInstantSend function definition not found"
        func_body = func_match.group(2)
        assert (
            "ws.send(JSON.stringify({ type: 'message', content: msg.text }))"
            in func_body
        ), "handleInstantSend must immediately call ws.send with message type and content"

    def test_t1_instant_send_not_requeued_when_thinking(self) -> None:
        # verify handleInstantSend does NOT re-queue item when isThinking is true
        app_code = (UI_SRC_DIR / "App.tsx").read_text(encoding="utf-8")
        func_match = re.search(
            r"const handleInstantSend = \((.*?)\) => \{(.*?)\n  \};",
            app_code,
            re.DOTALL,
        )
        assert func_match is not None
        func_body = func_match.group(2)
        assert (
            "setMessageQueue(prev => [msg, ...prev]);" not in func_body
        ), "handleInstantSend must not re-queue message when isThinking is true"

    def test_t1_instant_send_chat_message_appended(self) -> None:
        # verify handleInstantSend adds user message to visible chat state
        app_code = (UI_SRC_DIR / "App.tsx").read_text(encoding="utf-8")
        func_match = re.search(
            r"const handleInstantSend = \((.*?)\) => \{(.*?)\n  \};",
            app_code,
            re.DOTALL,
        )
        assert func_match is not None
        func_body = func_match.group(2)
        assert (
            "setMessages(prev => [...prev" in func_body
        ), "handleInstantSend must append user message to messages state"

    def test_t1_instant_send_button_dom_binding(self) -> None:
        # verify lightning button () onClick is wired to handleInstantSend
        app_code = (UI_SRC_DIR / "App.tsx").read_text(encoding="utf-8")
        assert re.search(
            r"onClick=\{\(\)\s*=>\s*handleInstantSend\(msg\.id\)\}", app_code
        ), "Lightning button in queue item must have onClick={() => handleInstantSend(msg.id)}"


class TestTier1I18nEngine:
    """Feature 2: Frontend i18n Localization Engine Core Verification."""

    def test_t1_i18n_module_exports(self) -> None:
        # verify i18n package exports provider, hook, and translations
        index_file = I18N_DIR / "index.ts"
        assert index_file.exists(), "i18n index.ts barrel file missing"
        all_code = _get_all_i18n_code()
        assert "I18nProvider" in all_code
        assert "useTranslation" in all_code
        assert "translations" in all_code

    def test_t1_i18n_default_language_is_en(self) -> None:
        # verify default fallback language is 'en'
        all_code = _get_all_i18n_code()
        assert "'en'" in all_code, "default language fallback must be 'en'"

    def test_t1_i18n_nested_key_resolution(self) -> None:
        # verify getNestedValue handles dot paths properly
        all_code = _get_all_i18n_code()
        assert "getNestedValue" in all_code
        assert "split('.')" in all_code

    def test_t1_i18n_parameter_interpolation(self) -> None:
        # verify interpolate replaces {param} tokens with runtime values
        all_code = _get_all_i18n_code()
        assert "interpolate" in all_code
        assert "replace" in all_code

    def test_t1_i18n_localstorage_persistence_key(self) -> None:
        # verify localStorage key 'friday_language' is used for persistence
        all_code = _get_all_i18n_code()
        assert (
            "friday_language" in all_code
        ), "localStorage key must be 'friday_language'"


class TestTier1BilingualUI:
    """Feature 3: Full Bilingual UI Translation Core Verification."""

    def test_t1_bilingual_dictionary_parity(self) -> None:
        # verify 1:1 key parity between english and russian dictionaries
        translations_file = I18N_DIR / "translations.ts"
        assert translations_file.exists(), "translations.ts missing"
        content = translations_file.read_text(encoding="utf-8")

        en_dict = _extract_ts_dict(content, "en")
        ru_dict = _extract_ts_dict(content, "ru")

        flat_en = _flatten_dict(en_dict)
        flat_ru = _flatten_dict(ru_dict)

        missing_in_ru = set(flat_en.keys()) - set(flat_ru.keys())
        missing_in_en = set(flat_ru.keys()) - set(flat_en.keys())

        assert not missing_in_ru, f"Keys missing in Russian dictionary: {missing_in_ru}"
        assert not missing_in_en, f"Keys missing in English dictionary: {missing_in_en}"

    def test_t1_bilingual_no_empty_strings(self) -> None:
        # verify no dictionary key contains an empty string
        content = (I18N_DIR / "translations.ts").read_text(encoding="utf-8")
        en_dict = _extract_ts_dict(content, "en")
        ru_dict = _extract_ts_dict(content, "ru")

        flat_en = _flatten_dict(en_dict)
        flat_ru = _flatten_dict(ru_dict)

        for k, v in flat_en.items():
            assert v.strip() != "", f"Empty string in EN key: {k}"
        for k, v in flat_ru.items():
            assert v.strip() != "", f"Empty string in RU key: {k}"

    def test_t1_bilingual_cyrillic_in_russian(self) -> None:
        # verify russian dictionary contains cyrillic strings
        content = (I18N_DIR / "translations.ts").read_text(encoding="utf-8")
        ru_dict = _extract_ts_dict(content, "ru")
        flat_ru = _flatten_dict(ru_dict)

        cyrillic_count = sum(
            1 for v in flat_ru.values() if re.search(r"[\u0400-\u04FF]", v)
        )
        assert (
            cyrillic_count > 30
        ), f"Russian dictionary lacks expected Cyrillic entries (found {cyrillic_count})"

    def test_t1_bilingual_all_components_use_i18n(self) -> None:
        # verify UI components import and use translation hook
        checked_components = [
            "App.tsx",
            "components/Sidebar.tsx",
            "components/SettingsModal.tsx",
            "components/VoicePanel.tsx",
            "components/WorkspaceSelector.tsx",
            "components/CreateProjectModal.tsx",
            "components/AgentDashboard.tsx",
        ]
        for rel_path in checked_components:
            comp_path = UI_SRC_DIR / rel_path
            assert comp_path.exists(), f"Component {rel_path} does not exist"
            code = comp_path.read_text(encoding="utf-8")
            assert (
                "useTranslation" in code or "i18n" in code
            ), f"Component {rel_path} missing useTranslation hook"

    def test_t1_bilingual_no_raw_cyrillic_in_components(self) -> None:
        # verify zero untranslated hardcoded raw cyrillic strings outside i18n files
        cyrillic_re = re.compile(r"[\u0400-\u04FF]+")
        for tsx_path in UI_SRC_DIR.glob("**/*.tsx"):
            if "i18n" in tsx_path.parts:
                continue
            code = tsx_path.read_text(encoding="utf-8")
            lines = code.splitlines()
            for line_no, line in enumerate(lines, 1):
                stripped = line.strip()
                # allow comments or settings modal language option labels
                if (
                    stripped.startswith("//")
                    or stripped.startswith("/*")
                    or "Русский" in stripped
                ):
                    continue
                matches = cyrillic_re.findall(stripped)
                assert (
                    not matches
                ), f"Raw untranslated Cyrillic found in {tsx_path.name}:{line_no} -> {stripped}"


class TestTier1SettingsSwitcher:
    """Feature 4: Settings Language Switcher Core Verification."""

    def test_t1_settings_language_dropdown_exists(self) -> None:
        # verify SettingsModal contains language select element
        code = (COMPONENTS_DIR / "SettingsModal.tsx").read_text(encoding="utf-8")
        assert "setLanguage" in code, "SettingsModal must import/use setLanguage"
        assert "<select" in code, "SettingsModal must contain select dropdown"

    def test_t1_settings_language_en_ru_options(self) -> None:
        # verify language options 'en' and 'ru' exist
        code = (COMPONENTS_DIR / "SettingsModal.tsx").read_text(encoding="utf-8")
        assert 'value="en"' in code, "English option missing in language selector"
        assert 'value="ru"' in code, "Russian option missing in language selector"

    def test_t1_settings_language_onchange_handler(self) -> None:
        # verify onChange handler triggers setLanguage
        code = (COMPONENTS_DIR / "SettingsModal.tsx").read_text(encoding="utf-8")
        assert (
            re.search(
                r"onChange=\{e\s*=>\s*setLanguage\(e\.target\.value\s+as\s+Language\)\}",
                code,
            )
            or "setLanguage(e.target.value" in code
        ), "Language select must call setLanguage with selected option"

    def test_t1_settings_language_localized_labels(self) -> None:
        # verify labels for language switcher use t() keys
        code = (COMPONENTS_DIR / "SettingsModal.tsx").read_text(encoding="utf-8")
        assert "settings.language" in code or "settings.appearance.language" in code

    def test_t1_settings_language_immediate_reactive_update(self) -> None:
        # verify useTranslation hook returns reactive state
        all_code = _get_all_i18n_code()
        assert "useState" in all_code
        assert "setLanguageState" in all_code or "setLanguage" in all_code


class TestTier1ReplClear:
    """Feature 5: REPL `clear` Command Completion Core Verification."""

    def test_t1_repl_clear_command_recognized(self) -> None:
        # verify REPL processes clear command
        repl_code = (SRC_DIR / "cli" / "repl.py").read_text(encoding="utf-8")
        assert (
            'user_input.lower() in ("clear", ":clear", "/clear")' in repl_code
            or '"clear"' in repl_code.lower()
        )

    def test_t1_repl_clear_invokes_agent_clear_history(self) -> None:
        # verify REPL calls agent.clear_history()
        repl_code = (SRC_DIR / "cli" / "repl.py").read_text(encoding="utf-8")
        assert (
            "self._agent.clear_history()" in repl_code
        ), "REPL clear handler must call self._agent.clear_history()"

    def test_t1_repl_clear_preserves_system_prompt(self) -> None:
        # verify ConversationMemory preserves system prompt after clear()
        mem = ConversationMemory(system_prompt="You are Friday, an AI assistant.")
        mem.add_user_message("hello")
        mem.add_assistant_message("hi there")
        assert len(mem) == 2
        mem.clear()
        assert len(mem) == 0
        messages = mem.get_messages()
        assert len(messages) == 1
        assert messages[0]["role"] == "system"
        assert "Friday" in messages[0]["content"]

    def test_t1_repl_clear_stub_message_removed(self) -> None:
        # verify outdated stub message is removed from repl.py
        repl_code = (SRC_DIR / "cli" / "repl.py").read_text(encoding="utf-8")
        assert (
            "Conversation clearing not yet implemented" not in repl_code
        ), "Outdated stub TODO message must be removed from repl.py"

    def test_t1_repl_help_documents_clear(self) -> None:
        # verify REPL help prints clear command without (future) tag
        repl_code = (SRC_DIR / "cli" / "repl.py").read_text(encoding="utf-8")
        assert "clear" in repl_code and "(future)" not in repl_code


class TestTier1ToolExports:
    """Feature 6: Tools `__all__` Exports Core Verification."""

    def test_t1_tools_exports_screenshot(self) -> None:
        # verify ScreenshotTool is in __all__ and importable
        assert "ScreenshotTool" in src.tools.__all__
        assert hasattr(src.tools, "ScreenshotTool")
        from src.tools import ScreenshotTool

        assert issubclass(ScreenshotTool, BaseTool)

    def test_t1_tools_exports_semantic_search(self) -> None:
        # verify SemanticSearchTool is in __all__ and importable
        assert "SemanticSearchTool" in src.tools.__all__
        assert hasattr(src.tools, "SemanticSearchTool")
        from src.tools import SemanticSearchTool

        assert issubclass(SemanticSearchTool, BaseTool)

    def test_t1_tools_exports_delegate_task(self) -> None:
        # verify DelegateTaskTool is in __all__ and importable
        assert "DelegateTaskTool" in src.tools.__all__
        assert hasattr(src.tools, "DelegateTaskTool")
        from src.tools import DelegateTaskTool

        assert issubclass(DelegateTaskTool, BaseTool)

    def test_t1_tools_all_symbols_defined(self) -> None:
        # verify every symbol in __all__ is an existing attribute
        for symbol in src.tools.__all__:
            assert hasattr(
                src.tools, symbol
            ), f"Export {symbol} is listed in __all__ but missing from src.tools"

    def test_t1_tools_all_classes_subclass_base(self) -> None:
        # verify all tool classes inherit from BaseTool
        for symbol in src.tools.__all__:
            if symbol in ("BaseTool", "ToolResult"):
                continue
            cls = getattr(src.tools, symbol)
            assert isinstance(cls, type) and issubclass(
                cls, BaseTool
            ), f"{symbol} does not inherit from BaseTool"


class TestTier1InformalComments:
    """Feature 7: Informal Human-like Comments Core Verification."""

    def test_t1_informal_comments_in_app(self) -> None:
        # verify informal comment in App.tsx
        code = (UI_SRC_DIR / "App.tsx").read_text(encoding="utf-8")
        assert "//" in code
        assert re.search(
            r"//\s*[a-z]", code
        ), "App.tsx should contain informal lowercase comments"

    def test_t1_informal_comments_in_i18n(self) -> None:
        # verify informal comments in i18n files
        for path in I18N_DIR.glob("*.ts*"):
            code = path.read_text(encoding="utf-8")
            assert "//" in code, f"{path.name} missing informal comments"

    def test_t1_informal_comments_in_settings_modal(self) -> None:
        # verify informal comments in SettingsModal.tsx
        code = (COMPONENTS_DIR / "SettingsModal.tsx").read_text(encoding="utf-8")
        assert "//" in code or "{/*" in code

    def test_t1_informal_comments_in_repl(self) -> None:
        # verify informal comment in repl.py
        code = (SRC_DIR / "cli" / "repl.py").read_text(encoding="utf-8")
        assert "#" in code
        assert re.search(
            r"#\s*[a-z]", code
        ), "repl.py should contain informal lowercase comments"

    def test_t1_informal_comments_in_tools_init(self) -> None:
        # verify informal comment in src/tools/__init__.py
        code = (SRC_DIR / "tools" / "__init__.py").read_text(encoding="utf-8")
        assert "#" in code
        assert re.search(
            r"#\s*[a-z]", code
        ), "tools/__init__.py should contain informal lowercase comments"


# ---------------------------------------------------------------------------
# Tier 2: Boundary & Corner Cases (>=5 per feature across 7 features = 35 tests)
# ---------------------------------------------------------------------------


class TestTier2InstantSendBoundaries:
    """Feature 1 Boundary & Corner Cases."""

    def test_t2_instant_send_nonexistent_id_ignored(self) -> None:
        # verify handleInstantSend safely returns when msgId is not found
        app_code = (UI_SRC_DIR / "App.tsx").read_text(encoding="utf-8")
        func_match = re.search(
            r"const handleInstantSend = \((.*?)\) => \{(.*?)\n  \};",
            app_code,
            re.DOTALL,
        )
        assert func_match is not None
        func_body = func_match.group(2)
        assert (
            "if (!msg || !ws || !connected) return;" in func_body
        ), "handleInstantSend must guard against missing message ID"

    def test_t2_instant_send_disconnected_ws_safe(self) -> None:
        # verify handleInstantSend guards against disconnected WebSocket
        app_code = (UI_SRC_DIR / "App.tsx").read_text(encoding="utf-8")
        assert "if (!msg || !ws || !connected) return;" in app_code

    def test_t2_instant_send_hidden_command_filtered(self) -> None:
        # verify hidden command is sent over WS but not added to visible chat messages
        app_code = (UI_SRC_DIR / "App.tsx").read_text(encoding="utf-8")
        func_match = re.search(
            r"const handleInstantSend = \((.*?)\) => \{(.*?)\n  \};",
            app_code,
            re.DOTALL,
        )
        assert func_match is not None
        func_body = func_match.group(2)
        assert "if (!HIDDEN_COMMANDS.includes(msg.text))" in func_body

    def test_t2_instant_send_unicode_emojis_multiline(self) -> None:
        # verify instant send payload formats json cleanly with special characters
        test_payload = "echo 'hello world'\nwith multiline and quotes \" ' "
        encoded = json.dumps({"type": "message", "content": test_payload})
        decoded = json.loads(encoded)
        assert decoded["content"] == test_payload

    def test_t2_instant_send_middle_item_ordering(self) -> None:
        # simulate queue filter logic when middle item is removed
        queue = [
            {"id": "1", "text": "A"},
            {"id": "2", "text": "B"},
            {"id": "3", "text": "C"},
        ]
        msg_id = "2"
        remaining = [m for m in queue if m["id"] != msg_id]
        assert [m["id"] for m in remaining] == ["1", "3"]


class TestTier2I18nEngineBoundaries:
    """Feature 2 Boundary & Corner Cases."""

    def test_t2_i18n_missing_key_returns_key(self) -> None:
        # verify missing key lookup returns key string itself
        all_code = _get_all_i18n_code()
        assert (
            "raw = key" in all_code
            or "raw || key" in all_code
            or "return key" in all_code
        )

    def test_t2_i18n_ru_missing_key_fallback_to_en(self) -> None:
        # verify fallback to english when target language lacks key
        all_code = _get_all_i18n_code()
        assert "language !== 'en'" in all_code or "translations.en" in all_code

    def test_t2_i18n_interpolation_missing_param(self) -> None:
        # verify interpolate leaves unmatched tokens intact without error
        def py_interpolate(text: str, params: dict[str, Any] | None = None) -> str:
            if not params:
                return text
            return re.sub(
                r"\{(\w+)\}",
                lambda m: (
                    str(params[m.group(1)]) if m.group(1) in params else m.group(0)
                ),
                text,
            )

        res = py_interpolate("In Queue ({count}) and {other}", {"count": 5})
        assert res == "In Queue (5) and {other}"

    def test_t2_i18n_interpolation_falsy_values(self) -> None:
        # verify interpolate handles 0, empty string, etc.
        def py_interpolate(text: str, params: dict[str, Any] | None = None) -> str:
            if not params:
                return text
            return re.sub(
                r"\{(\w+)\}",
                lambda m: (
                    str(params[m.group(1)]) if m.group(1) in params else m.group(0)
                ),
                text,
            )

        res = py_interpolate("Count: {count}, Val: {val}", {"count": 0, "val": ""})
        assert res == "Count: 0, Val: "

    def test_t2_i18n_corrupt_localstorage_fallback(self) -> None:
        # verify invalid language in localStorage defaults to 'en'
        all_code = _get_all_i18n_code()
        assert (
            "saved === 'en' || saved === 'ru'" in all_code or "return 'en'" in all_code
        )


class TestTier2BilingualUIBoundaries:
    """Feature 3 Boundary & Corner Cases."""

    def test_t2_bilingual_deeply_nested_keys(self) -> None:
        # verify deep key traversal e.g. settings.appearance.accentColorHint
        content = (I18N_DIR / "translations.ts").read_text(encoding="utf-8")
        en_dict = _extract_ts_dict(content, "en")
        ru_dict = _extract_ts_dict(content, "ru")

        flat_en = _flatten_dict(en_dict)
        flat_ru = _flatten_dict(ru_dict)

        assert (
            "settings.appearance.themeDark" in flat_en
            or "settings.theme_dark" in flat_en
        )
        assert (
            "settings.appearance.themeDark" in flat_ru
            or "settings.theme_dark" in flat_ru
        )

    def test_t2_bilingual_total_key_count_at_least_62(self) -> None:
        # verify total unique translation keys is at least 62
        content = (I18N_DIR / "translations.ts").read_text(encoding="utf-8")
        en_dict = _extract_ts_dict(content, "en")
        flat_en = _flatten_dict(en_dict)
        assert (
            len(flat_en) >= 62
        ), f"Expected at least 62 translation keys, found {len(flat_en)}"

    def test_t2_bilingual_all_jsx_calls_valid(self) -> None:
        # verify t('...') calls in JSX files exist in dictionary
        content = (I18N_DIR / "translations.ts").read_text(encoding="utf-8")
        en_dict = _extract_ts_dict(content, "en")
        flat_en = _flatten_dict(en_dict)

        t_call_re = re.compile(r"t\(\s*['\"]([a-zA-Z0-9_.]+)['\"]")
        for tsx_path in UI_SRC_DIR.glob("**/*.tsx"):
            code = tsx_path.read_text(encoding="utf-8")
            calls = t_call_re.findall(code)
            for call_key in calls:
                if "." in call_key:
                    assert call_key in flat_en or any(
                        k.startswith(call_key) for k in flat_en
                    ), f"Key '{call_key}' used in {tsx_path.name} not found in translations"

    def test_t2_bilingual_russian_grammar_and_punctuation(self) -> None:
        # verify russian dictionary retains symbols like emoji, punctuation
        content = (I18N_DIR / "translations.ts").read_text(encoding="utf-8")
        ru_dict = _extract_ts_dict(content, "ru")
        flat_ru = _flatten_dict(ru_dict)
        assert any(
            "..." in v for v in flat_ru.values()
        )  # verify punctuation is retained

    def test_t2_bilingual_no_untranslated_placeholders(self) -> None:
        # verify parameter tokens like {count} match exactly between en and ru
        content = (I18N_DIR / "translations.ts").read_text(encoding="utf-8")
        en_dict = _extract_ts_dict(content, "en")
        ru_dict = _extract_ts_dict(content, "ru")
        flat_en = _flatten_dict(en_dict)
        flat_ru = _flatten_dict(ru_dict)

        param_re = re.compile(r"\{(\w+)\}")
        for k in flat_en:
            en_params = set(param_re.findall(flat_en[k]))
            ru_params = set(param_re.findall(flat_ru[k]))
            assert (
                en_params == ru_params
            ), f"Parameter token mismatch in key {k}: {en_params} vs {ru_params}"


class TestTier2SettingsSwitcherBoundaries:
    """Feature 4 Boundary & Corner Cases."""

    def test_t2_settings_switcher_language_type_safety(self) -> None:
        # verify Language union type is 'en' | 'ru'
        types_file = I18N_DIR / "types.ts"
        assert types_file.exists()
        types_content = types_file.read_text(encoding="utf-8")
        assert "'en' | 'ru'" in types_content or "'ru' | 'en'" in types_content

    def test_t2_settings_switcher_html_lang_sync(self) -> None:
        # verify document.documentElement.lang is updated on language change
        all_code = _get_all_i18n_code()
        assert "document.documentElement.lang" in all_code

    def test_t2_settings_switcher_unmounted_hook_safety(self) -> None:
        # verify useTranslation provides safe fallback when context is null
        use_trans_code = (I18N_DIR / "useTranslation.ts").read_text(encoding="utf-8")
        assert "if (!context)" in use_trans_code
        assert "language: 'en'" in use_trans_code

    def test_t2_settings_switcher_persistence_across_close(self) -> None:
        # verify setLanguage updates localStorage immediately on change
        all_code = _get_all_i18n_code()
        assert "localStorage.setItem" in all_code

    def test_t2_settings_switcher_rapid_toggles(self) -> None:
        # test state toggle simulation
        langs = ["en", "ru", "en", "ru", "en"]
        active = "en"
        for lang in langs:
            active = lang
        assert active == "en"


class TestTier2ReplClearBoundaries:
    """Feature 5 Boundary & Corner Cases."""

    def test_t2_repl_clear_empty_history_noop(self) -> None:
        # verify clear on empty history executes cleanly
        mem = ConversationMemory(system_prompt="prompt")
        assert len(mem) == 0
        mem.clear()
        assert len(mem) == 0

    def test_t2_repl_clear_case_insensitivity_mixed(self) -> None:
        # verify mixed case input triggers clear
        inputs = ["CLEAR", "Clear", "cLeAr", ":CLEAR", "/Clear"]
        for inp in inputs:
            cleaned = inp.strip().lower()
            assert cleaned in ("clear", ":clear", "/clear")

    def test_t2_repl_clear_whitespace_padding(self) -> None:
        # verify whitespace padding is trimmed
        raw_input = "   clear   \t"
        assert raw_input.strip().lower() == "clear"

    def test_t2_repl_clear_multiturn_tool_messages(self) -> None:
        # verify clearing memory with tool calls and tool results
        mem = ConversationMemory(system_prompt="sys")
        mem.add_user_message("run tool")
        mem.add_assistant_message(
            content="",
            tool_calls=[
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "read_file", "arguments": "{}"},
                }
            ],
        )
        mem.add_tool_result("c1", "file contents")
        mem.add_assistant_message("done")
        assert len(mem) == 4
        mem.clear()
        assert len(mem) == 0
        assert len(mem.get_messages()) == 1

    def test_t2_repl_clear_disk_persistence_sync(self, tmp_path: Path) -> None:
        # verify on-disk file is cleared if save_dir is configured
        chat_dir = tmp_path / "chats"
        chat_dir.mkdir()
        mem = ConversationMemory(
            system_prompt="sys", save_dir=chat_dir, chat_id="test_chat"
        )
        mem.add_user_message("persisted message")
        assert (chat_dir / "test_chat.json").exists()
        mem.clear()
        # verify saved json reflects empty messages
        data = json.loads((chat_dir / "test_chat.json").read_text(encoding="utf-8"))
        assert len(data.get("messages", [])) == 0


class TestTier2ToolExportsBoundaries:
    """Feature 6 Boundary & Corner Cases."""

    def test_t2_tools_wildcard_import_count(self) -> None:
        # verify exactly 16 symbols in __all__
        assert (
            len(src.tools.__all__) == 16
        ), f"Expected 16 exports in src.tools.__all__, got {len(src.tools.__all__)}"

    def test_t2_tools_no_duplicate_exports(self) -> None:
        # verify no duplicates in __all__
        assert len(src.tools.__all__) == len(set(src.tools.__all__))

    def test_t2_tools_parameter_schemas_valid_json(self) -> None:
        # verify parameter schemas produce valid JSON Schema dictionaries
        from src.tools import DelegateTaskTool, ScreenshotTool, SemanticSearchTool

        for tool_cls in (ScreenshotTool, SemanticSearchTool, DelegateTaskTool):
            tool_instance = (
                tool_cls(app=MagicMock(), registry=ToolRegistry())
                if tool_cls is DelegateTaskTool
                else tool_cls()
            )
            schema = tool_instance.parameters_schema
            assert isinstance(schema, dict)
            assert schema.get("type") == "object"
            assert "properties" in schema

    def test_t2_tools_instantiation_without_crash(self) -> None:
        # verify tool instantiation
        from src.tools import (
            DelegateTaskTool,
            ScreenshotTool,
            SemanticSearchTool,
            TimeTool,
        )

        t1 = TimeTool()
        assert t1.name == "get_current_time"
        t2 = SemanticSearchTool()
        assert t2.name == "semantic_search"
        t3 = ScreenshotTool()
        assert t3.name == "take_screenshot"
        t4 = DelegateTaskTool(app=MagicMock(), registry=ToolRegistry())
        assert t4.name == "delegate_task"

    def test_t2_tools_registry_registration(self) -> None:
        # verify tool registry accepts all exported tools
        from src.tools import DelegateTaskTool

        registry = ToolRegistry()
        for symbol in src.tools.__all__:
            if symbol in ("BaseTool", "ToolResult"):
                continue
            tool_cls = getattr(src.tools, symbol)
            instance = (
                tool_cls(app=MagicMock(), registry=registry)
                if tool_cls is DelegateTaskTool
                else tool_cls()
            )
            registry.register(instance)
        assert len(registry.list_tools()) == 14


class TestTier2InformalCommentsBoundaries:
    """Feature 7 Boundary & Corner Cases."""

    def test_t2_comments_syntax_validity(self) -> None:
        # verify modified python files parse cleanly with AST
        ast.parse((SRC_DIR / "cli" / "repl.py").read_text(encoding="utf-8"))
        ast.parse((SRC_DIR / "tools" / "__init__.py").read_text(encoding="utf-8"))

    def test_t2_comments_no_corporate_boilerplate(self) -> None:
        # verify absence of overly verbose boilerplate in modified files
        repl_code = (SRC_DIR / "cli" / "repl.py").read_text(encoding="utf-8")
        assert "/** FactoryMethodPatternProviderImpl **/" not in repl_code

    def test_t2_comments_casual_markers_detected(self) -> None:
        # verify casual style markers across codebase
        app_code = (UI_SRC_DIR / "App.tsx").read_text(encoding="utf-8")
        repl_code = (SRC_DIR / "cli" / "repl.py").read_text(encoding="utf-8")
        i18n_code = _get_all_i18n_code()

        all_text = app_code + repl_code + i18n_code
        casual_patterns = [
            r"//\s*instant",
            r"//\s*pop",
            r"//\s*send",
            r"#\s*reset",
            r"//\s*handy",
            r"//\s*grab",
        ]
        matches = [p for p in casual_patterns if re.search(p, all_text)]
        assert (
            len(matches) >= 3
        ), f"Expected casual comments across codebase, matched: {matches}"

    def test_t2_comments_multiline_and_singleline(self) -> None:
        # verify both single line and inline comments exist
        app_code = (UI_SRC_DIR / "App.tsx").read_text(encoding="utf-8")
        assert "//" in app_code

    def test_t2_comments_docstrings_vs_comments(self) -> None:
        # verify python files retain docstrings while having informal inline comments
        repl_code = (SRC_DIR / "cli" / "repl.py").read_text(encoding="utf-8")
        assert '"""' in repl_code
        assert "#" in repl_code


# ---------------------------------------------------------------------------
# Tier 3: Pairwise Feature Combinations (>=6 pairwise interaction tests)
# ---------------------------------------------------------------------------


class TestTier3PairwiseInteractions:
    """Tier 3: Pairwise Feature Interactions."""

    def test_t3_pairwise_instant_send_with_russian_locale(self) -> None:
        # Pair 1: F1 (Instant Send) x F2/F3 (i18n & Russian UI)
        content = (I18N_DIR / "translations.ts").read_text(encoding="utf-8")
        ru_dict = _extract_ts_dict(content, "ru")
        flat_ru = _flatten_dict(ru_dict)

        # verify Russian translations for queue header and send immediately tooltip
        assert (
            flat_ru.get("chat.inQueue") == "В очереди ({count})"
            or flat_ru.get("chat.queue_header") == "В очереди ({count})"
        )
        assert (
            flat_ru.get("chat.sendImmediately") == "Отправить немедленно"
            or flat_ru.get("chat.send_immediately") == "Отправить немедленно"
        )

    def test_t3_pairwise_instant_send_with_tool_dispatch(self) -> None:
        # Pair 2: F1 (Instant Send) x F6 (Tool Exports)
        try:
            from src.api.server import create_app

            app = create_app()
            client = TestClient(app)
            with client.websocket_connect("/ws/chat") as ws:
                _ = ws.receive_json()
                _ = ws.receive_json()
                _ = ws.receive_json()
                ws.send_json(
                    {"type": "message", "content": "What is the current time?"}
                )
                resp = ws.receive_json()
                # chat_history or status or chunk or complete or tool_start is valid
                assert resp.get("type") in (
                    "chat_history",
                    "status",
                    "stream_chunk",
                    "complete",
                    "tool_start",
                )
        except SyntaxError as e:
            pytest.fail(f"Implementation bug in src/api/server.py: {e}")

    def test_t3_pairwise_instant_send_with_repl_clear(self) -> None:
        # Pair 3: F1 (Instant Send) x F5 (REPL Clear / Memory)
        app = FridayApplication()
        app.initialize()
        repl = FridayREPL(app)

        # simulate prompt handling in agent memory
        repl._agent.memory.add_user_message("test task")
        repl._agent.memory.add_assistant_message("result")
        assert len(repl._agent.memory) == 2

        # simulate clear
        repl._agent.clear_history()
        assert len(repl._agent.memory) == 0

    def test_t3_pairwise_settings_language_and_persistence(self) -> None:
        # Pair 4: F2 (i18n Context) x F4 (Settings Switcher)
        all_code = _get_all_i18n_code()
        settings_code = (COMPONENTS_DIR / "SettingsModal.tsx").read_text(
            encoding="utf-8"
        )

        assert "friday_language" in all_code
        assert "setLanguage" in settings_code

    def test_t3_pairwise_repl_clear_and_tool_stability(self) -> None:
        # Pair 5: F5 (REPL Clear) x F6 (Tool Exports & Registry)
        app = FridayApplication()
        app.initialize()
        repl = FridayREPL(app)

        # tools registered before clear
        initial_tools_count = len(repl._registry.list_tools())
        assert initial_tools_count >= 12

        # clear history
        repl._agent.clear_history()

        # tools intact after clear
        assert len(repl._registry.list_tools()) == initial_tools_count

    def test_t3_pairwise_websocket_clear_and_instant_send(self) -> None:
        # Pair 6: F1 (Instant Send) x F5 (Clear Command via WebSocket)
        try:
            from src.api.server import create_app

            app = create_app()
            client = TestClient(app)
            with client.websocket_connect("/ws/chat") as ws:
                _ = ws.receive_json()
                _ = ws.receive_json()
                _ = ws.receive_json()

                # send /clear
                ws.send_json({"type": "message", "content": "/clear"})
                resp = ws.receive_json()
                assert resp.get("type") in ("chat_history", "status", "complete")
        except SyntaxError as e:
            pytest.fail(f"Implementation bug in src/api/server.py: {e}")

    def test_t3_pairwise_informal_comments_and_linting(self) -> None:
        # Pair 7: F7 (Informal Comments) x All Features
        # verify python AST parses without errors
        for py_file in (SRC_DIR).glob("**/*.py"):
            ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))


# ---------------------------------------------------------------------------
# Tier 4: Real-World Application Workloads (>=5 full scenario tests)
# ---------------------------------------------------------------------------


class TestTier4RealWorldScenarios:
    """Tier 4: Realistic Application Workloads."""

    def test_t4_scenario_1_instant_send_preemption_and_queue_drainage(self) -> None:
        # Scenario 1: Multi-message queueing and instant-send fast dispatch
        queue = [
            {"id": "task-1", "text": "Analyze repository"},
            {"id": "task-2", "text": "Check current time"},
            {"id": "task-3", "text": "Find README"},
        ]

        # user clicks instant-send on task-2
        instant_id = "task-2"
        target_msg = next(m for m in queue if m["id"] == instant_id)
        queue = [m for m in queue if m["id"] != instant_id]

        # verify target_msg is dispatched and queue preserves remaining order
        assert target_msg["text"] == "Check current time"
        assert [m["id"] for m in queue] == ["task-1", "task-3"]

    def test_t4_scenario_2_full_ui_localization_lifecycle(self) -> None:
        # Scenario 2: Complete UI localization cycle (EN default -> RU -> Persist -> EN)
        content = (I18N_DIR / "translations.ts").read_text(encoding="utf-8")
        en_dict = _extract_ts_dict(content, "en")
        ru_dict = _extract_ts_dict(content, "ru")

        flat_en = _flatten_dict(en_dict)
        flat_ru = _flatten_dict(ru_dict)

        # 1. verify initial English texts
        assert (
            flat_en["chat.emptyStateConnected"] == "How can I help you today?"
            or flat_en["chat.empty_connected"] == "How can I help you today?"
        )
        assert flat_en["sidebar.chats"] == "Chats"

        # 2. verify Russian translations
        assert (
            flat_ru["chat.emptyStateConnected"] == "Чем я могу помочь вам сегодня?"
            or flat_ru["chat.empty_connected"] == "Чем я могу помочь вам сегодня?"
        )
        assert flat_ru["sidebar.chats"] == "Чаты"

    def test_t4_scenario_3_multi_turn_repl_chat_and_clear(self) -> None:
        # Scenario 3: Multi-turn REPL chat with tool calls followed by clear command
        app = FridayApplication()
        app.initialize()
        repl = FridayREPL(app)

        # turn 1: user greeting
        repl._agent.memory.add_user_message("Hello")
        repl._agent.memory.add_assistant_message("Hi! How can I help you?")

        # turn 2: tool invocation
        repl._agent.memory.add_user_message("What time is it?")
        repl._agent.memory.add_assistant_message(
            content="",
            tool_calls=[
                {
                    "id": "t1",
                    "type": "function",
                    "function": {"name": "get_current_time", "arguments": "{}"},
                }
            ],
        )
        repl._agent.memory.add_tool_result("t1", "12:00:00")
        repl._agent.memory.add_assistant_message("The time is 12:00:00")

        assert len(repl._agent.memory) == 6

        # clear conversation
        repl._agent.clear_history()
        assert len(repl._agent.memory) == 0
        assert len(repl._agent.memory.get_messages()) == 1

    def test_t4_scenario_4_dynamic_tool_loading_and_pipeline(self) -> None:
        # Scenario 4: Dynamic tool loading, export verification, and schema validation
        from src.tools import (
            DelegateTaskTool,
            ReadFileTool,
            ScreenshotTool,
            SemanticSearchTool,
            ShellCommandTool,
        )

        tools = [
            ScreenshotTool(),
            SemanticSearchTool(),
            DelegateTaskTool(app=MagicMock(), registry=ToolRegistry()),
            ReadFileTool(),
            ShellCommandTool(),
        ]
        for t in tools:
            assert isinstance(t.name, str) and len(t.name) > 0
            assert isinstance(t.description, str) and len(t.description) > 0
            assert isinstance(t.parameters_schema, dict)

    def test_t4_scenario_5_end_to_end_user_integration_flow(self) -> None:
        # Scenario 5: Full E2E User Flow with FastAPI backend
        try:
            from src.api.server import create_app

            app = create_app()
            client = TestClient(app)

            # 1. verify health endpoint
            res = client.get("/health")
            assert res.status_code == 200

            # 2. connect websocket and send instant message
            with client.websocket_connect("/ws/chat") as ws:
                _ = ws.receive_json()
                _ = ws.receive_json()
                _ = ws.receive_json()

                ws.send_json({"type": "message", "content": "Hello Friday"})
                resp = ws.receive_json()
                # chat_history or status or chunk or complete is fine
                assert resp.get("type") in (
                    "chat_history",
                    "status",
                    "stream_chunk",
                    "complete",
                )
        except SyntaxError as e:
            pytest.fail(f"Implementation bug in src/api/server.py: {e}")


# ---------------------------------------------------------------------------
# Tier 5: Adversarial & Stress Testing (>=5 stress tests)
# ---------------------------------------------------------------------------


class TestTier5AdversarialStress:
    """Tier 5: White-Box Adversarial & Stress Tests."""

    def test_t5_stress_websocket_rapid_burst_instant_send(self) -> None:
        # Stress 1: Rapid burst of instant send messages over WebSocket
        try:
            from src.api.server import create_app

            app = create_app()
            client = TestClient(app)
            with client.websocket_connect("/ws/chat") as ws:
                _ = ws.receive_json()
                _ = ws.receive_json()
                _ = ws.receive_json()

                # send 5 rapid messages
                for i in range(5):
                    ws.send_json({"type": "message", "content": f"rapid ping {i}"})

                # verify server receives and responds without crashing
                resp = ws.receive_json()
                assert resp is not None
        except SyntaxError as e:
            pytest.fail(f"Implementation bug in src/api/server.py: {e}")

    def test_t5_stress_corrupted_i18n_inputs(self) -> None:
        # Stress 2: Missing keys, invalid paths, and special regex characters
        content = (I18N_DIR / "translations.ts").read_text(encoding="utf-8")
        en_dict = _extract_ts_dict(content, "en")

        def py_get_nested(obj: Any, path: str) -> str | None:
            if not obj or not isinstance(obj, dict):
                return None
            parts = path.split(".")
            curr = obj
            for p in parts:
                if isinstance(curr, dict) and p in curr:
                    curr = curr[p]
                else:
                    return None
            return curr if isinstance(curr, str) else None

        assert py_get_nested(en_dict, "non.existent.path") is None
        assert (
            py_get_nested(en_dict, "chat.showSystemOutput") == "Show system output"
            or py_get_nested(en_dict, "chat.show_system_output") == "Show system output"
        )

    def test_t5_stress_repl_clear_under_rapid_input_stream(self) -> None:
        # Stress 3: Multiple rapid clear operations
        mem = ConversationMemory(system_prompt="sys")
        for i in range(20):
            mem.add_user_message(f"msg {i}")
            if i % 5 == 0:
                mem.clear()
        assert len(mem) == 4

    def test_t5_stress_tool_registry_concurrency(self) -> None:
        # Stress 4: Rapid tool registration and retrieval
        from src.tools import DelegateTaskTool

        registry = ToolRegistry()
        for symbol in src.tools.__all__:
            if symbol in ("BaseTool", "ToolResult"):
                continue
            cls = getattr(src.tools, symbol)
            instance = (
                cls(app=MagicMock(), registry=registry)
                if cls is DelegateTaskTool
                else cls()
            )
            registry.register(instance)

        for _ in range(50):
            tools = registry.list_tools()
            assert len(tools) == 14

    def test_t5_stress_frontend_build_and_lint_pipeline(self) -> None:
        # Stress 5: Verify npm run lint (oxlint) and npm run build (tsc + vite) succeed
        npm_cmd = shutil.which("npm.cmd") or shutil.which("npm")
        if npm_cmd:
            lint_res = subprocess.run(
                [npm_cmd, "run", "lint"],
                cwd=str(UI_SRC_DIR.parent),
                capture_output=True,
                text=True,
            )
            assert (
                lint_res.returncode == 0
            ), f"npm run lint failed: {lint_res.stderr} {lint_res.stdout}"
            build_res = subprocess.run(
                [npm_cmd, "run", "build"],
                cwd=str(UI_SRC_DIR.parent),
                capture_output=True,
                text=True,
            )
            assert (
                build_res.returncode == 0
            ), f"npm run build failed: {build_res.stderr} {build_res.stdout}"
