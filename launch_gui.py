"""Launch the Friday GUI (webview window + API server)."""

import atexit
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

server_process = None
_server_port = 8000  # Will be updated once the server writes its port file


def _read_port() -> int:
    """Read the runtime port written by the API server."""
    port_file = Path.home() / ".friday" / "runtime_port"
    for _ in range(60):  # Wait up to 30 seconds (60 × 0.5s)
        try:
            text = port_file.read_text(encoding="utf-8").strip()
            if text:
                return int(text)
        except (FileNotFoundError, ValueError, OSError):
            pass
        time.sleep(0.5)
    return 8000  # Fallback


def _wait_for_server(port: int, timeout: float = 30.0) -> bool:
    """Poll the /health endpoint until the server is ready or timeout."""
    deadline = time.monotonic() + timeout
    url = f"http://127.0.0.1:{port}/health"
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except (URLError, OSError, Exception):
            pass
        time.sleep(0.5)
    return False


def start_server() -> None:
    """Start the FastAPI server as a subprocess using the current Python."""
    global server_process
    # Use sys.executable so we always use the correct Python interpreter,
    # regardless of what "python" points to in the system PATH.
    server_process = subprocess.Popen(
        [sys.executable, "-m", "src.api.server"],
        cwd=str(Path(__file__).resolve().parent),
    )


def cleanup() -> None:
    """Kill the server process tree (not just the parent) on Windows."""
    if server_process and server_process.poll() is None:
        if sys.platform == "win32":
            # taskkill /T kills the entire process tree, preventing orphans
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(server_process.pid)],
                    capture_output=True,
                    timeout=5,
                )
            except Exception:
                server_process.kill()
        else:
            server_process.terminate()
            try:
                server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_process.kill()

    # Clean up the port file
    try:
        port_file = Path.home() / ".friday" / "runtime_port"
        port_file.unlink(missing_ok=True)
    except OSError:
        pass


def open_wv(port: int) -> None:
    """Open the webview window pointing to the discovered port."""
    import webview

    window = webview.create_window(
        "Friday AI", f"http://127.0.0.1:{port}", width=1024, height=768
    )
    if window:
        window.events.closed += cleanup
    webview.start()


if __name__ == "__main__":
    atexit.register(cleanup)

    # Start API server in the background
    threading.Thread(target=start_server, daemon=True).start()

    # Wait for the server to write its port and become healthy
    port = _read_port()
    print(f"Discovered server on port {port}, waiting for health check...")

    if _wait_for_server(port):
        print(f"Server is ready on port {port}")
        open_wv(port)
    else:
        print(f"Warning: Server health check timed out on port {port}, opening anyway...")
        open_wv(port)
