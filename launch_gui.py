import threading
import webview
import time
import os
import subprocess


def start_server():
    # Start the FastAPI server
    subprocess.Popen(["python", "-m", "src.api.server"])


def open_wv():
    webview.create_window("Friday AI", "http://127.0.0.1:8000", width=1024, height=768)
    webview.start()


if __name__ == "__main__":
    # Start API server in the background
    threading.Thread(target=start_server, daemon=True).start()
    time.sleep(2)  # Give server a moment to start
    open_wv()
