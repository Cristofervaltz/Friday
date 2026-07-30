"""Entry point for the Friday sidecar (used by Tauri)."""

import os
import sys
from pathlib import Path


def main() -> None:
    print("Starting Friday sidecar...")

    if getattr(sys, "frozen", False):
        # If running as a PyInstaller bundle, the root is the temporary extraction folder
        project_root = Path(getattr(sys, "_MEIPASS"))
        sys.path.insert(0, str(project_root))
        # Do not change cwd, server.py will handle workspace switching
    else:
        # If running in local dev environment
        project_root = Path(__file__).resolve().parent
        while project_root.parent != project_root:
            if (project_root / "src" / "api" / "server.py").exists():
                break
            project_root = project_root.parent

        if not (project_root / "src" / "api" / "server.py").exists():
            print("Failed to find project root.")
        
        # Set working directory to project root so relative paths work in dev
        os.chdir(str(project_root))
        sys.path.insert(0, str(project_root))

    # Import and run directly in this process
    from src.api.server import start_server

    try:
        print(f"Launching API server in {project_root}")
        start_server(host="127.0.0.1", port=8000)
    except KeyboardInterrupt:
        print("Sidecar stopped.")


if __name__ == "__main__":
    main()
