"""FastAPI server for the Friday GUI."""

import asyncio
import json
import logging
import sys
import threading
from pathlib import Path

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


def create_app() -> "FastAPI":
    """Create the FastAPI application."""
    if FastAPI is None:
        raise RuntimeError("FastAPI is not installed. Run 'pip install friday[gui]'.")

    app = FastAPI(title="Friday API")
    friday_app = FridayApplication()
    friday_app.initialize()

    # We use REPL to reuse the existing Agent and Tools wiring
    friday_repl = FridayREPL(friday_app)

    # We only really support one active GUI connected to the local agent
    # active_connection = None

    class WSMockIO:
        """Mock IO that routes print() calls to the WebSocket."""

        def __init__(self, ws: "WebSocket"):
            self.ws = ws

        def write(self, data: str) -> None:
            if not data.strip():
                return
            # We must use asyncio.run_coroutine_threadsafe because
            # Friday runs synchronously in a thread, while WS is async
            loop = asyncio.get_event_loop()
            asyncio.run_coroutine_threadsafe(
                self.ws.send_text(json.dumps({"type": "output", "content": data})),
                loop,
            )

        def flush(self) -> None:
            pass

    @app.websocket("/ws/chat")  # type: ignore
    async def websocket_endpoint(websocket: "WebSocket") -> None:
        await websocket.accept()

        # Hijack stdout just for this session if needed,
        # but better to let FridayApplication return text or stream to a callback.
        # Since FridayApplication uses print, we can intercept sys.stdout in a thread
        # Actually, FridayApplication is tightly coupled to console print.
        # To avoid massive refactoring, we'll run _handle_message in a thread.

        try:
            while True:
                data = await websocket.receive_text()
                payload = json.loads(data)

                if payload.get("type") == "message":
                    user_text = payload.get("content", "")

                    # Run Friday's message handling in a background thread to unblock WS
                    def run_friday(msg_text: str = user_text) -> None:
                        # Temporary stdout hijacking
                        original_stdout = sys.stdout
                        sys.stdout = WSMockIO(websocket)  # type: ignore
                        try:
                            # Use the REPL's message handling
                            friday_repl._handle_message(msg_text)
                        except Exception as e:
                            sys.stdout.write(f"Error: {str(e)}\\n")
                        finally:
                            sys.stdout = original_stdout
                            # Signal completion
                            loop = asyncio.get_event_loop()
                            asyncio.run_coroutine_threadsafe(
                                websocket.send_text(json.dumps({"type": "done"})),
                                loop,
                            )

                    threading.Thread(target=run_friday).start()

        except WebSocketDisconnect:
            pass

    @app.get("/health")  # type: ignore
    async def health() -> dict[str, str]:
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


"""FastAPI server for the Friday GUI."""

import asyncio
import json
import logging
import sys
import threading
from pathlib import Path

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


def create_app() -> "FastAPI":
    """Create the FastAPI application."""
    if FastAPI is None:
        raise RuntimeError("FastAPI is not installed. Run 'pip install friday[gui]'.")

    app = FastAPI(title="Friday API")
    friday_app = FridayApplication()
    friday_app.initialize()

    # We use REPL to reuse the existing Agent and Tools wiring
    friday_repl = FridayREPL(friday_app)

    # We only really support one active GUI connected to the local agent
    # active_connection = None

    class WSMockIO:
        """Mock IO that routes print() calls to the WebSocket."""

        def __init__(self, ws: "WebSocket"):
            self.ws = ws

        def write(self, data: str) -> None:
            if not data.strip():
                return
            # We must use asyncio.run_coroutine_threadsafe because
            # Friday runs synchronously in a thread, while WS is async
            loop = asyncio.get_event_loop()
            asyncio.run_coroutine_threadsafe(
                self.ws.send_text(json.dumps({"type": "output", "content": data})),
                loop,
            )

        def flush(self) -> None:
            pass

    @app.websocket("/ws/chat")  # type: ignore
    async def websocket_endpoint(websocket: "WebSocket") -> None:
        await websocket.accept()

        # Hijack stdout just for this session if needed,
        # but better to let FridayApplication return text or stream to a callback.
        # Since FridayApplication uses print, we can intercept sys.stdout in a thread
        # Actually, FridayApplication is tightly coupled to console print.
        # To avoid massive refactoring, we'll run _handle_message in a thread.

        try:
            while True:
                data = await websocket.receive_text()
                payload = json.loads(data)

                if payload.get("type") == "message":
                    user_text = payload.get("content", "")

                    # Run Friday's message handling in a background thread to unblock WS
                    def run_friday(msg_text: str = user_text) -> None:
                        # Temporary stdout hijacking
                        original_stdout = sys.stdout
                        sys.stdout = WSMockIO(websocket)  # type: ignore
                        try:
                            # Use the REPL's message handling
                            friday_repl._handle_message(msg_text)
                        except Exception as e:
                            sys.stdout.write(f"Error: {str(e)}\n")
                        finally:
                            sys.stdout = original_stdout
                            # Signal completion
                            loop = asyncio.get_event_loop()
                            asyncio.run_coroutine_threadsafe(
                                websocket.send_text(json.dumps({"type": "done"})),
                                loop,
                            )

                    threading.Thread(target=run_friday).start()

        except WebSocketDisconnect:
            pass

    @app.get("/health")  # type: ignore
    async def health() -> dict[str, str]:
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

    import webbrowser

    webbrowser.open("http://127.0.0.1:8000")

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
