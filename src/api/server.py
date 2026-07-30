"""FastAPI server for the Friday GUI."""

import asyncio
import json
import logging
import sys
import threading
from pathlib import Path
from typing import Any

try:
    import uvicorn  # type: ignore
    import webview  # type: ignore
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect  # type: ignore
    from fastapi.responses import HTMLResponse  # type: ignore
    from fastapi.staticfiles import StaticFiles  # type: ignore
except ImportError:
    FastAPI = None  # type: ignore
    uvicorn = None  # type: ignore
    webview = None  # type: ignore

from ..cli.repl import FridayREPL
from ..runtime import FridayApplication

logger = logging.getLogger(__name__)

active_websocket: Any = None
server_loop: asyncio.AbstractEventLoop | None = None
permission_event: threading.Event = threading.Event()
permission_result: bool = False
wake_word_detector: Any = None
active_tts: Any = None


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

        text = provider.listen_and_transcribe()

        print(f"Voice captured: {text}")

        # Send transcribed text back to the UI as a special message type
        asyncio.run_coroutine_threadsafe(
            websocket.send_text(json.dumps({"type": "voice_result", "text": text})),
            loop,
        )
    except RuntimeError as exc:
        asyncio.run_coroutine_threadsafe(
            websocket.send_text(json.dumps({"type": "voice_error", "error": str(exc)})),
            loop,
        )
    except TimeoutError:
        asyncio.run_coroutine_threadsafe(
            websocket.send_text(
                json.dumps(
                    {
                        "type": "voice_error",
                        "error": "No speech detected. Microphone timed out.",
                    }
                )
            ),
            loop,
        )
    except Exception as exc:
        asyncio.run_coroutine_threadsafe(
            websocket.send_text(json.dumps({"type": "voice_error", "error": str(exc)})),
            loop,
        )


