"""Unit tests for Friday interactive REPL commands and clear functionality."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.cli.repl import FridayREPL
from src.llm.base import BaseLLMProvider, LLMResponse


class DummyLLMProvider(BaseLLMProvider):
    # tiny dummy provider for repl tests
    def generate(self, prompt: str) -> str:
        return "dummy response"

    def generate_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        return LLMResponse(content="Dummy response from LLM", finish_reason="stop")

    def model_name(self) -> str:
        return "dummy-model"


@pytest.fixture
def mock_app(tmp_path: Any) -> MagicMock:
    # create a mock app with configs for repl testing
    app = MagicMock()
    app.config = MagicMock()
    app.config.app_name = "Friday"
    app.config.version = "0.1.0"
    app.config.paths.data_dir = tmp_path / "data"
    app.config.paths.app_home = tmp_path
    app.config.llm.system_prompt = "You are a test assistant."
    app.config.llm.max_iterations = 5
    app.config.speech_language = "en"
    app.provider = DummyLLMProvider()
    app.logger = MagicMock()
    return app


def test_repl_init_tools(mock_app: MagicMock) -> None:
    # check that repl registers expected tools on startup
    repl = FridayREPL(mock_app)
    tools = repl._registry.list_tools()
    assert "read_file" in tools
    assert "write_file" in tools
    assert "edit_file" in tools
    assert "list_files" in tools
    assert "execute_command" in tools
    assert "delegate_task" in tools


def test_repl_help_command(
    mock_app: MagicMock, capsys: pytest.CaptureFixture[str]
) -> None:
    # test help message prints active clear command without '(future)' note
    repl = FridayREPL(mock_app)
    repl._print_help()
    captured = capsys.readouterr().out

    assert "clear" in captured
    assert "(future)" not in captured
    assert "exit, quit" in captured
    assert "read <path>" in captured


@pytest.mark.parametrize(
    "clear_cmd", ["clear", ":clear", "/clear", "CLEAR", ":Clear", "/CLEAR"]
)
def test_repl_clear_commands(
    mock_app: MagicMock,
    clear_cmd: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # verify that clear variants properly reset conversation history
    repl = FridayREPL(mock_app)

    # populate history with user and assistant msgs
    repl._agent.memory.add_user_message("hello test")
    repl._agent.memory.add_assistant_message("hello back")
    assert len(repl._agent.get_history()) == 3  # system + user + assistant

    # simulate user entering clear command
    with patch("builtins.input", return_value=clear_cmd):
        repl._process_input()

    # history should now only retain the system prompt
    history = repl._agent.get_history()
    assert len(history) == 1
    assert history[0]["role"] == "system"

    out = capsys.readouterr().out
    assert "Conversation history cleared." in out


def test_repl_exit_and_quit(mock_app: MagicMock) -> None:
    # test exit and quit commands stop repl running flag
    repl = FridayREPL(mock_app)
    repl._running = True

    with patch("builtins.input", return_value="exit"):
        repl._process_input()
    assert repl._running is False

    repl._running = True
    with patch("builtins.input", return_value="quit"):
        repl._process_input()
    assert repl._running is False


def test_repl_empty_input(mock_app: MagicMock) -> None:
    # verify empty input returns immediately without error
    repl = FridayREPL(mock_app)
    with patch("builtins.input", return_value="   "):
        repl._process_input()


def test_repl_read_file(
    mock_app: MagicMock,
    tmp_path: Any,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # test built-in read file command in repl
    test_file = tmp_path / "sample.txt"
    test_file.write_text("sample content here", encoding="utf-8")

    repl = FridayREPL(mock_app)
    with patch("builtins.input", return_value=f"read {test_file}"):
        repl._process_input()

    out = capsys.readouterr().out
    assert "sample content here" in out


def test_repl_list_files(
    mock_app: MagicMock,
    tmp_path: Any,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # test list files command in repl
    (tmp_path / "file1.txt").write_text("1", encoding="utf-8")
    repl = FridayREPL(mock_app)
    with patch("builtins.input", return_value=f"list {tmp_path}"):
        repl._process_input()

    out = capsys.readouterr().out
    assert "file1.txt" in out


def test_repl_handle_message(mock_app: MagicMock) -> None:
    # test normal chat message sent to agent run
    repl = FridayREPL(mock_app)
    with patch.object(repl._agent, "run", return_value="Done!") as mock_run:
        with patch("builtins.input", return_value="what is 2+2?"):
            repl._process_input()
        mock_run.assert_called_once_with("what is 2+2?")


def test_repl_run_loop(mock_app: MagicMock) -> None:
    # test the main repl loop with graceful exit
    repl = FridayREPL(mock_app)
    with patch("builtins.input", side_effect=["help", "clear", "exit"]):
        exit_code = repl.run()
        assert exit_code == 0
