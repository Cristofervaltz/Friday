"""Entry point for the Friday sidecar (used by Tauri)."""

import os
import sys
from pathlib import Path


def main() -> None:
    print("Starting Friday sidecar...")

    current_dir = Path(os.getcwd()).resolve()
    project_root = current_dir

    while project_root.parent != project_root:
        if (project_root / "src" / "api" / "server.py").exists():
            break
        project_root = project_root.parent

    if not (project_root / "src" / "api" / "server.py").exists():
        # Fallback to hardcoded path for local dev if not found
        project_root = Path(r"C:\Users\Klim\OneDrive\Desktop\Friday")

    # Add project root to sys.path so src module can be resolved
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    # Set CWD to the project root
    os.chdir(str(project_root))

    # Import and run directly in this process
    from src.api.server import start_server

    try:
        print(f"Launching API server in {project_root}")
        start_server(host="127.0.0.1", port=8000)
    except KeyboardInterrupt:
        print("Sidecar stopped.")


if __name__ == "__main__":
    main()
