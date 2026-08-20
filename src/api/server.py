"""FastAPI server for the Friday GUI."""

import asyncio
import concurrent.futures
import json
import logging
import sys
import threading
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

try:
    import uvicorn  # type: ignore
    import webview  # type: ignore
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect  # type: ignore
    from fastapi.responses import HTMLResponse  # type: ignore
    from fastapi.staticfiles import StaticFiles  # type: ignore
    from starlette.websockets import WebSocketState  # type: ignore
except ImportError:
    FastAPI = None  # type: ignore
    uvicorn = None  # type: ignore
    webview = None  # type: ignore
    WebSocketState = None  # type: ignore

from ..cli.repl import FridayREPL
from ..runtime import FridayApplication

logger = logging.getLogger(__name__)

active_websocket: Any = None
server_loop: asyncio.AbstractEventLoop | None = None
permission_event: threading.Event = threading.Event()
permission_result: bool = False
_permission_lock: threading.Lock = threading.Lock()
wake_word_detector: Any = None
active_tts: Any = None

# Active background task tracking & thread pool
active_agent_tasks: set[asyncio.Task[Any]] = set()
_agent_executor: concurrent.futures.ThreadPoolExecutor | None = None


def safe_send_ws(
    ws: Any,
    payload: dict[str, Any],
    loop: asyncio.AbstractEventLoop | None,
) -> None:
    """Send text frame over WebSocket safely from worker threads."""
    if loop is None or loop.is_closed() or not loop.is_running():
        return
    if ws is None:
        return

    # Check client_state if present
    client_state = getattr(ws, "client_state", None)
    if client_state is not None and hasattr(client_state, "name"):
        if WebSocketState is not None and client_state != WebSocketState.CONNECTED:
            return

    async def _send() -> None:
        try:
            curr_state = getattr(ws, "client_state", None)
            if curr_state is not None and hasattr(curr_state, "name"):
                if WebSocketState is not None and curr_state != WebSocketState.CONNECTED:
                    return
            await ws.send_text(json.dumps(payload))
        except Exception:
            pass

    try:
        asyncio.run_coroutine_threadsafe(_send(), loop)
    except Exception:
        pass



def _handle_voice_for_ws(
    websocket: "WebSocket",
    friday_app: "FridayApplication",
    loop: asyncio.AbstractEventLoop,
) -> None:
    """Handle voice input for WebSocket: transcribe only, return text to UI.

    Unlike _handle_voice in the REPL, this does NOT send the transcribed
    text to the LLM. Instead, it sends it back via WebSocket so the
    frontend can populate the input field and the user can review/edit.
    """
    try:
        from ..speech import GoogleSpeechProvider

        print("Initializing microphone...")

        provider = GoogleSpeechProvider(language=friday_app.config.speech_language)
        print("Listening...")

        global voice_abort_event
        voice_abort_event.clear()
        text = provider.listen_and_transcribe(abort_event=voice_abort_event)

        print(f"Voice captured: {text}")

        # Send transcribed text back to the UI as a special message type
        safe_send_ws(websocket, {"type": "voice_result", "text": text}, loop)
    except RuntimeError as exc:
        safe_send_ws(websocket, {"type": "voice_error", "error": str(exc)}, loop)
    except TimeoutError:
        safe_send_ws(
            websocket,
            {
                "type": "voice_error",
                "error": "No speech detected. Microphone timed out.",
            },
            loop,
        )
    except Exception as exc:
        if "aborted by user" in str(exc):
            safe_send_ws(websocket, {"type": "done", "command": "/voice"}, loop)
        else:
            safe_send_ws(websocket, {"type": "voice_error", "error": str(exc)}, loop)


