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
    active_websocket = None
    server_loop = None
    permission_event = threading.Event()
    permission_result = False

    @app.websocket("/ws/chat")  # type: ignore
    async def websocket_endpoint(websocket: "WebSocket") -> None:
        global active_websocket, server_loop
        await websocket.accept()
        loop = asyncio.get_event_loop()
        server_loop = loop
        active_websocket = websocket

        # Subscribe to agent memory changes to stream updates live
        def on_memory_change() -> None:
            chat_id = friday_repl._agent.memory.chat_id
            # Filter out system messages — the UI should never see them
            ui_messages = [
                m
                for m in friday_repl._agent.memory.get_messages()
                if m.get("role") != "system"
            ]
            chats = friday_repl._agent.memory.get_all_chats()

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

            asyncio.run_coroutine_threadsafe(send_updates(), loop)

        friday_repl._agent.memory.add_on_change_callback(on_memory_change)

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

                elif payload.get("type") == "set_workspace":
                    import os

                    path = payload.get("path")
                    chat_id = friday_repl._agent.memory.current_chat_id

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
                            json.dumps({"type": "workspace_set", "path": ""})
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
                            json.dumps({"type": "workspace_set", "path": path})
                        )

                elif payload.get("type") == "message":
                    user_text = payload.get("content", "")

                    def run_friday(msg_text: str = user_text) -> None:
                        try:
                            if msg_text.strip() == "/voice":
                                # Handle voice separately: only transcribe,
                                # don't send to LLM. Return text to UI.
                                _handle_voice_for_ws(websocket, friday_app, loop)
                            elif msg_text.strip() == "/clear":
                                # Clear backend conversation memory
                                friday_repl._agent.memory.clear()
                            else:
                                # Use the REPL's message handling
                                friday_repl._handle_message(msg_text)
                        except Exception as e:
                            # Add error to agent memory directly
                            friday_repl._agent.memory.add_assistant_message(
                                f"Error: {str(e)}"
                            )
                        finally:
                            # Signal completion
                            asyncio.run_coroutine_threadsafe(
                                websocket.send_text(json.dumps({"type": "done"})),
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
        return {"status": "ok"}

    # Serve Vite build if it exists
    ui_dist = Path(__file__).parent.parent / "ui" / "dist"
    if ui_dist.exists() and ui_dist.is_dir():
        app.mount("/", StaticFiles(directory=str(ui_dist), html=True), name="ui")
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
