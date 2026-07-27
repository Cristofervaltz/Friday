import subprocess
import threading
import time

import webview

server_process = None


def start_server() -> None:
    global server_process
    # Start the FastAPI server
    server_process = subprocess.Popen(["python", "-m", "src.api.server"])


def cleanup() -> None:
    if server_process:
        server_process.terminate()


def open_wv() -> None:
    window = webview.create_window(
        "Friday AI", "http://127.0.0.1:8000", width=1024, height=768
    )
    if window:
        window.events.closed += cleanup
    webview.start()


if __name__ == "__main__":
    import atexit

    atexit.register(cleanup)

    # Start API server in the background
    threading.Thread(target=start_server, daemon=True).start()
    time.sleep(2)  # Give server a moment to start
    open_wv()
