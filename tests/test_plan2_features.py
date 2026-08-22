from pathlib import Path

from src.memory.conversation import ConversationMemory

# Paths
ROOT_DIR = Path(__file__).parent.parent
UI_DIR = ROOT_DIR / "src" / "ui" / "src"
SERVER_PY = ROOT_DIR / "src" / "api" / "server.py"


class TestPlan2Features:
    def test_multi_model_support(self) -> None:
        """1. Verify Multi-Model API keys in config and UI Dropdown."""
        app_tsx = (UI_DIR / "App.tsx").read_text(encoding="utf-8")
        assert "id: 'openai'" in app_tsx
        assert "id: 'gemini'" in app_tsx
        assert "id: 'openrouter'" in app_tsx
        assert "id: 'ollama'" in app_tsx

    def test_tool_dashboard_redesign(self) -> None:
        """2. Verify ToolBlock grouping in App.tsx."""
        app_tsx = (UI_DIR / "App.tsx").read_text(encoding="utf-8")
        assert "<ToolBlock" in app_tsx
        assert "currentGroup.push(m)" in app_tsx
        assert "tools={g.tools as Message[]}" in app_tsx

    def test_chat_history_edit_regenerate(self) -> None:
        """3. Verify Smart Chat History Edit/Regenerate backend logic."""
        # Test ConversationMemory truncate logic
        mem = ConversationMemory(chat_id="test_edit")
        mem.add_user_message("First")
        mem.add_assistant_message("Answer 1")
        mem.add_user_message("Second")
        mem.add_assistant_message("Answer 2")

        messages = mem.get_messages(inject_system=False)
        assert len(messages) == 4

        target_id = messages[2]["id"]  # "Second" message ID
        mem.truncate_messages(target_id, inclusive=False)

        truncated = mem.get_messages(inject_system=False)
        assert len(truncated) == 2
        assert truncated[-1]["content"] == "Answer 1"

        # Verify server.py handles edit_message payload
        server_code = SERVER_PY.read_text(encoding="utf-8")
        assert "edit_message" in server_code
        assert "regenerate_message" in server_code
        assert "truncate_messages" in server_code

    def test_interactive_surveys(self) -> None:
        """4. Verify /grill-me system instruction injection."""
        server_code = SERVER_PY.read_text(encoding="utf-8")
        assert "/grill-me" in server_code
        assert "[SYSTEM]: The user has invoked the /grill-me command" in server_code

        translations = (UI_DIR / "i18n" / "translations.ts").read_text(encoding="utf-8")
        assert "grill_desc" in translations

    def test_auto_updates_github(self) -> None:
        """5. Verify Auto-updates logic in frontend."""
        app_tsx = (UI_DIR / "App.tsx").read_text(encoding="utf-8")
        assert "api.github.com/repos/Cristofervaltz/Friday/releases/latest" in app_tsx
        assert "updateAvailable" in app_tsx
        assert "A new version" in app_tsx