def create_app() -> "FastAPI":
    """Create the FastAPI application."""
    if FastAPI is None:
        raise RuntimeError("FastAPI is not installed. Run 'pip install friday[gui]'.")

    friday_app = FridayApplication()
    friday_app.initialize()

    # We use REPL to reuse the existing Agent and Tools wiring
    friday_repl = FridayREPL(friday_app)
    friday_app.repl = friday_repl  # type: ignore

    def _get_permission_mode() -> str:
        """Read permission_mode from saved settings."""
        from .._compat import load_settings_safe

        try:
            s = load_settings_safe()
            return str(s.get("permission_mode", "default"))
        except Exception:
            return "default"

    def _get_custom_rules() -> dict[str, list[str]]:
        """Read custom permission rules from saved settings."""
        from .._compat import load_settings_safe

        try:
            s = load_settings_safe()
            return {
                "allow": [
                    r.strip()
                    for r in str(s.get("perm_allow", "")).split(",")
                    if r.strip()
                ],
                "deny": [
                    r.strip()
                    for r in str(s.get("perm_deny", "")).split(",")
                    if r.strip()
                ],
                "ask": [
                    r.strip()
                    for r in str(s.get("perm_ask", "")).split(",")
                    if r.strip()
                ],
            }
        except Exception:
            return {"allow": [], "deny": [], "ask": []}

    def _command_matches_any(command: str, patterns: list[str]) -> bool:
        """Check if command starts with any of the given patterns."""
        cmd_lower = command.strip().lower()
        for p in patterns:
            if cmd_lower.startswith(p.lower()):
                return True
        return False

    def _ask_user_permission(command: str) -> bool:
        """Send permission request to UI and wait for response."""
        global active_websocket, server_loop, permission_event, permission_result
        if active_websocket is None or server_loop is None:
            return False

        # lock permission prompts so concurrent subagents dont clobber each other
        with _permission_lock:
            permission_event.clear()
            safe_send_ws(
                active_websocket,
                {"type": "permission_request", "action": command},
                server_loop,
            )

            # wait up to 5 mins for user confirmation
            waited = permission_event.wait(timeout=300.0)
            if not waited:
                return False
            return permission_result

    def gui_confirmation_callback(command: str) -> bool:
        mode = _get_permission_mode()

        if mode == "turbo":
            return True

        if mode == "custom":
            rules = _get_custom_rules()
            if _command_matches_any(command, rules["deny"]):
                return False
            if _command_matches_any(command, rules["allow"]):
                return True
            if _command_matches_any(command, rules["ask"]):
                return _ask_user_permission(command)
            # If command doesn't match any rule, ask by default
            return _ask_user_permission(command)

        # mode == "default" — ask for everything
        return _ask_user_permission(command)

    # Overwrite the execute method in ToolRegistry to intercept all tools
    original_execute = friday_repl._registry.execute

    def registry_execute_with_permission(name: str, **kwargs: object) -> Any:
        from src.tools.base import ToolResult

        cmd_str = name
        if name == "execute_command":
            cmd_str = str(kwargs.get("command", kwargs))
        else:
            args = ", ".join(f"{k}={v!r}" for k, v in kwargs.items())
            cmd_str = f"{name}({args})"

        if not gui_confirmation_callback(str(cmd_str)):
            return ToolResult(
                success=False, error=f"User rejected permission to run: {cmd_str}"
            )

        return original_execute(name, **kwargs)

    friday_repl._registry.execute = registry_execute_with_permission  # type: ignore

    # Overwrite the executor in ShellCommandTool to bypass its internal safety check
    # since we are now handling permissions at the registry level.
    from src.executor.command_executor import CommandExecutor

    try:
        shell_tool = friday_repl._registry.get_tool("execute_command")
        shell_tool.executor = CommandExecutor(confirmation_callback=lambda cmd: True)  # type: ignore
    except KeyError:
        pass

    # We only really support one active GUI connected to the local agent
    # active_connection = None

    global active_websocket, server_loop, permission_event, permission_result
    global wake_word_detector, active_tts
    active_websocket = None
    server_loop = None
    wake_word_detector = None
    active_tts = None
    permission_event = threading.Event()
    permission_result = False
    global agent_cancel_event
    agent_cancel_event = threading.Event()
    global voice_abort_event
    voice_abort_event = threading.Event()

    def _on_wake_word() -> None:
        global active_websocket, server_loop
        if active_websocket and server_loop:
            try:
                safe_send_ws(active_websocket, {"type": "wake_word"}, server_loop)
            except Exception as e:
                print(f"Failed to send wake word signal: {e}")

    def _start_wake_word() -> None:
        global wake_word_detector
        if wake_word_detector is None:
            try:
                from ..speech.wake_word import WakeWordDetector

                wake_word_detector = WakeWordDetector()
                wake_word_detector.start(_on_wake_word)
                print("Wake Word detector started successfully.")
            except Exception as e:
                import traceback

                print(f"Failed to start Wake Word: {e}")
                traceback.print_exc()

    def _stop_wake_word() -> None:
        """Stop the wake word detector thread safely."""
        global wake_word_detector
        if wake_word_detector is not None:
            try:
                wake_word_detector.stop()
            except Exception as exc:
                logger.warning("Error stopping wake word detector: %s", exc)
            finally:
                wake_word_detector = None

    @asynccontextmanager
    async def lifespan(app: "FastAPI") -> AsyncGenerator[None, None]:
        """Manage server startup and graceful 7-stage shutdown lifecycle."""
        global server_loop, _agent_executor, wake_word_detector, active_tts
        server_loop = asyncio.get_running_loop()
        _agent_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=4, thread_name_prefix="friday-agent"
        )

        # Startup sequence
        _start_wake_word()

        try:
            yield
        finally:
            # --- 7-STAGE GRACEFUL SHUTDOWN SEQUENCE ---
            # 1. Cancel in-flight agent tasks & stop active TTS
            global active_agent_tasks, active_tts
            if active_tts is not None:
                try:
                    active_tts.stop()
                except Exception as exc:
                    logger.warning("Error stopping TTS on shutdown: %s", exc)
                finally:
                    active_tts = None

            if active_agent_tasks:
                for task in list(active_agent_tasks):
                    task.cancel()
                await asyncio.gather(*list(active_agent_tasks), return_exceptions=True)
                active_agent_tasks.clear()

            if _agent_executor is not None:
                _agent_executor.shutdown(wait=False, cancel_futures=True)
                _agent_executor = None

            # 2. Stop wake word detector
            _stop_wake_word()

            # 4. Clean up Pygame audio subsystem
            try:
                from src.speech.tts_provider import cleanup_audio_subsystem

                await asyncio.to_thread(cleanup_audio_subsystem)
            except Exception as exc:
                logger.warning("Error cleaning up audio subsystem: %s", exc)

            # 5. Shut down MCP plugin processes & background event loops
            if hasattr(friday_repl, "_registry"):
                try:
                    friday_repl._registry.shutdown_all_plugins()
                except Exception as exc:
                    logger.warning("Error shutting down MCP plugins: %s", exc)

            # 6. Shut down FridayApplication runtime
            try:
                friday_app.shutdown()
            except Exception as exc:
                logger.warning("Error shutting down FridayApplication: %s", exc)

            # 7. Clean up runtime port file
            try:
                from src.utils.port import cleanup_runtime_port

                cleanup_runtime_port(
                    friday_app.config.paths.app_home if friday_app.config else None
                )
            except Exception:
                pass

    app = FastAPI(title="Friday API", lifespan=lifespan)

    @app.websocket("/ws/chat")  # type: ignore
    async def websocket_endpoint(websocket: "WebSocket") -> None:
        global active_websocket, server_loop
        await websocket.accept()
        loop = asyncio.get_event_loop()
        server_loop = loop
        active_websocket = websocket

        # On connection, sync backend OS directory with current chat's workspace
        import os
        from pathlib import Path

        initial_ws = friday_repl._agent.memory.workspace
        if not initial_ws:
            os.chdir(friday_app.config.paths.app_home)
        elif Path(initial_ws).exists():
            os.chdir(initial_ws)
        try:
            search_tool = friday_repl._agent.tools.get_tool("semantic_search")
            search_tool.workspace_path = initial_ws or "."  # type: ignore[attr-defined]
            search_tool._indexer = None  # type: ignore[attr-defined]
        except KeyError:
            pass

        # Subscribe to agent memory changes to stream updates live
        def on_memory_change(memory_instance: Any = None) -> None:
            mem = memory_instance or friday_repl._agent.memory
            chat_id = mem.chat_id
            # Filter out system messages — the UI should never see them
            ui_messages = [
                m
                for m in mem.get_messages(inject_system=False)
                if m.get("role") != "system"
            ]
            chats = mem.get_all_chats()

            safe_send_ws(
                websocket,
                {
                    "type": "chat_history",
                    "chat_id": chat_id,
                    "messages": ui_messages,
                },
                loop,
            )
            safe_send_ws(
                websocket,
                {"type": "chats_list", "chats": chats},
                loop,
            )
            safe_send_ws(
                websocket,
                {
                    "type": "workspace_set",
                    "path": mem.workspace,
                    "chat_id": chat_id,
                },
                loop,
            )

        friday_repl._agent.memory.add_on_change_callback(on_memory_change)
        on_memory_change()

        try:
            while True:
                data = await websocket.receive_text()
                # guard against broken json so ws doesnt randomly crash
                try:
                    payload = json.loads(data)
                except Exception as exc:
                    logger.warning("invalid json on ws: %s", exc)
                    continue

                if payload.get("type") == "permission_response":
                    global permission_result
                    permission_result = payload.get("approved", False)
                    permission_event.set()

                elif payload.get("type") == "get_chats":
                    chats = await asyncio.to_thread(
                        friday_repl._agent.memory.get_all_chats
                    )
                    await websocket.send_text(
                        json.dumps({"type": "chats_list", "chats": chats})
                    )

                elif payload.get("type") == "switch_chat":
                    chat_id = payload.get("chat_id")
                    if chat_id:
                        await asyncio.to_thread(
                            friday_repl._agent.memory.switch_chat, chat_id
                        )

                        # Apply this chat's workspace
                        import os

                        ws_path = friday_repl._agent.memory.workspace
                        if not ws_path:
                            os.chdir(friday_app.config.paths.app_home)
                        elif Path(ws_path).exists():
                            os.chdir(ws_path)

                        try:
                            search_tool = friday_repl._agent.tools.get_tool(
                                "semantic_search"
                            )
                            search_tool.workspace_path = ws_path or "."  # type: ignore[attr-defined]
                            search_tool._indexer = None  # type: ignore[attr-defined]
                        except KeyError:
                            pass

                        # Also send back the messages for this chat
                        await websocket.send_text(
                            json.dumps(
                                {
                                    "type": "chat_history",
                                    "chat_id": chat_id,
                                    "title": friday_repl._agent.memory.title,
                                    "messages": friday_repl._agent.memory._messages,
                                }
                            )
                        )
                        await websocket.send_text(
                            json.dumps(
                                {
                                    "type": "workspace_set",
                                    "path": ws_path,
                                    "chat_id": chat_id,
                                }
                            )
                        )

                elif payload.get("type") == "get_workspaces":
                    def _read_workspaces() -> list[str]:
                        ws_file = friday_app.config.paths.data_dir / "workspaces.json"
                        if ws_file.exists():
                            try:
                                loaded: Any = json.loads(
                                    ws_file.read_text(encoding="utf-8")
                                )
                                if isinstance(loaded, list):
                                    return [str(item) for item in loaded]
                            except Exception:
                                pass
                        return []

                    workspaces = await asyncio.to_thread(_read_workspaces)
                    await websocket.send_text(
                        json.dumps(
                            {"type": "workspaces_list", "workspaces": workspaces}
                        )
                    )

                elif payload.get("type") == "rename_chat":
                    # parse payload flexibly whether native dict, stringified json, or flat keys
                    raw_data = payload.get("payload")
                    if isinstance(raw_data, dict):
                        data_obj = raw_data
                    elif isinstance(raw_data, str):
                        try:
                            data_obj = json.loads(raw_data)
                        except Exception:
                            data_obj = {}
                    else:
                        data_obj = payload

                    chat_id = (
                        data_obj.get("id")
                        or data_obj.get("chat_id")
                        or payload.get("chat_id")
                        or payload.get("id")
                    )
                    title = data_obj.get("title") or payload.get("title")
                    if chat_id and title:
                        await asyncio.to_thread(
                            friday_repl._agent.memory.rename_chat,
                            str(chat_id),
                            str(title),
                        )
                        chats = await asyncio.to_thread(
                            friday_repl._agent.memory.get_all_chats
                        )
                        try:
                            await websocket.send_text(
                                json.dumps({"type": "chats_list", "chats": chats})
                            )
                        except Exception:
                            pass

                elif payload.get("type") == "delete_chat":
                    chat_id = payload.get("chat_id")
                    if chat_id:
                        await asyncio.to_thread(
                            friday_repl._agent.memory.delete_chat, chat_id
                        )
                        chats = await asyncio.to_thread(
                            friday_repl._agent.memory.get_all_chats
                        )
                        await websocket.send_text(
                            json.dumps({"type": "chats_list", "chats": chats})
                        )

                elif payload.get("type") == "stop_tts":
                    global active_tts
                    if active_tts:
                        try:
                            active_tts.stop()
                        except Exception as e:
                            print(f"Failed to stop TTS: {e}")

                elif payload.get("type") == "stop_generation":
                    global agent_cancel_event
                    agent_cancel_event.set()
                    if active_tts:
                        try:
                            active_tts.stop()
                        except Exception:
                            pass

                elif payload.get("type") == "stop_voice":
                    global voice_abort_event
                    voice_abort_event.set()

                elif payload.get("type") == "set_workspace":
                    import os

                    path = payload.get("path", "")
                    chat_id = friday_repl._agent.memory.current_chat_id
                    ws_target = str(path) if path is not None else ""

                    def _sync_set_workspace(target_path: str = ws_target) -> list[str]:
                        friday_repl._agent.memory.workspace = target_path
                        friday_repl._agent.memory.save()

                        if target_path == "":
                            os.chdir(friday_app.config.paths.app_home)
                        elif target_path and Path(target_path).exists():
                            os.chdir(target_path)

                        ws_file = friday_app.config.paths.data_dir / "workspaces.json"
                        workspaces_list: list[str] = []
                        if ws_file.exists():
                            try:
                                loaded: Any = json.loads(
                                    ws_file.read_text(encoding="utf-8")
                                )
                                if isinstance(loaded, list):
                                    workspaces_list = [str(item) for item in loaded]
                            except Exception:
                                pass
                        if target_path and target_path not in workspaces_list:
                            workspaces_list.insert(0, target_path)
                            ws_file.write_text(
                                json.dumps(workspaces_list[:10]), encoding="utf-8"
                            )
                        return workspaces_list

                    workspaces = await asyncio.to_thread(_sync_set_workspace)

                    if path == "":
                        if chat_id:
                            friday_repl._agent.memory.add_message(
                                "system",
                                "The user cleared the workspace. You are no longer "
                                "constrained to a specific project folder.",
                                chat_id=chat_id,
                            )
                            # add visual message for user too
                            friday_repl._agent.memory.add_message(
                                "assistant", "📁 Workspace cleared.", chat_id=chat_id
                            )
                            await websocket.send_text(
                                json.dumps(
                                    {
                                        "type": "chat_history",
                                        "chat_id": chat_id,
                                        "messages": friday_repl._agent.memory.get_chat(
                                            chat_id
                                        )["messages"],
                                    }
                                )
                            )
                        await websocket.send_text(
                            json.dumps(
                                {
                                    "type": "workspace_set",
                                    "path": "",
                                    "chat_id": chat_id,
                                }
                            )
                        )

                    elif path and Path(path).exists():
                        try:
                            search_tool = friday_repl._agent.tools.get_tool(
                                "semantic_search"
                            )
                            search_tool.workspace_path = path  # type: ignore
                            search_tool._indexer = None  # type: ignore
                        except KeyError:
                            pass

                        if chat_id:
                            friday_repl._agent.memory.add_message(
                                "system",
                                f"The user changed the workspace directory to: {path}. "
                                "All file operations should be relative "
                                "to this directory.",
                                chat_id=chat_id,
                            )
                            friday_repl._agent.memory.add_message(
                                "assistant",
                                f"📁 Workspace set to: `{path}`",
                                chat_id=chat_id,
                            )
                            await websocket.send_text(
                                json.dumps(
                                    {
                                        "type": "chat_history",
                                        "chat_id": chat_id,
                                        "messages": friday_repl._agent.memory.get_chat(
                                            chat_id
                                        )["messages"],
                                    }
                                )
                            )

                        await websocket.send_text(
                            json.dumps(
                                {
                                    "type": "workspace_set",
                                    "path": path,
                                    "chat_id": chat_id,
                                }
                            )
                        )

                elif payload.get("type") == "message":
                    user_text = payload.get("content", "")

                    target_chat_id = friday_repl._agent.memory.chat_id

                    def run_friday(
                        msg_text: str = user_text, chat_id: str = target_chat_id
                    ) -> None:
                        try:
                            if msg_text.strip() == "/voice":
                                _handle_voice_for_ws(websocket, friday_app, loop)
                            elif msg_text.strip() == "/clear":
                                if friday_repl._agent.memory.chat_id == chat_id:
                                    friday_repl._agent.memory.clear()
                                else:
                                    from src.memory.conversation import (
                                        ConversationMemory,
                                    )

                                    temp_mem = ConversationMemory(
                                        chat_id=chat_id,
                                        save_dir=(
                                            friday_app.config.paths.data_dir / "chats"
                                            if friday_app.config
                                            else None
                                        ),
                                    )
                                    temp_mem.clear()
                            else:
                                import copy

                                from src.core.agent import Agent
                                from src.core.tool_registry import ToolRegistry
                                from src.memory.conversation import ConversationMemory

                                local_memory = ConversationMemory(
                                    system_prompt=(
                                        friday_repl._agent.memory.system_prompt
                                        if friday_repl
                                        and hasattr(friday_repl, "_agent")
                                        else (
                                            friday_app.config.llm.system_prompt
                                            if friday_app.config
                                            else None
                                        )
                                    ),
                                    chat_id=chat_id,
                                    save_dir=(
                                        friday_app.config.paths.data_dir / "chats"
                                        if friday_app.config
                                        else None
                                    ),
                                )
                                local_memory.add_on_change_callback(on_memory_change)

                                local_registry = ToolRegistry()
                                for tool_name in friday_repl._registry.list_tools():
                                    tool = friday_repl._registry.get_tool(tool_name)
                                    try:
                                        tool_copy = copy.copy(tool)
                                    except Exception:
                                        tool_copy = tool

                                    if (
                                        getattr(tool_copy, "name", None)
                                        == "delegate_task"
                                    ):
                                        tool_copy.registry = local_registry  # type: ignore[attr-defined]

                                    local_registry.register(tool_copy)

                                try:
                                    search_tool = local_registry.get_tool(
                                        "semantic_search"
                                    )
                                    search_tool.workspace_path = (  # type: ignore[attr-defined]
                                        local_memory.workspace or "."
                                    )
                                    search_tool._indexer = None  # type: ignore[attr-defined]
                                except KeyError:
                                    pass

                                original_local_execute = local_registry.execute

                                def local_registry_execute(
                                    name: str, **kwargs: Any
                                ) -> Any:
                                    from src.tools.base import ToolResult

                                    cmd_str = name
                                    if name == "execute_command":
                                        cmd_str = str(kwargs.get("command", kwargs))
                                    else:
                                        args = ", ".join(
                                            f"{k}={v!r}" for k, v in kwargs.items()
                                        )
                                        cmd_str = f"{name}({args})"

                                    if agent_cancel_event.is_set():
                                        return ToolResult(
                                            success=False,
                                            error="Execution cancelled by user.",
                                        )

                                    if not gui_confirmation_callback(str(cmd_str)):
                                        return ToolResult(
                                            success=False,
                                            error=f"User rejected permission to run: {cmd_str}",
                                        )

                                    if (
                                        name == "execute_command"
                                        and "cwd" not in kwargs
                                    ):
                                        kwargs["cwd"] = local_memory.workspace or str(
                                            friday_app.config.paths.app_home
                                        )
                                    return original_local_execute(name, **kwargs)

                                local_registry.execute = local_registry_execute  # type: ignore[method-assign]

                                agent_cancel_event.clear()
                                local_agent = Agent(
                                    llm_provider=friday_app.provider,
                                    tool_registry=local_registry,
                                    memory=local_memory,
                                    max_iterations=(
                                        friday_app.config.llm.max_iterations
                                        if friday_app.config
                                        else 10
                                    ),
                                    cancel_event=agent_cancel_event
                                )
                                local_agent.run(msg_text)

                                try:
                                    assistant_msgs = [
                                        m
                                        for m in local_memory.get_messages()
                                        if m.get("role") == "assistant"
                                    ]
                                    if assistant_msgs:
                                        last_msg = assistant_msgs[-1].get("content", "")
                                        if last_msg:
                                            from .._compat import load_settings_safe

                                            s = load_settings_safe()
                                            tts_enabled = (
                                                str(
                                                    s.get("tts_enabled", "true")
                                                ).lower()
                                                == "true"
                                            )
                                            if tts_enabled:
                                                with open(
                                                    friday_app.config.paths.data_dir
                                                    / "tts_debug.log",
                                                    "a",
                                                    encoding="utf-8",
                                                ) as f:
                                                    f.write(
                                                        f"Speak: {last_msg[:50]}...\n"
                                                    )
                                                from src.speech.tts_provider import (
                                                    EdgeTTSProvider,
                                                )

                                                global active_tts
                                                tts_voice = str(
                                                    s.get(
                                                        "tts_voice",
                                                        "ru-RU-SvetlanaNeural",
                                                    )
                                                )
                                                active_tts = EdgeTTSProvider(
                                                    voice=tts_voice
                                                )
                                                safe_send_ws(
                                                    websocket,
                                                    {
                                                        "type": "tts_state",
                                                        "playing": True,
                                                    },
                                                    loop,
                                                )
                                                try:
                                                    active_tts.speak(last_msg)
                                                finally:
                                                    # always reset tts and notify ui that speech stopped
                                                    active_tts = None
                                                    safe_send_ws(
                                                        websocket,
                                                        {
                                                            "type": "tts_state",
                                                            "playing": False,
                                                        },
                                                        loop,
                                                    )
                                except Exception as e:
                                    with open(
                                        friday_app.config.paths.data_dir
                                        / "tts_debug.log",
                                        "a",
                                        encoding="utf-8",
                                    ) as f:
                                        import traceback

                                        f.write(
                                            f"TTS fail: {e}\n{traceback.format_exc()}\n"
                                        )

                                if friday_repl._agent.memory.chat_id == chat_id:
                                    friday_repl._agent.memory.load()
                        except Exception as e:
                            import traceback

                            with open(
                                friday_app.config.paths.data_dir / "agent_crash.log",
                                "a",
                                encoding="utf-8",
                            ) as f:
                                f.write(
                                    f"Agent crashed: {e}\n{traceback.format_exc()}\n"
                                )
                            if friday_repl._agent.memory.chat_id == chat_id:
                                friday_repl._agent.memory.add_assistant_message(
                                    f"Error: {str(e)}"
                                )
                            else:
                                from src.memory.conversation import ConversationMemory

                                temp_mem = ConversationMemory(
                                    chat_id=chat_id,
                                    save_dir=(
                                        friday_app.config.paths.data_dir / "chats"
                                        if friday_app.config
                                        else None
                                    ),
                                )
                                temp_mem.add_assistant_message(f"Error: {str(e)}")
                        finally:
                            # send done signal to ui if ws is still alive
                            safe_send_ws(
                                websocket,
                                {"type": "done", "command": msg_text.strip()},
                                loop,
                            )

                    async def _async_agent_worker(
                        text: str = user_text, chat: str = target_chat_id
                    ) -> None:
                        current_loop = asyncio.get_running_loop()
                        try:
                            if _agent_executor is not None:
                                await current_loop.run_in_executor(
                                    _agent_executor,
                                    run_friday,
                                    text,
                                    chat,
                                )
                            else:
                                await asyncio.to_thread(
                                    run_friday, text, chat
                                )
                        except asyncio.CancelledError:
                            logger.info("Agent execution task cancelled")
                        except Exception as exc:
                            logger.exception("Agent worker error: %s", exc)

                    agent_task = asyncio.create_task(_async_agent_worker())
                    active_agent_tasks.add(agent_task)
                    agent_task.add_done_callback(active_agent_tasks.discard)

        except WebSocketDisconnect:
            pass
        except Exception as exc:
            # log any weird ws disconnect error
            logger.warning("websocket disconnected with error: %s", exc)
        finally:
            # clean up active websocket so we don't try sending to closed conn
            active_websocket = None
            # clean up callback so no leaks happen on reconnect
            try:
                friday_repl._agent.memory._on_change_callbacks.remove(on_memory_change)
            except (AttributeError, ValueError):
                pass

    from fastapi.middleware.cors import CORSMiddleware  # type: ignore

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")  # type: ignore
    async def add_cache_headers(request: Any, call_next: Any) -> Any:
        response = await call_next(request)
        if request.url.path == "/" or request.url.path.endswith(".html"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    @app.get("/health")  # type: ignore
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/settings")  # type: ignore
    async def get_settings() -> dict[str, Any]:
        from ..config import load_settings

        return await asyncio.to_thread(load_settings)

    @app.post("/api/settings")  # type: ignore
    async def update_settings(settings: dict[str, Any]) -> dict[str, Any]:
        from ..config import save_settings

        await asyncio.to_thread(save_settings, settings)
        await asyncio.to_thread(friday_app.reload_config)
        # Update the active agent's provider so it applies immediately without restart
        friday_repl._agent.llm = friday_app.provider
        if friday_app.config and friday_app.config.llm.system_prompt:
            friday_repl._agent.memory.system_prompt = (
                friday_app.config.llm.system_prompt
            )
        return {"status": "ok"}

    # Serve Vite build if it exists
    ui_dist = Path(__file__).parent.parent / "ui" / "dist"
    if ui_dist.exists() and ui_dist.is_dir():
        from fastapi.responses import FileResponse

        @app.get("/")
        async def serve_index() -> Any:
            return FileResponse(
                str(ui_dist / "index.html"),
                headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
            )

        app.mount("/", StaticFiles(directory=str(ui_dist), html=False), name="ui")
    else:

        @app.get("/")  # type: ignore
        async def root() -> HTMLResponse:
            return HTMLResponse(
                "<h1>Friday UI Not Found</h1><p>Build the UI in src/ui first.</p>"
            )

    return app


def start_server(host: str = "127.0.0.1", port: int | None = None) -> None:
    """Start the FastAPI server.

    If *port* is ``None`` (the default), automatically finds a free port
    starting from 8000 and writes it to ``~/.friday/runtime_port`` so that
    the UI and other components can discover it.
    """
    if uvicorn is None:
        print("Error: uvicorn not installed.")
        sys.exit(1)

    from src.utils.port import cleanup_runtime_port, find_free_port, write_runtime_port

    if port is None:
        port = find_free_port()

    port_file = write_runtime_port(port)
    print(f"Friday API server starting on http://{host}:{port}")
    print(f"Port written to {port_file}")

    app = create_app()
    try:
        uvicorn.run(app, host=host, port=port, log_level="error")
    finally:
        cleanup_runtime_port()


def main() -> int:
    """Entry point for friday-gui."""
    # Run the server in a daemon thread so it stops when webview closes
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    print("API server running. Press Ctrl+C to stop.")
    try:
        while True:
            import time

            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        from src.utils.port import cleanup_runtime_port

        cleanup_runtime_port()

    return 0


if __name__ == "__main__":
    sys.exit(main())