def create_app() -> "FastAPI":
    """Create the FastAPI application."""
    if FastAPI is None:
        raise RuntimeError("FastAPI is not installed. Run 'pip install friday[gui]'.")

    app = FastAPI(title="Friday API")
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

        permission_event.clear()
        asyncio.run_coroutine_threadsafe(
            active_websocket.send_text(
                json.dumps({"type": "permission_request", "action": command})
            ),
            server_loop,
        )

        # Wait up to 5 minutes for user response
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

    def _on_wake_word() -> None:
        global active_websocket, server_loop
        if active_websocket and server_loop:
            try:
                import asyncio
                import json

                asyncio.run_coroutine_threadsafe(
                    active_websocket.send_text(json.dumps({"type": "wake_word"})),
                    server_loop,
                )
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

    @app.on_event("startup")
    async def startup_event() -> None:
        """Initialize server resources on startup."""
        global server_loop
        server_loop = asyncio.get_running_loop()
        _start_wake_word()

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

            async def send_updates() -> None:
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "chat_history",
                            "chat_id": chat_id,
                            "messages": ui_messages,
                        }
                    )
                )
                await websocket.send_text(
                    json.dumps({"type": "chats_list", "chats": chats})
                )
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "workspace_set",
                            "path": mem.workspace,
                            "chat_id": chat_id,
                        }
                    )
                )

            asyncio.run_coroutine_threadsafe(send_updates(), loop)

        friday_repl._agent.memory.add_on_change_callback(on_memory_change)
        on_memory_change()

        try:
            while True:
                data = await websocket.receive_text()
                payload = json.loads(data)

                if payload.get("type") == "permission_response":
                    global permission_result
                    permission_result = payload.get("approved", False)
                    permission_event.set()

                elif payload.get("type") == "get_chats":
                    chats = friday_repl._agent.memory.get_all_chats()
                    await websocket.send_text(
                        json.dumps({"type": "chats_list", "chats": chats})
                    )

                elif payload.get("type") == "switch_chat":
                    chat_id = payload.get("chat_id")
                    if chat_id:
                        friday_repl._agent.memory.switch_chat(chat_id)

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
                    ws_file = friday_app.config.paths.data_dir / "workspaces.json"
                    workspaces = []
                    if ws_file.exists():
                        try:
                            workspaces = json.loads(ws_file.read_text(encoding="utf-8"))
                        except Exception:
                            pass
                    await websocket.send_text(
                        json.dumps(
                            {"type": "workspaces_list", "workspaces": workspaces}
                        )
                    )

                elif payload.get("type") == "rename_chat":
                    data_obj = json.loads(payload.get("payload", "{}"))
                    chat_id = data_obj.get("id")
                    title = data_obj.get("title")
                    if chat_id and title:
                        friday_repl._agent.memory.rename_chat(chat_id, title)
                        chats = friday_repl._agent.memory.get_all_chats()
                        await websocket.send_text(
                            json.dumps({"type": "chats_list", "chats": chats})
                        )

                elif payload.get("type") == "delete_chat":
                    chat_id = payload.get("chat_id")
                    if chat_id:
                        friday_repl._agent.memory.delete_chat(chat_id)
                        chats = friday_repl._agent.memory.get_all_chats()
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

                elif payload.get("type") == "set_workspace":
                    import os

                    path = payload.get("path")
                    chat_id = friday_repl._agent.memory.current_chat_id

                    friday_repl._agent.memory.workspace = path
                    friday_repl._agent.memory.save()

                    if path == "":
                        os.chdir(friday_app.config.paths.app_home)
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
                        os.chdir(path)
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

                        # Save to recent workspaces
                        ws_file = friday_app.config.paths.data_dir / "workspaces.json"
                        workspaces = []
                        if ws_file.exists():
                            try:
                                workspaces = json.loads(
                                    ws_file.read_text(encoding="utf-8")
                                )
                            except Exception:
                                pass
                        if path not in workspaces:
                            workspaces.insert(0, path)
                        ws_file.write_text(
                            json.dumps(workspaces[:10]), encoding="utf-8"
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
                                from src.core.agent import Agent
                                from src.memory.conversation import ConversationMemory
                                from src.core.tool_registry import ToolRegistry
                                import copy

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
                                    if (
                                        name == "execute_command"
                                        and "cwd" not in kwargs
                                    ):
                                        kwargs["cwd"] = local_memory.workspace or str(
                                            friday_app.config.paths.app_home
                                        )
                                    return original_local_execute(name, **kwargs)

                                local_registry.execute = local_registry_execute  # type: ignore[method-assign]

                                local_agent = Agent(
                                    llm_provider=friday_app.provider,
                                    tool_registry=local_registry,
                                    memory=local_memory,
                                    max_iterations=(
                                        friday_app.config.llm.max_iterations
                                        if friday_app.config
                                        else 10
                                    ),
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
                                                    r"c:\Users\Klim\OneDrive\Desktop\Friday\tts_debug.log",
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
                                                asyncio.run_coroutine_threadsafe(
                                                    websocket.send_text(
                                                        json.dumps(
                                                            {
                                                                "type": "tts_state",
                                                                "playing": True,
                                                            }
                                                        )
                                                    ),
                                                    loop,
                                                )
                                                active_tts.speak(last_msg)
                                                active_tts = None
                                                asyncio.run_coroutine_threadsafe(
                                                    websocket.send_text(
                                                        json.dumps(
                                                            {
                                                                "type": "tts_state",
                                                                "playing": False,
                                                            }
                                                        )
                                                    ),
                                                    loop,
                                                )
                                except Exception as e:
                                    with open(
                                        r"c:\Users\Klim\OneDrive\Desktop\Friday\tts_debug.log",
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
                                r"c:\Users\Klim\OneDrive\Desktop\Friday\agent_crash.log",
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
                            # Signal completion
                            asyncio.run_coroutine_threadsafe(
                                websocket.send_text(
                                    json.dumps(
                                        {"type": "done", "command": msg_text.strip()}
                                    )
                                ),
                                loop,
                            )

                    threading.Thread(target=run_friday).start()

        except WebSocketDisconnect:
            pass
        finally:
            # Clean up the callback to prevent memory leak on reconnects
            try:
                friday_repl._agent.memory._on_change_callbacks.remove(on_memory_change)
            except ValueError:
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

        return load_settings()

    @app.post("/api/settings")  # type: ignore
    async def update_settings(settings: dict[str, Any]) -> dict[str, Any]:
        from ..config import save_settings

        save_settings(settings)
        friday_app.reload_config()
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


def start_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Start the FastAPI server."""
    if uvicorn is None:
        print("Error: uvicorn not installed.")
        sys.exit(1)

    app = create_app()
    uvicorn.run(app, host=host, port=port, log_level="error")


def main() -> int:
    """Entry point for friday-gui."""
    # Run the server in a daemon thread so it stops when webview closes
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    # webbrowser.open("http://127.0.0.1:8000")

    print("API server running. Press Ctrl+C to stop.")
    try:
        while True:
            import time

            time.sleep(1)
    except KeyboardInterrupt:
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
